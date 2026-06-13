"""Quota check: allow/deny based on org limits, Redis counters, and lifetime DB."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    ORG_STATUS_ACTIVE,
    PERIOD_LIFETIME,
    PERIOD_PER_DAY,
    PERIOD_PER_MONTH,
)
from app.models.organization import Organization
from app.models.organization_usage_lifetime import OrganizationUsageLifetime
from app.models.quota_action import QuotaAction
from app.models.quota_check_request import QuotaCheckRequest
from app.models.product import Product
from app.services.audit_service import log_audit
from app.services.credit_service import consume_credits, hold_credits, commit_credits, rollback_credits
from app.services.pricing_service import get_rate_cents_per_compute_unit
from app.services.quota_cache_service import get_org_limits, get_org_status
from app.services.subscription_service import get_current_subscription
from app.services.usage_ledger_service import record_usage
from app.utils.redis_keys import (
    TTL_QUOTA_DAY,
    TTL_QUOTA_MONTH,
    quota_daily_key,
    quota_monthly_key,
    yyyymm,
    yyyymmdd,
)


async def _get_action_by_key(db: AsyncSession, action_key: str) -> QuotaAction | None:
    """Get quota_actions row by action_key with product joined."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(QuotaAction)
        .options(selectinload(QuotaAction.product))
        .where(QuotaAction.action_key == action_key)
    )
    return result.scalars().one_or_none()


def _limits_for_action(limits: list[dict], action_id: UUID) -> list[tuple[str, int]]:
    """Return list of (period, limit_value) for this action_id."""
    out = []
    for lim in limits:
        if lim.get("action_id") == str(action_id):
            out.append((lim["period"], int(lim["limit_value"])))
    return out


async def _get_lifetime_usage(db: AsyncSession, org_id: UUID, action_id: UUID) -> int:
    """Current lifetime usage from organization_usage_lifetime."""
    result = await db.execute(
        select(OrganizationUsageLifetime).where(
            OrganizationUsageLifetime.organization_id == org_id,
            OrganizationUsageLifetime.action_id == action_id,
        )
    )
    row = result.scalars().one_or_none()
    return row.used_units if row else 0


async def _increment_lifetime(
    db: AsyncSession, org_id: UUID, action_id: UUID, units: int
) -> None:
    """Increment (or create) organization_usage_lifetime by units."""
    result = await db.execute(
        select(OrganizationUsageLifetime).where(
            OrganizationUsageLifetime.organization_id == org_id,
            OrganizationUsageLifetime.action_id == action_id,
        )
    )
    row = result.scalars().one_or_none()
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for TIMESTAMP WITHOUT TIME ZONE
    if row is not None:
        row.used_units += units
        row.updated_at = now
    else:
        from uuid import uuid4

        row = OrganizationUsageLifetime(
            id=uuid4(),
            organization_id=org_id,
            action_id=action_id,
            used_units=units,
            updated_at=now,
        )
        db.add(row)
    await db.flush()


