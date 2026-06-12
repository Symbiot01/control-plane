"""Subscription lifecycle: create, get current, update status, change plan."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    SUBSCRIPTION_STATUS_ACTIVE,
    SUBSCRIPTION_STATUS_CANCELED,
)
from app.models.organization import Organization
from app.models.organization_subscription import OrganizationSubscription
from app.models.plan import Plan


def _naive_utc(dt: datetime) -> datetime:
    """Ensure datetime is naive UTC for TIMESTAMP WITHOUT TIME ZONE."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


async def create_subscription(
    db: AsyncSession,
    organization_id: UUID,
    plan_id: UUID,
    billing_cycle_start: datetime,
    billing_cycle_end: datetime,
) -> OrganizationSubscription:
    """Create an active subscription for the org. Validates org and plan exist. Optionally skips if overlapping active exists."""
    start = _naive_utc(billing_cycle_start)
    end = _naive_utc(billing_cycle_end)
    # Validate org exists
    org = (await db.execute(select(Organization).where(Organization.id == organization_id))).scalars().one_or_none()
    if org is None:
        raise ValueError("Organization not found")
    # Validate plan exists
    plan = (await db.execute(select(Plan).where(Plan.id == plan_id))).scalars().one_or_none()
    if plan is None:
        raise ValueError("Plan not found")
    # Optional: no overlapping active subscription
    overlap = await db.execute(
        select(OrganizationSubscription).where(
            OrganizationSubscription.organization_id == organization_id,
            OrganizationSubscription.status == SUBSCRIPTION_STATUS_ACTIVE,
            OrganizationSubscription.billing_cycle_start < end,
            OrganizationSubscription.billing_cycle_end > start,
        )
    )
    if overlap.scalars().first() is not None:
        raise ValueError("Organization already has an active subscription for this period")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sub = OrganizationSubscription(
        id=uuid4(),
        organization_id=organization_id,
        plan_id=plan_id,
        status=SUBSCRIPTION_STATUS_ACTIVE,
        billing_cycle_start=start,
        billing_cycle_end=end,
        created_at=now,
    )
    db.add(sub)
    await db.flush()
    await db.refresh(sub)
    return sub


async def get_current_subscription(
    db: AsyncSession,
    organization_id: UUID,
    at: datetime | None = None,
) -> OrganizationSubscription | None:
    """Return the active subscription for org whose billing window contains `at` (default now), or latest active."""
    if at is None:
        at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        at = _naive_utc(at)
    # Prefer subscription that contains `at`
    result = await db.execute(
        select(OrganizationSubscription)
        .where(
            OrganizationSubscription.organization_id == organization_id,
            OrganizationSubscription.status == SUBSCRIPTION_STATUS_ACTIVE,
            OrganizationSubscription.billing_cycle_start <= at,
            OrganizationSubscription.billing_cycle_end > at,
        )
        .order_by(OrganizationSubscription.billing_cycle_end.desc())
        .limit(1)
    )
    row = result.scalars().one_or_none()
    if row is not None:
        return row
    # Else latest active by end date
    result = await db.execute(
        select(OrganizationSubscription)
        .where(
            OrganizationSubscription.organization_id == organization_id,
            OrganizationSubscription.status == SUBSCRIPTION_STATUS_ACTIVE,
        )
        .order_by(OrganizationSubscription.billing_cycle_end.desc())
        .limit(1)
    )
    return result.scalars().one_or_none()


async def update_subscription_status(
    db: AsyncSession,
    subscription_id: UUID,
    status: str,
) -> OrganizationSubscription | None:
    """Set subscription status (e.g. canceled, past_due). Returns updated row or None if not found."""
    result = await db.execute(
        select(OrganizationSubscription).where(OrganizationSubscription.id == subscription_id)
    )
    sub = result.scalars().one_or_none()
    if sub is None:
        return None
    sub.status = status
    await db.flush()
    await db.refresh(sub)
    return sub


async def change_plan(
    db: AsyncSession,
    subscription_id: UUID,
    new_plan_id: UUID,
    new_billing_cycle_start: datetime,
    new_billing_cycle_end: datetime,
) -> OrganizationSubscription:
    """End current subscription (set to canceled) and create a new subscription for the new plan/period."""
    result = await db.execute(
        select(OrganizationSubscription).where(OrganizationSubscription.id == subscription_id)
    )
    current = result.scalars().one_or_none()
    if current is None:
        raise ValueError("Subscription not found")
    plan = (await db.execute(select(Plan).where(Plan.id == new_plan_id))).scalars().one_or_none()
    if plan is None:
        raise ValueError("Plan not found")
    current.status = SUBSCRIPTION_STATUS_CANCELED
    await db.flush()
    new_sub = await create_subscription(
        db,
        current.organization_id,
        new_plan_id,
        new_billing_cycle_start,
        new_billing_cycle_end,
    )
    return new_sub
