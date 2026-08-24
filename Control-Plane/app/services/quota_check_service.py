"""Quota check / reserve / commit / rollback with PostgreSQL-authoritative capacity."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.constants import (
    ORG_STATUS_ACTIVE,
    QUOTA_OP_CHECK,
    QUOTA_OP_RESERVE,
    QUOTA_STATUS_COMMITTED,
    QUOTA_STATUS_DENIED,
    QUOTA_STATUS_EXPIRED,
    QUOTA_STATUS_HELD,
    QUOTA_STATUS_PENDING,
    QUOTA_STATUS_ROLLED_BACK,
    ROLE_VIEWER,
)
from app.models.organization import Organization
from app.models.organization_entitlement import OrganizationEntitlement
from app.models.organization_member import OrganizationMember
from app.models.quota_action import QuotaAction
from app.models.quota_check_request import QuotaCheckRequest
from app.services.audit_service import log_audit
from app.services.credit_service import (
    commit_credits,
    consume_credits,
    hold_credits,
    rollback_credits,
)
from app.services.pricing_service import get_rate_cents_per_compute_unit
from app.services.quota_accounting_service import (
    QuotaConflictError,
    QuotaStateError,
    apply_reserved_units,
    apply_used_units,
    assert_fingerprint,
    check_capacity,
    claim_request,
    get_reservation_for_update,
    load_org_limits_from_db,
    lock_buckets_for_limits,
    naive_utc_now,
    release_reserved_and_consume,
    release_reserved_only,
    request_fingerprint,
)
from app.services.quota_cache_service import get_org_status
from app.services.subscription_service import get_current_subscription
from app.services.usage_ledger_service import record_usage


async def _get_action_by_key(db: AsyncSession, action_key: str) -> QuotaAction | None:
    result = await db.execute(
        select(QuotaAction)
        .options(selectinload(QuotaAction.product))
        .where(QuotaAction.action_key == action_key)
    )
    return result.scalars().one_or_none()


def _response_from_row(row: QuotaCheckRequest) -> dict:
    out: dict = {
        "allowed": bool(row.allowed),
        "reason": row.reason,
        "status": row.status,
        "request_id": row.request_id,
    }
    if row.actual_cost_cents is not None:
        out["actual_cost_cents"] = int(row.actual_cost_cents)
    if row.expires_at is not None:
        out["expires_at"] = row.expires_at.isoformat() + "Z"
    return out


async def _deny_pending(
    db: AsyncSession,
    row: QuotaCheckRequest,
    reason: str,
    action_key: str,
    org_id: UUID,
    audit_result: str,
) -> dict:
    now = naive_utc_now()
    row.status = QUOTA_STATUS_DENIED
    row.allowed = False
    row.reason = reason
    row.updated_at = now
    await log_audit(db, organization_id=org_id, action_key=action_key, result=audit_result)
    await db.flush()
    return _response_from_row(row)


async def _validate_common(
    db: AsyncSession,
    redis: Redis,
    org_id: UUID,
    action_key: str,
) -> tuple[Organization | None, QuotaAction | None, str | None, str]:
    """
    Shared gates. Returns (org, action, deny_reason, audit_suffix).
    deny_reason is None when all gates pass.
    """
    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalars().one_or_none()

    status = await get_org_status(redis, db, org_id)
    if status != ORG_STATUS_ACTIVE:
        return org, None, f"organization status is {status or 'unknown'}", "deny:org_status"

    sub = await get_current_subscription(db, org_id)
    if sub is None:
        return org, None, "no active subscription", "deny:subscription_inactive"

    action = await _get_action_by_key(db, action_key)
    if action is None or not action.is_active:
        return org, None, "action not found or inactive", "deny:action_invalid"

    if action.product is not None:
        ent_result = await db.execute(
            select(OrganizationEntitlement).where(
                OrganizationEntitlement.organization_id == org_id,
                OrganizationEntitlement.product_id == action.product_id,
            )
        )
        ent = ent_result.scalars().first()
        now = naive_utc_now()
        if not ent:
            return (
                org,
                action,
                f"Organization is not entitled to product '{action.product.product_key}'",
                "deny:not_entitled",
            )
        if ent.expires_at and ent.expires_at < now:
            return (
                org,
                action,
                f"Entitlement to product '{action.product.product_key}' has expired",
                "deny:not_entitled",
            )

    return org, action, None, "allow"


async def _deny_reason_for_member(
    db: AsyncSession,
    org_id: UUID,
    member_id: UUID | None,
) -> tuple[str | None, str | None]:
    """
    If member_id is set, require membership and reject viewers.
    Returns (deny_reason, audit_suffix) or (None, None) when allowed / member_id omitted.
    """
    if member_id is None:
        return None, None
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.member_id == member_id,
        )
    )
    om = result.scalars().one_or_none()
    if om is None:
        return "member not in organization", "deny:member_not_in_org"
    if om.role == ROLE_VIEWER:
        return "viewer_readonly", "deny:viewer_readonly"
    return None, None


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
    Check and consume quota. request_id is required.
    Postpay: cost_cents=0 on usage_ledger (invoice uses compute_units).
    Prepay: debit wallet before consuming counters.
    """
    if not request_id:
        raise ValueError("request_id is required")

    charge_compute_units = compute_units if compute_units is not None else units
    fingerprint = request_fingerprint(
        operation=QUOTA_OP_CHECK,
        action_key=action_key,
        units=units,
        compute_units=compute_units,
        member_id=member_id,
    )

    row, created = await claim_request(
        db,
        org_id=org_id,
        request_id=request_id,
        operation=QUOTA_OP_CHECK,
        fingerprint=fingerprint,
        member_id=member_id,
    )
    if not created:
        assert_fingerprint(row, fingerprint)
        if row.status == QUOTA_STATUS_PENDING:
            raise QuotaStateError("request is still pending", status=row.status)
        return _response_from_row(row)

    org, action, deny_reason, audit = await _validate_common(db, redis, org_id, action_key)
    if deny_reason:
        return await _deny_pending(db, row, deny_reason, action_key, org_id, audit)

    member_deny, member_audit = await _deny_reason_for_member(db, org_id, member_id)
    if member_deny:
        return await _deny_pending(db, row, member_deny, action_key, org_id, member_audit or "deny")

    assert org is not None and action is not None
    row.action_id = action.id
    row.member_id = member_id

    limits = await load_org_limits_from_db(db, org_id, action.id)
    locked = await lock_buckets_for_limits(db, org_id, action.id, limits) if limits else []
    exceeded = check_capacity(locked, units) if locked else None
    if exceeded:
        period, current, limit_value = exceeded
        reason = f"{period} limit exceeded"
        resp = await _deny_pending(db, row, reason, action_key, org_id, "deny:limit_exceeded")
        resp["current_usage"] = current
        resp["limit"] = limit_value
        return resp

    billing_mode = getattr(org, "billing_mode", "postpay")
    cost_cents = 0
    if billing_mode == "prepay":
        try:
            rate_cents = await get_rate_cents_per_compute_unit(db, action.id)
        except ValueError as exc:
            return await _deny_pending(
                db, row, str(exc), action_key, org_id, "deny:pricing_missing"
            )
        cost_cents = int(charge_compute_units) * int(rate_cents)
        success = await consume_credits(db, org_id, cost_cents, request_id=request_id)
        if not success:
            return await _deny_pending(
                db, row, "insufficient_credits", action_key, org_id, "deny:insufficient_credits"
            )

    if locked:
        await apply_used_units(locked, units)

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

    now = naive_utc_now()
    row.status = QUOTA_STATUS_COMMITTED
    row.allowed = True
    row.reason = None
    row.actual_units = units
    row.actual_compute_units = charge_compute_units
    row.actual_cost_cents = cost_cents
    row.updated_at = now
    await log_audit(db, organization_id=org_id, action_key=action_key, result="allow")
    await db.flush()

    response = _response_from_row(row)
    if locked:
        bucket, limit_value = locked[0]
        response["current_usage"] = int(bucket.used_units)
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
    """Phase 1: reserve quota capacity and optionally hold credits."""
    if not request_id:
        raise ValueError("request_id is required")
    if max_units < 1:
        raise ValueError("max_units must be >= 1")

    charge_compute_units = compute_units if compute_units is not None else max_units
    fingerprint = request_fingerprint(
        operation=QUOTA_OP_RESERVE,
        action_key=action_key,
        units=max_units,
        compute_units=compute_units,
        member_id=member_id,
    )

    row, created = await claim_request(
        db,
        org_id=org_id,
        request_id=request_id,
        operation=QUOTA_OP_RESERVE,
        fingerprint=fingerprint,
        member_id=member_id,
    )
    if not created:
        assert_fingerprint(row, fingerprint)
        if row.status == QUOTA_STATUS_HELD:
            return _response_from_row(row)
        if row.status == QUOTA_STATUS_DENIED:
            return _response_from_row(row)
        if row.status == QUOTA_STATUS_PENDING:
            raise QuotaStateError("request is still pending", status=row.status)
        raise QuotaConflictError(
            f"request_id already {row.status}",
            code="idempotency_key_terminal",
        )

    org, action, deny_reason, audit = await _validate_common(db, redis, org_id, action_key)
    if deny_reason:
        return await _deny_pending(db, row, deny_reason, action_key, org_id, audit)

    member_deny, member_audit = await _deny_reason_for_member(db, org_id, member_id)
    if member_deny:
        return await _deny_pending(db, row, member_deny, action_key, org_id, member_audit or "deny")

    assert org is not None and action is not None
    row.action_id = action.id
    row.member_id = member_id

    limits = await load_org_limits_from_db(db, org_id, action.id)
    locked = await lock_buckets_for_limits(db, org_id, action.id, limits) if limits else []
    exceeded = check_capacity(locked, max_units) if locked else None
    if exceeded:
        period, current, limit_value = exceeded
        reason = f"{period} limit exceeded"
        resp = await _deny_pending(db, row, reason, action_key, org_id, "deny:limit_exceeded")
        resp["current_usage"] = current
        resp["limit"] = limit_value
        return resp

    billing_mode = getattr(org, "billing_mode", "postpay")
    cost_cents = 0
    rate_cents: int | None = None
    if billing_mode == "prepay":
        try:
            rate_cents = await get_rate_cents_per_compute_unit(db, action.id)
        except ValueError as exc:
            return await _deny_pending(
                db, row, str(exc), action_key, org_id, "deny:pricing_missing"
            )
        cost_cents = int(charge_compute_units) * int(rate_cents)
        success = await hold_credits(db, org_id, cost_cents, request_id)
        if not success:
            return await _deny_pending(
                db, row, "insufficient_credits", action_key, org_id, "deny:insufficient_credits"
            )

    if locked:
        await apply_reserved_units(db, row.id, locked, max_units)

    now = naive_utc_now()
    row.status = QUOTA_STATUS_HELD
    row.allowed = True
    row.reason = None
    row.held_units = max_units
    row.held_cents = cost_cents
    row.held_compute_units = charge_compute_units
    row.rate_cents_per_compute_unit = rate_cents
    row.expires_at = now + timedelta(seconds=int(settings.QUOTA_HOLD_TTL_SECONDS))
    row.updated_at = now
    await db.flush()
    return _response_from_row(row)


