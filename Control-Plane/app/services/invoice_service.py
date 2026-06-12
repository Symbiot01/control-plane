"""Invoice generation from usage_ledger and subscription/plan."""

import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _naive_utc(dt: datetime) -> datetime:
    """Ensure datetime is naive UTC for TIMESTAMP WITHOUT TIME ZONE."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


from app.core.constants import INVOICE_STATUS_DRAFT
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.organization_subscription import OrganizationSubscription
from app.models.usage_ledger import UsageLedger
from app.services.subscription_service import get_current_subscription


async def generate_invoice_for_org(
    db: AsyncSession,
    organization_id: UUID,
    billing_period_end: datetime,
) -> UUID:
    """
    Aggregate usage_ledger for org in [start, end), resolve plan from subscription,
    compute amount_due, create Invoice and InvoiceLineItems. Returns invoice id.
    Start is derived by backend:
    - latest existing invoice.billing_period_end for the org, else
    - active subscription.billing_cycle_start.
    Idempotent: if an invoice already exists for same org and derived period, returns its id.
    Rejects overlapping periods.
    """
    end = _naive_utc(billing_period_end)
    # Latest invoice determines next period start if invoice history exists.
    latest_result = await db.execute(
        select(Invoice)
        .where(Invoice.organization_id == organization_id)
        .order_by(Invoice.billing_period_end.desc())
        .limit(1)
    )
    latest = latest_result.scalars().one_or_none()
    if latest is not None:
        start = latest.billing_period_end
    else:
        # First invoice starts at active subscription start.
        sub_for_start = await get_current_subscription(db, organization_id, at=end)
        if sub_for_start is None:
            raise ValueError("No active subscription for this organization in the billing period")
        start = _naive_utc(sub_for_start.billing_cycle_start)

    if end <= start:
        raise ValueError("billing_period_end must be greater than derived billing_period_start")

    # Idempotency: existing invoice for same org and period
    existing = await db.execute(
        select(Invoice).where(
            Invoice.organization_id == organization_id,
            Invoice.billing_period_start == start,
            Invoice.billing_period_end == end,
        )
    )
    inv = existing.scalars().one_or_none()
    if inv is not None:
        return inv.id

    # Guard against overlapping windows to avoid double billing.
    overlap = await db.execute(
        select(Invoice).where(
            Invoice.organization_id == organization_id,
            Invoice.billing_period_start < end,
            Invoice.billing_period_end > start,
        )
    )
    if overlap.scalars().first() is not None:
        raise ValueError("Invoice period overlaps existing invoice window")

    # Subscription covering this period (validate plan at period start)
    sub = await get_current_subscription(db, organization_id, at=start)
    if sub is None:
        raise ValueError("No active subscription for this organization in the billing period")
    await db.refresh(sub, ["plan"])
    plan = sub.plan
    if plan is None:
        raise ValueError("Subscription has no plan")

    # Sum usage_ledger for org in period; group by action_id
    agg = await db.execute(
        select(
            UsageLedger.action_id,
            func.sum(UsageLedger.units).label("units"),
            func.sum(UsageLedger.compute_units).label("compute_units"),
        )
        .where(
            UsageLedger.organization_id == organization_id,
            UsageLedger.created_at >= start,
            UsageLedger.created_at < end,
            UsageLedger.action_id.isnot(None),
        )
        .group_by(UsageLedger.action_id)
    )
    rows = agg.all()

    total_compute_units = sum(r.compute_units for r in rows)
    included_units = min(total_compute_units, plan.included_compute_units)
    overage_units = total_compute_units - included_units
    overage_charge = overage_units * plan.overage_rate
    amount_due = plan.monthly_price + overage_charge

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    invoice = Invoice(
        id=uuid.uuid4(),
        organization_id=organization_id,
        billing_period_start=start,
        billing_period_end=end,
        total_compute_units=total_compute_units,
        included_units=included_units,
        overage_units=overage_units,
        amount_due=amount_due,
        credits_applied_cents=0,
        amount_paid_cents=0,
        status=INVOICE_STATUS_DRAFT,
        external_id=None,
        created_at=now,
    )
    db.add(invoice)
    await db.flush()

    # Line items: one per action, amount = proportional share of overage charge
    for r in rows:
        action_compute = r.compute_units
        if total_compute_units > 0:
            line_amount = (action_compute * overage_charge) // total_compute_units
        else:
            line_amount = 0
        line = InvoiceLineItem(
            id=uuid.uuid4(),
            invoice_id=invoice.id,
            action_id=r.action_id,
            units=r.units,
            compute_units=action_compute,
            amount=line_amount,
        )
        db.add(line)
    await db.flush()
    return invoice.id


async def set_org_suspended_for_invoice(db: AsyncSession, invoice_id: UUID) -> None:
    """Set organization status to suspended (e.g. when invoice is marked overdue)."""
    from app.core.constants import ORG_STATUS_SUSPENDED
    from app.models.organization import Organization

    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    inv = result.scalars().one_or_none()
    if inv is None:
        return
    org_result = await db.execute(select(Organization).where(Organization.id == inv.organization_id))
    org = org_result.scalars().one_or_none()
    if org is not None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        org.status = ORG_STATUS_SUSPENDED
        org.updated_at = now
        await db.flush()
