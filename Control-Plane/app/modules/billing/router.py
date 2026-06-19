"""Billing routes: read-only subscriptions, invoices, and usage summary for org members."""

from datetime import datetime
from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import INVOICE_STATUSES
from app.core.dependencies import require_org_member_for_path
from app.db.session import get_db
from app.models.invoice import Invoice
from app.models.organization_member import OrganizationMember
from app.schemas.billing import (
    InvoiceLineItemResponse,
    InvoiceResponse,
    InvoiceSummaryResponse,
    PlanResponse,
    SubscriptionResponse,
)
from app.schemas.usage import UsageSummaryResponse
from app.services.subscription_service import (
    get_current_subscription as get_current_subscription_svc,
)
from app.services.usage_summary_service import (
    resolve_usage_period,
    summarize_usage_for_org,
)

router = APIRouter(prefix="/organizations/{org_id}", tags=["billing"])


@router.get("/subscriptions/current", response_model=SubscriptionResponse | None)
async def get_subscription_current(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _membership: Annotated[OrganizationMember, Depends(require_org_member_for_path)],
):
    """Get current active subscription for the org. JWT org must match path org_id."""
    sub = await get_current_subscription_svc(db, org_id)
    if sub is None:
        return None
    await db.refresh(sub, ["plan"])
    return SubscriptionResponse(
        id=sub.id,
        organization_id=sub.organization_id,
        plan_id=sub.plan_id,
        status=sub.status,
        billing_cycle_start=sub.billing_cycle_start,
        billing_cycle_end=sub.billing_cycle_end,
        created_at=sub.created_at,
        plan=PlanResponse.model_validate(sub.plan) if sub.plan else None,
    )


@router.get("/usage/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _membership: Annotated[OrganizationMember, Depends(require_org_member_for_path)],
    from_dt: datetime | None = Query(None, alias="from", description="Period start (UTC); use with to"),
    to_dt: datetime | None = Query(None, alias="to", description="Period end (exclusive, UTC); use with from"),
):
    """Aggregated usage from usage_ledger for [from, to). Defaults to last 30 days when both omitted."""
    try:
        period_start, period_end = resolve_usage_period(from_dt, to_dt)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return await summarize_usage_for_org(db, org_id, period_start, period_end)


# ---- Invoices (under same org prefix) ----

@router.get("/invoices", response_model=list[InvoiceSummaryResponse])
async def list_invoices(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _membership: Annotated[OrganizationMember, Depends(require_org_member_for_path)],
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
):
    """List invoices for the org. JWT org must match path org_id."""
    q = select(Invoice).where(Invoice.organization_id == org_id).order_by(Invoice.created_at.desc()).limit(limit)
    if status_filter and status_filter in INVOICE_STATUSES:
        q = q.where(Invoice.status == status_filter)
    result = await db.execute(q)
    invoices = result.scalars().all()
    return [InvoiceSummaryResponse.model_validate(inv) for inv in invoices]


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    org_id: UUID,
    invoice_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _membership: Annotated[OrganizationMember, Depends(require_org_member_for_path)],
):
    """Get invoice detail with line items. Invoice must belong to org."""
    result = await db.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.organization_id == org_id,
        )
    )
    inv = result.scalars().one_or_none()
    if inv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    await db.refresh(inv, ["line_items"])
    return InvoiceResponse(
        id=inv.id,
        organization_id=inv.organization_id,
        billing_period_start=inv.billing_period_start,
        billing_period_end=inv.billing_period_end,
        total_compute_units=inv.total_compute_units,
        included_units=inv.included_units,
        overage_units=inv.overage_units,
        amount_due=inv.amount_due,
        status=inv.status,
        external_id=inv.external_id,
        created_at=inv.created_at,
        line_items=[InvoiceLineItemResponse.model_validate(li) for li in inv.line_items] if inv.line_items else [],
    )
