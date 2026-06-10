"""Billing-related Pydantic schemas: plans, subscriptions, invoices."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.constants import (
    INVOICE_STATUSES,
    SUBSCRIPTION_STATUSES,
)


class PlanResponse(BaseModel):
    id: UUID
    name: str
    monthly_price: int
    included_compute_units: int
    overage_rate: int
    currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


def _coerce_int(v: str | int | None) -> int | None:
    """Coerce string to int for JSON clients that send numbers as strings."""
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return v
    if isinstance(v, str):
        return int(v)
    return v


class PlanCreate(BaseModel):
    model_config = {"extra": "ignore", "populate_by_name": True}

    name: str = Field(..., min_length=1, alias="planName")
    monthly_price: int = Field(
        ...,
        ge=0,
        description="Base monthly price in smallest currency unit (e.g. cents)",
        alias="monthlyPrice",
    )
    included_compute_units: int = Field(..., ge=0, alias="includedComputeUnits")
    overage_rate: int = Field(
        ...,
        ge=0,
        description="Price per compute unit above included units",
        alias="overageRate",
    )
    currency: str = Field("USD", min_length=1)

    @field_validator("monthly_price", "included_compute_units", "overage_rate", mode="before")
    @classmethod
    def coerce_ints(cls, v: str | int | None) -> int:
        out = _coerce_int(v)
        if out is None:
            raise ValueError("value is required")
        return out


class SubscriptionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    plan_id: UUID
    status: str
    billing_cycle_start: datetime
    billing_cycle_end: datetime
    created_at: datetime
    plan: PlanResponse | None = None

    model_config = {"from_attributes": True}


class SubscriptionCreate(BaseModel):
    plan_id: UUID
    billing_cycle_start: datetime
    billing_cycle_end: datetime


class SubscriptionUpdate(BaseModel):
    status: str | None = Field(
        None,
        description=f"New subscription status (one of {', '.join(SUBSCRIPTION_STATUSES)})",
    )
    new_plan_id: UUID | None = Field(
        None,
        description="Optional new plan id when changing plan",
    )
    new_billing_cycle_start: datetime | None = None
    new_billing_cycle_end: datetime | None = None


class InvoiceLineItemResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    action_id: UUID
    units: int
    compute_units: int
    amount: int

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    id: UUID
    organization_id: UUID
    billing_period_start: datetime
    billing_period_end: datetime
    total_compute_units: int
    included_units: int
    overage_units: int
    amount_due: int
    status: str
    external_id: str | None = None
    created_at: datetime
    line_items: list[InvoiceLineItemResponse] | None = None

    model_config = {"from_attributes": True}


class InvoiceSummaryResponse(BaseModel):
    """
    Summary shape for invoice lists.

    Note: intentionally excludes relationship fields (e.g. line_items) so async ORM
    lazy-loading cannot be triggered during response serialization.
    """

    id: UUID
    organization_id: UUID
    billing_period_start: datetime
    billing_period_end: datetime
    total_compute_units: int
    included_units: int
    overage_units: int
    amount_due: int
    status: str
    external_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoiceStatusUpdate(BaseModel):
    status: str = Field(..., description=f"New invoice status (one of {', '.join(INVOICE_STATUSES)})")


class InvoiceListResponse(BaseModel):
    invoices: list[InvoiceResponse]