async def quota_check(
    redis: Redis,
    db: AsyncSession,
    org_id: UUID,
    action_key: str,
    units: int = 1,
    member_id: UUID | None = None,
    request_id: str | None = None,
    compute_units: int | None = None,
) -> dict:
    """
    Check if (org, action_key, units) is allowed.

    Responsibilities:
    - Enforce organization status (e.g. suspended => deny).
    - Enforce per-period limits (day, month, lifetime).
    - For prepaid orgs (billing_mode='prepay'), enforce wallet balance and deny with
      'insufficient_credits' if not enough balance.
    - Be idempotent per (organization_id, request_id) using QuotaCheckRequest.

    Returns dict with: allowed: bool, reason?: str, current_usage?: int, limit?: int.
    On allow, increments Redis and/or DB and records usage to usage_ledger for billing.
    """
    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalars().one_or_none()

    # 1. Org status (suspended => deny; used for non-payment / manual billing)
    status = await get_org_status(redis, db, org_id)
    if status != ORG_STATUS_ACTIVE:
        reason = f"organization status is {status or 'unknown'}"
        await log_audit(db, organization_id=org_id, action_key=action_key, result="deny:org_status")
        # quota_check_requests.organization_id FK requires a row in organizations
        if request_id is not None and org is not None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            db.add(
                QuotaCheckRequest(
                    id=uuid4(),
                    organization_id=org_id,
                    request_id=request_id,
                    allowed=False,
                    reason=reason,
                    created_at=now,
                )
            )
            await db.flush()
        return {"allowed": False, "reason": reason}

    # 1b. Existing idempotent decision for this (org, request_id)
    if request_id is not None:
        existing = await db.execute(
            select(QuotaCheckRequest).where(
                and_(
                    QuotaCheckRequest.organization_id == org_id,
                    QuotaCheckRequest.request_id == request_id,
                )
            )
        )
        qr = existing.scalars().one_or_none()
        if qr is not None:
            return {"allowed": qr.allowed, "reason": qr.reason}

    # 1c. Org billing mode (default postpay if not found)
    billing_mode = getattr(org, "billing_mode", "postpay")

    # 1d. Require active subscription (minimal plan enforcement)
    sub = await get_current_subscription(db, org_id)
    if sub is None:
        reason = "no active subscription"
        await log_audit(db, organization_id=org_id, action_key=action_key, result="deny:subscription_inactive")
        if request_id is not None and org is not None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            db.add(
                QuotaCheckRequest(
                    id=uuid4(),
                    organization_id=org_id,
                    request_id=request_id,
                    allowed=False,
                    reason=reason,
                    created_at=now,
                )
            )
            await db.flush()
        return {"allowed": False, "reason": reason}

    # 2. Action
    action = await _get_action_by_key(db, action_key)
    if action is None or not action.is_active:
        await log_audit(db, organization_id=org_id, action_key=action_key, result="deny:action_invalid")
        if request_id is not None and org is not None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            db.add(
                QuotaCheckRequest(
                    id=uuid4(),
                    organization_id=org_id,
                    request_id=request_id,
                    allowed=False,
                    reason="action not found or inactive",
                    created_at=now,
                )
            )
            await db.flush()
        return {"allowed": False, "reason": "action not found or inactive"}

    # 2b. Entitlement Check
    if action.product is not None:
        from app.models.organization_entitlement import OrganizationEntitlement
        from sqlalchemy import and_
        ent_result = await db.execute(
            select(OrganizationEntitlement).where(
                and_(
                    OrganizationEntitlement.organization_id == org_id,
                    OrganizationEntitlement.product_id == action.product_id,
                )
            )
        )
        ent = ent_result.scalars().first()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        reason = None
        if not ent:
            reason = f"Organization is not entitled to product '{action.product.product_key}'"
        elif ent.expires_at and ent.expires_at < now:
            reason = f"Entitlement to product '{action.product.product_key}' has expired"
            
        if reason:
            await log_audit(db, organization_id=org_id, action_key=action_key, result="deny:not_entitled")
            if request_id is not None and org is not None:
                db.add(
                    QuotaCheckRequest(
                        id=uuid4(),
                        organization_id=org_id,
                        request_id=request_id,
                        allowed=False,
                        reason=reason,
                        created_at=now,
                    )
                )
                await db.flush()
            return {"allowed": False, "reason": reason}

    # 3. Limits for this org
    limits_list = await get_org_limits(redis, db, org_id)
    action_limits = _limits_for_action(limits_list, action.id)

    org_id_str = str(org_id)
    day_key = quota_daily_key(org_id_str, action_key, yyyymmdd())
    month_key = quota_monthly_key(org_id_str, action_key, yyyymm())

    # 4. Read current usage for each period (no increment yet)
    current_usages: dict[str, int] = {}
    for period, limit_value in action_limits:
        if period == PERIOD_LIFETIME:
            current_usages[PERIOD_LIFETIME] = await _get_lifetime_usage(db, org_id, action.id)
        elif period == PERIOD_PER_DAY:
            raw = await redis.get(day_key)
            current_usages[PERIOD_PER_DAY] = int(raw) if raw else 0
        elif period == PERIOD_PER_MONTH:
            raw = await redis.get(month_key)
            current_usages[PERIOD_PER_MONTH] = int(raw) if raw else 0

    # 5. Check all limits would pass
    for period, limit_value in action_limits:
        current = current_usages.get(period, 0)
        if current + units > limit_value:
            await log_audit(db, organization_id=org_id, action_key=action_key, result="deny:limit_exceeded")
            reason = f"{period} limit exceeded"
            if request_id is not None and org is not None:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                db.add(
                    QuotaCheckRequest(
                        id=uuid4(),
                        organization_id=org_id,
                        request_id=request_id,
                        allowed=False,
                        reason=reason,
                        created_at=now,
                    )
                )
                await db.flush()
            return {
                "allowed": False,
                "reason": reason,
                "current_usage": current,
                "limit": limit_value,
            }

    # 6. If prepaid mode, enforce credits before writing usage / counters
    if billing_mode == "prepay":
        if request_id is None:
            reason = "request_id required for prepaid organizations"
            await log_audit(
                db, organization_id=org_id, action_key=action_key, result="deny:missing_request_id"
            )
            return {"allowed": False, "reason": reason}
        charge_compute_units = compute_units if compute_units is not None else units
        try:
            rate_cents = await get_rate_cents_per_compute_unit(db, action.id)
        except ValueError as exc:
            reason = str(exc)
            await log_audit(db, organization_id=org_id, action_key=action_key, result="deny:pricing_missing")
            if org is not None:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                db.add(
                    QuotaCheckRequest(
                        id=uuid4(),
                        organization_id=org_id,
                        request_id=request_id,
                        allowed=False,
                        reason=reason,
                        created_at=now,
                    )
                )
                await db.flush()
            return {"allowed": False, "reason": reason}

        cost_cents = int(charge_compute_units) * int(rate_cents)
        success = await consume_credits(db, org_id, cost_cents, request_id=request_id)
        if not success:
            reason = "insufficient_credits"
            await log_audit(
                db, organization_id=org_id, action_key=action_key, result="deny:insufficient_credits"
            )
            if org is not None:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                db.add(
                    QuotaCheckRequest(
                        id=uuid4(),
                        organization_id=org_id,
                        request_id=request_id,
                        allowed=False,
                        reason=reason,
                        created_at=now,
                    )
                )
                await db.flush()
            return {"allowed": False, "reason": reason}

    # 7. All pass: increment limits and record usage
    for period, limit_value in action_limits:
        if period == PERIOD_LIFETIME:
            await _increment_lifetime(db, org_id, action.id, units)
        elif period == PERIOD_PER_DAY:
            await redis.incrby(day_key, units)
            await redis.expire(day_key, TTL_QUOTA_DAY)
        elif period == PERIOD_PER_MONTH:
            await redis.incrby(month_key, units)
            await redis.expire(month_key, TTL_QUOTA_MONTH)

    # Representative usage/limit (first limit) if any limits exist
    if action_limits:
        period, limit_value = action_limits[0]
        current = current_usages.get(period, 0) + units
    else:
        period, limit_value, current = None, None, None

    await log_audit(db, organization_id=org_id, action_key=action_key, result="allow")
    await record_usage(
        db,
        organization_id=org_id,
        action_id=action.id,
        units=units,
        unit_type=action.unit_type or "request",
        compute_units=charge_compute_units,
        cost_cents=cost_cents,
        member_id=member_id,
        request_id=request_id,
    )

    if request_id is not None and org is not None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(
            QuotaCheckRequest(
                id=uuid4(),
                organization_id=org_id,
                request_id=request_id,
                allowed=True,
                reason=None,
                created_at=now,
            )
        )
        await db.flush()

    response: dict = {"allowed": True}
    if period is not None and limit_value is not None and current is not None:
        response["current_usage"] = current
        response["limit"] = limit_value
    return response


