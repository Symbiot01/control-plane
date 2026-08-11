"""Transactional PostgreSQL quota capacity and request-claim helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    PERIOD_LIFETIME,
    PERIOD_PER_DAY,
    PERIOD_PER_HOUR,
    PERIOD_PER_MINUTE,
    PERIOD_PER_MONTH,
    QUOTA_STATUS_PENDING,
)
from app.models.organization_quota_limit import OrganizationQuotaLimit
from app.models.quota_check_request import QuotaCheckRequest
from app.models.quota_usage_bucket import QuotaReservationAllocation, QuotaUsageBucket


class QuotaConflictError(Exception):
    """Same request_id with a different fingerprint or illegal state transition."""

    def __init__(self, detail: str, code: str = "idempotency_key_reuse_mismatch"):
        super().__init__(detail)
        self.detail = detail
        self.code = code


class QuotaStateError(Exception):
    """Illegal reservation state transition."""

    def __init__(self, detail: str, status: str | None = None):
        super().__init__(detail)
        self.detail = detail
        self.status = status


def naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def window_start_for_period(period: str, at: datetime | None = None) -> datetime:
    """Return naive UTC window start for a quota period."""
    now = at or naive_utc_now()
    if period == PERIOD_PER_MINUTE:
        return now.replace(second=0, microsecond=0)
    if period == PERIOD_PER_HOUR:
        return now.replace(minute=0, second=0, microsecond=0)
    if period == PERIOD_PER_DAY:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == PERIOD_PER_MONTH:
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period == PERIOD_LIFETIME:
        return datetime(1970, 1, 1)
    raise ValueError(f"Unsupported period: {period}")


def request_fingerprint(
    *,
    operation: str,
    action_key: str,
    units: int,
    compute_units: int | None,
    member_id: UUID | None,
) -> str:
    payload = {
        "operation": operation,
        "action_key": action_key,
        "units": int(units),
        "compute_units": None if compute_units is None else int(compute_units),
        "member_id": None if member_id is None else str(member_id),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def load_org_limits_from_db(
    db: AsyncSession, org_id: UUID, action_id: UUID
) -> list[tuple[str, int]]:
    """Return [(period, limit_value)] for this org/action from PostgreSQL."""
    result = await db.execute(
        select(OrganizationQuotaLimit).where(
            OrganizationQuotaLimit.organization_id == org_id,
            OrganizationQuotaLimit.action_id == action_id,
        )
    )
    rows = result.scalars().all()
    return [(r.period, int(r.limit_value)) for r in rows]


async def get_or_create_bucket(
    db: AsyncSession,
    org_id: UUID,
    action_id: UUID,
    period: str,
    window_start: datetime,
) -> QuotaUsageBucket:
    """Create bucket if missing, then lock it FOR UPDATE."""
    now = naive_utc_now()
    insert = text(
        """
        INSERT INTO quota_usage_buckets (
            id, organization_id, action_id, period, window_start,
            used_units, reserved_units, updated_at
        ) VALUES (
            :id, :organization_id, :action_id, :period, :window_start,
            0, 0, :updated_at
        )
        ON CONFLICT (organization_id, action_id, period, window_start) DO NOTHING
        """
    )
    await db.execute(
        insert,
        {
            "id": uuid4(),
            "organization_id": org_id,
            "action_id": action_id,
            "period": period,
            "window_start": window_start,
            "updated_at": now,
        },
    )
    result = await db.execute(
        select(QuotaUsageBucket)
        .where(
            QuotaUsageBucket.organization_id == org_id,
            QuotaUsageBucket.action_id == action_id,
            QuotaUsageBucket.period == period,
            QuotaUsageBucket.window_start == window_start,
        )
        .with_for_update()
    )
    return result.scalars().one()


async def lock_buckets_for_limits(
    db: AsyncSession,
    org_id: UUID,
    action_id: UUID,
    limits: list[tuple[str, int]],
    at: datetime | None = None,
) -> list[tuple[QuotaUsageBucket, int]]:
    """
    Lock buckets in deterministic (period, window_start) order.
    Returns [(bucket, limit_value), ...].
    """
    now = at or naive_utc_now()
    specs: list[tuple[str, datetime, int]] = []
    for period, limit_value in limits:
        specs.append((period, window_start_for_period(period, now), limit_value))
    specs.sort(key=lambda s: (s[0], s[1]))

    out: list[tuple[QuotaUsageBucket, int]] = []
    for period, window_start, limit_value in specs:
        bucket = await get_or_create_bucket(db, org_id, action_id, period, window_start)
        out.append((bucket, limit_value))
    return out


def check_capacity(
    locked: list[tuple[QuotaUsageBucket, int]], units: int
) -> tuple[str, int, int] | None:
    """
    Return (period, current_usage, limit) if any period would exceed, else None.
    current_usage = used + reserved.
    """
    for bucket, limit_value in locked:
        current = int(bucket.used_units) + int(bucket.reserved_units)
        if current + units > limit_value:
            return bucket.period, current, limit_value
    return None


async def apply_used_units(
    locked: list[tuple[QuotaUsageBucket, int]], units: int
) -> None:
    now = naive_utc_now()
    for bucket, _ in locked:
        bucket.used_units = int(bucket.used_units) + units
        bucket.updated_at = now


async def apply_reserved_units(
    db: AsyncSession,
    reservation_id: UUID,
    locked: list[tuple[QuotaUsageBucket, int]],
    units: int,
) -> None:
    now = naive_utc_now()
    for bucket, _ in locked:
        bucket.reserved_units = int(bucket.reserved_units) + units
        bucket.updated_at = now
        db.add(
            QuotaReservationAllocation(
                id=uuid4(),
                reservation_id=reservation_id,
                bucket_id=bucket.id,
                units=units,
                created_at=now,
            )
        )


async def release_reserved_and_consume(
    db: AsyncSession,
    reservation: QuotaCheckRequest,
    actual_units: int,
) -> None:
    """
    On commit: release reserved capacity and increment used by actual_units.
    Locks allocation buckets in deterministic order.
    """
    result = await db.execute(
        select(QuotaReservationAllocation)
        .where(QuotaReservationAllocation.reservation_id == reservation.id)
        .order_by(QuotaReservationAllocation.bucket_id)
        .with_for_update()
    )
    allocations = list(result.scalars().all())
    if not allocations:
        return

    bucket_ids = [a.bucket_id for a in allocations]
    buckets_result = await db.execute(
        select(QuotaUsageBucket)
        .where(QuotaUsageBucket.id.in_(bucket_ids))
        .order_by(QuotaUsageBucket.id)
        .with_for_update()
    )
    buckets = {b.id: b for b in buckets_result.scalars().all()}
    now = naive_utc_now()
    for alloc in allocations:
        bucket = buckets[alloc.bucket_id]
        reserved = int(alloc.units)
        bucket.reserved_units = max(0, int(bucket.reserved_units) - reserved)
        bucket.used_units = int(bucket.used_units) + actual_units
        bucket.updated_at = now
        await db.delete(alloc)


async def release_reserved_only(
    db: AsyncSession,
    reservation: QuotaCheckRequest,
) -> None:
    """On rollback/expire: release reserved capacity without consuming used_units."""
    result = await db.execute(
        select(QuotaReservationAllocation)
        .where(QuotaReservationAllocation.reservation_id == reservation.id)
        .order_by(QuotaReservationAllocation.bucket_id)
        .with_for_update()
    )
    allocations = list(result.scalars().all())
    if not allocations:
        return

    bucket_ids = [a.bucket_id for a in allocations]
    buckets_result = await db.execute(
        select(QuotaUsageBucket)
        .where(QuotaUsageBucket.id.in_(bucket_ids))
        .order_by(QuotaUsageBucket.id)
        .with_for_update()
    )
    buckets = {b.id: b for b in buckets_result.scalars().all()}
    now = naive_utc_now()
    for alloc in allocations:
        bucket = buckets[alloc.bucket_id]
        reserved = int(alloc.units)
        bucket.reserved_units = max(0, int(bucket.reserved_units) - reserved)
        bucket.updated_at = now
        await db.delete(alloc)


async def claim_request(
    db: AsyncSession,
    *,
    org_id: UUID,
    request_id: str,
    operation: str,
    fingerprint: str,
    allowed: bool = False,
    reason: str | None = None,
    action_id: UUID | None = None,
    member_id: UUID | None = None,
) -> tuple[QuotaCheckRequest, bool]:
    """
    Claim a request row as pending.

    Returns (row, created). If created is False, caller must treat as idempotent
    retry / conflict against the existing durable row.
    """
    now = naive_utc_now()
    insert = text(
        """
        INSERT INTO quota_check_requests (
            id, organization_id, action_id, member_id, request_id, operation,
            request_fingerprint, status, allowed, reason, created_at, updated_at
        ) VALUES (
            :id, :organization_id, :action_id, :member_id, :request_id, :operation,
            :request_fingerprint, :status, :allowed, :reason, :created_at, :updated_at
        )
        ON CONFLICT (organization_id, request_id) DO NOTHING
        RETURNING id
        """
    )
    row_id = uuid4()
    result = await db.execute(
        insert,
        {
            "id": row_id,
            "organization_id": org_id,
            "action_id": action_id,
            "member_id": member_id,
            "request_id": request_id,
            "operation": operation,
            "request_fingerprint": fingerprint,
            "status": QUOTA_STATUS_PENDING,
            "allowed": allowed,
            "reason": reason,
            "created_at": now,
            "updated_at": now,
        },
    )
    returned = result.first()
    if returned is not None:
        claimed = await db.execute(
            select(QuotaCheckRequest)
            .where(QuotaCheckRequest.id == row_id)
            .with_for_update()
        )
        return claimed.scalars().one(), True

    existing = await db.execute(
        select(QuotaCheckRequest)
        .where(
            and_(
                QuotaCheckRequest.organization_id == org_id,
                QuotaCheckRequest.request_id == request_id,
            )
        )
        .with_for_update()
    )
    row = existing.scalars().one()
    return row, False


async def get_reservation_for_update(
    db: AsyncSession, org_id: UUID, request_id: str
) -> QuotaCheckRequest | None:
    result = await db.execute(
        select(QuotaCheckRequest)
        .where(
            and_(
                QuotaCheckRequest.organization_id == org_id,
                QuotaCheckRequest.request_id == request_id,
            )
        )
        .with_for_update()
    )
    return result.scalars().one_or_none()


def assert_fingerprint(row: QuotaCheckRequest, fingerprint: str) -> None:
    if row.request_fingerprint and row.request_fingerprint != fingerprint:
        raise QuotaConflictError(
            "request_id already used with a different payload",
            code="idempotency_key_reuse_mismatch",
        )
