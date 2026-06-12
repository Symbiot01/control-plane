"""Pricing service – resolve per-action rates in cents per compute unit."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quota_action import QuotaAction
from app.models.quota_action_price import QuotaActionPrice


def _naive_utc(dt: datetime) -> datetime:
    """Ensure datetime is naive UTC for TIMESTAMP WITHOUT TIME ZONE."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


async def get_rate_cents_per_compute_unit(
    db: AsyncSession,
    action_id: UUID,
    at: datetime | None = None,
) -> int:
    """
    Return the effective rate_cents_per_compute_unit for an action at time `at`.

    Strategy:
    - Pick the QuotaActionPrice row with latest effective_from <= at.
    - If none exists, raise ValueError so callers can decide how to handle.
    """
    if at is None:
        at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        at = _naive_utc(at)

    result = await db.execute(
        select(QuotaActionPrice)
        .where(
            QuotaActionPrice.action_id == action_id,
            QuotaActionPrice.effective_from <= at,
        )
        .order_by(QuotaActionPrice.effective_from.desc())
        .limit(1)
    )
    price = result.scalars().one_or_none()
    if price is None:
        raise ValueError(f"No pricing configured for action_id={action_id}")
    return int(price.rate_cents_per_compute_unit)


async def get_rate_for_action_key(
    db: AsyncSession,
    action_key: str,
    at: datetime | None = None,
) -> int:
    """
    Convenience helper: resolve rate for a given action_key.

    Looks up QuotaAction by action_key, then delegates to get_rate_cents_per_compute_unit.
    """
    result = await db.execute(select(QuotaAction).where(QuotaAction.action_key == action_key))
    action = result.scalars().one_or_none()
    if action is None:
        raise ValueError(f"Unknown action_key={action_key}")
    return await get_rate_cents_per_compute_unit(db, action.id, at=at)