async def quota_commit(
    db: AsyncSession,
    redis: Redis,
    org_id: UUID,
    request_id: str,
    actual_units: int,
    compute_units: int | None = None,
) -> dict:
    """Phase 2: commit reservation — consume actual usage and settle credits."""
    if actual_units < 0:
        raise ValueError("actual_units must be >= 0")

    qr = await get_reservation_for_update(db, org_id, request_id)
    if qr is None:
        raise LookupError("Reservation not found")

    if qr.status == QUOTA_STATUS_COMMITTED:
        return _response_from_row(qr)
    if qr.status != QUOTA_STATUS_HELD:
        raise QuotaStateError(
            f"reservation is {qr.status}, not held",
            status=qr.status,
        )

    held_units = int(qr.held_units or 0)
    held_compute = int(qr.held_compute_units or held_units)
    charge_compute = compute_units if compute_units is not None else actual_units
    if actual_units > held_units:
        raise ValueError("actual_units exceeds reserved max_units")
    if charge_compute > held_compute:
        raise ValueError("compute_units exceeds reserved max compute units")

    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalars().one()
    billing_mode = getattr(org, "billing_mode", "postpay")

    actual_cost = 0
    if billing_mode == "prepay":
        if qr.rate_cents_per_compute_unit is not None:
            actual_cost = int(charge_compute) * int(qr.rate_cents_per_compute_unit)
        elif qr.held_units and qr.held_units > 0:
            # Legacy holds without rate snapshot
            rate = int(qr.held_cents or 0) // int(qr.held_units)
            actual_cost = int(charge_compute) * rate
        await commit_credits(db, org_id, qr.held_cents or 0, actual_cost, request_id)

    await release_reserved_and_consume(db, qr, actual_units)

    if qr.action_id:
        result = await db.execute(select(QuotaAction).where(QuotaAction.id == qr.action_id))
        action = result.scalars().one_or_none()
        if action:
            await record_usage(
                db,
                organization_id=org_id,
                action_id=action.id,
                units=actual_units,
                unit_type=action.unit_type or "request",
                compute_units=charge_compute,
                cost_cents=actual_cost,
                member_id=qr.member_id,
                request_id=request_id,
            )

    now = naive_utc_now()
    qr.status = QUOTA_STATUS_COMMITTED
    qr.allowed = True
    qr.actual_units = actual_units
    qr.actual_compute_units = charge_compute
    qr.actual_cost_cents = actual_cost
    qr.updated_at = now
    await db.flush()
    return _response_from_row(qr)


async def quota_rollback(
    db: AsyncSession,
    org_id: UUID,
    request_id: str,
    *,
    expired: bool = False,
) -> dict:
    """Phase 2 alternative: release hold and reserved capacity."""
    qr = await get_reservation_for_update(db, org_id, request_id)
    if qr is None:
        raise LookupError("Reservation not found")

    if qr.status in (QUOTA_STATUS_ROLLED_BACK, QUOTA_STATUS_EXPIRED):
        return _response_from_row(qr)
    if qr.status == QUOTA_STATUS_COMMITTED:
        raise QuotaStateError("reservation already committed", status=qr.status)
    if qr.status != QUOTA_STATUS_HELD:
        raise QuotaStateError(
            f"reservation is {qr.status}, not held",
            status=qr.status,
        )

    await rollback_credits(db, org_id, qr.held_cents or 0, request_id)
    await release_reserved_only(db, qr)

    now = naive_utc_now()
    qr.status = QUOTA_STATUS_EXPIRED if expired else QUOTA_STATUS_ROLLED_BACK
    qr.updated_at = now
    await db.flush()
    return _response_from_row(qr)