async def quota_reserve(
    redis: Redis,
    db: AsyncSession,
    org_id: UUID,
    action_key: str,
    max_units: int,
    request_id: str,
    member_id: UUID | None = None,
    compute_units: int | None = None,
) -> dict:
    """Phase 1: Reserve quota and hold credits."""
    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalars().one_or_none()

    status = await get_org_status(redis, db, org_id)
    if status != ORG_STATUS_ACTIVE:
        return {"allowed": False, "reason": f"organization status is {status or 'unknown'}"}

    # Check idempotency
    existing = await db.execute(
        select(QuotaCheckRequest).where(
            and_(
                QuotaCheckRequest.organization_id == org_id,
                QuotaCheckRequest.request_id == request_id,
            )
        )
    )
    qr = existing.scalars().one_or_none()
    if qr is not None:
        return {"allowed": qr.allowed, "reason": qr.reason}

    billing_mode = getattr(org, "billing_mode", "postpay")

    sub = await get_current_subscription(db, org_id)
    if sub is None:
        return {"allowed": False, "reason": "no active subscription"}

    action = await _get_action_by_key(db, action_key)
    if action is None or not action.is_active:
        return {"allowed": False, "reason": "action not found or inactive"}

    if action.product is not None:
        from app.models.organization_entitlement import OrganizationEntitlement
        from sqlalchemy import and_
        ent_result = await db.execute(
            select(OrganizationEntitlement).where(
                and_(
                    OrganizationEntitlement.organization_id == org_id,
                    OrganizationEntitlement.product_id == action.product_id,
                )
            )
        )
        ent = ent_result.scalars().first()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        reason = None
        if not ent:
            reason = f"Organization is not entitled to product '{action.product.product_key}'"
        elif ent.expires_at and ent.expires_at < now:
            reason = f"Entitlement to product '{action.product.product_key}' has expired"
            
        if reason:
            return {"allowed": False, "reason": reason}

    limits_list = await get_org_limits(redis, db, org_id)
    action_limits = _limits_for_action(limits_list, action.id)

    org_id_str = str(org_id)
    day_key = quota_daily_key(org_id_str, action_key, yyyymmdd())
    month_key = quota_monthly_key(org_id_str, action_key, yyyymm())

    current_usages: dict[str, int] = {}
    for period, limit_value in action_limits:
        if period == PERIOD_LIFETIME:
            current_usages[PERIOD_LIFETIME] = await _get_lifetime_usage(db, org_id, action.id)
        elif period == PERIOD_PER_DAY:
            raw = await redis.get(day_key)
            current_usages[PERIOD_PER_DAY] = int(raw) if raw else 0
        elif period == PERIOD_PER_MONTH:
            raw = await redis.get(month_key)
            current_usages[PERIOD_PER_MONTH] = int(raw) if raw else 0

    for period, limit_value in action_limits:
        current = current_usages.get(period, 0)
        if current + max_units > limit_value:
            return {"allowed": False, "reason": f"{period} limit exceeded"}

    cost_cents = 0
    if billing_mode == "prepay":
        charge_compute_units = compute_units if compute_units is not None else max_units
        try:
            rate_cents = await get_rate_cents_per_compute_unit(db, action.id)
        except ValueError as exc:
            return {"allowed": False, "reason": str(exc)}
        cost_cents = int(charge_compute_units) * int(rate_cents)
        
        success = await hold_credits(db, org_id, cost_cents, request_id)
        if not success:
            return {"allowed": False, "reason": "insufficient_credits"}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Note: For commit logic to know the action pricing, we temporarily encode the action_key into reason 
    # if it's not null, or we just rely on passing action_key in commit (but commit schema doesn't have it).
    # Since we can't change the commit schema yet, we will fetch pricing dynamically by storing action_id in the DB.
    # Wait, QuotaCheckRequest doesn't have action_id. But it's passed dynamically in the reserve.
    # Let's save the action_id in `reason` temporarily for the POC or we can just stick to proportional cost.
    # Actually, if we want accurate compute_units * rate, we MUST know the rate. 
    # Let's just calculate the rate from held_cents and max_units instead!
    # rate_cents_per_compute_unit = held_cents / max_units! That is brilliant.
    
    db.add(
        QuotaCheckRequest(
            id=uuid4(),
            organization_id=org_id,
            action_id=action.id,
            request_id=request_id,
            status="held",
            allowed=True,
            reason=None,
            held_units=max_units,
            held_cents=cost_cents,
            created_at=now,
        )
    )
    await db.flush()
    return {"allowed": True}


async def quota_commit(
    db: AsyncSession,
    redis: Redis,
    org_id: UUID,
    request_id: str,
    actual_units: int,
    compute_units: int | None = None,
) -> dict:
    """Phase 2: Commit usage and capture credits."""
    existing = await db.execute(
        select(QuotaCheckRequest).where(
            and_(
                QuotaCheckRequest.organization_id == org_id,
                QuotaCheckRequest.request_id == request_id,
            )
        )
    )
    qr = existing.scalars().one_or_none()
    if qr is None:
        raise ValueError("Reservation not found")
    if qr.status != "held":
        return {"status": qr.status}

    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalars().one()
    billing_mode = getattr(org, "billing_mode", "postpay")

    actual_cost = 0
    charge_compute = compute_units if compute_units is not None else actual_units
    
    if billing_mode == "prepay":
        # We calculate the exact rate used during reservation
        if qr.held_units and qr.held_units > 0:
            rate = qr.held_cents / qr.held_units
            actual_cost = int(charge_compute * rate)
        else:
            actual_cost = 0
            
        await commit_credits(db, org_id, qr.held_cents or 0, actual_cost, request_id)

    if qr.action_id:
        result = await db.execute(select(QuotaAction).where(QuotaAction.id == qr.action_id))
        action = result.scalars().one_or_none()
        if action:
            from app.services.usage_ledger_service import record_usage
            await record_usage(
                db,
                organization_id=org_id,
                action_id=action.id,
                units=actual_units,
                unit_type=action.unit_type,
                compute_units=charge_compute,
                cost_cents=actual_cost,
                member_id=None,
                request_id=request_id,
            )

    qr.status = "committed"
    await db.flush()
    return {"status": "committed", "actual_cost_cents": actual_cost}


async def quota_rollback(
    db: AsyncSession,
    org_id: UUID,
    request_id: str,
) -> dict:
    """Phase 2 Alternative: Rollback reservation."""
    existing = await db.execute(
        select(QuotaCheckRequest).where(
            and_(
                QuotaCheckRequest.organization_id == org_id,
                QuotaCheckRequest.request_id == request_id,
            )
        )
    )
    qr = existing.scalars().one_or_none()
    if qr is None:
        raise ValueError("Reservation not found")
    if qr.status != "held":
        return {"status": qr.status}

    await rollback_credits(db, org_id, qr.held_cents or 0, request_id)
    qr.status = "rolled_back"
    await db.flush()
    return {"status": "rolled_back"}
