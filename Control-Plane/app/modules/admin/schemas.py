"""Admin-specific request/response Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.constants import ORG_STATUSES
from app.schemas.organization import EntitlementResponse


class AdminOrgResponse(BaseModel):
    """Organization with admin-only fields and members_count."""

    id: UUID
    name: str
    slug: str
    status: str
    tier: str
    prepaid_balance_cents: int
    billing_mode: str
    overdraft_limit_cents: int
    members_count: int
    entitlements: list["EntitlementResponse"] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminOrgCreate(BaseModel):
    """Create organization (admin)."""

    name: str = Field(..., min_length=1)
    slug: str | None = None
    owner_email: str = Field(..., description="Email of the user to assign as owner")


class AdminOrgUpdate(BaseModel):
    """Partial update for organization (admin)."""

    status: str | None = Field(None, description=f"One of {', '.join(ORG_STATUSES)}")
    tier: str | None = None
    billing_mode: str | None = None
    overdraft_limit_cents: int | None = Field(None, ge=0)


class AdminOrgListParams(BaseModel):
    """Query params for listing organizations."""

    status: str | None = None
    search: str | None = None
    offset: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=200)


# --- Credits ---


class CreditGrantRequest(BaseModel):
    """Request to grant/top-up credits to an org."""

    amount_cents: int = Field(..., gt=0)
    type: str = Field("grant", description="e.g. grant, top_up")
    reference_id: str | None = None


class CreditLedgerEntry(BaseModel):
    """Single credit_ledger row."""

    id: UUID
    amount_cents: int
    type: str
    reference_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditBalanceResponse(BaseModel):
    """Current balance and recent ledger."""

    balance_cents: int
    billing_mode: str
    overdraft_limit_cents: int
    recent_ledger: list[CreditLedgerEntry]


# --- Invoices ---


class InvoiceGenerateRequest(BaseModel):
    """Request to generate an invoice ending at billing_period_end.

    Start is derived by backend:
    - latest invoice end for the org, else
    - subscription.billing_cycle_start
    """

    billing_period_end: datetime


class InvoicePaymentUpdate(BaseModel):
    """Record payment on an invoice."""

    amount_paid_cents: int | None = Field(None, ge=0)
    credits_applied_cents: int | None = Field(None, ge=0)


# Admin invoice detail (includes credits_applied_cents, amount_paid_cents; reuse InvoiceLineItemResponse from billing)
class AdminInvoiceLineItemResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    action_id: UUID
    units: int
    compute_units: int
    amount: int

    model_config = {"from_attributes": True}


class AdminInvoiceResponse(BaseModel):
    """Invoice detail for admin (includes payment fields)."""

    id: UUID
    organization_id: UUID
    billing_period_start: datetime
    billing_period_end: datetime
    total_compute_units: int
    included_units: int
    overage_units: int
    amount_due: int
    credits_applied_cents: int
    amount_paid_cents: int
    status: str
    external_id: str | None
    created_at: datetime
    line_items: list[AdminInvoiceLineItemResponse] | None = None

    model_config = {"from_attributes": True}


# --- Super admins ---


class SuperAdminResponse(BaseModel):
    """Super admin list item."""

    member_id: UUID
    email: str
    display_name: str | None
    created_at: datetime


class SuperAdminCreate(BaseModel):
    """Add super admin by email."""

    email: str = Field(..., description="Member email (must exist)")


# --- Audit log ---


class AdminAuditLogResponse(BaseModel):
    """Single admin audit log entry."""

    id: UUID
    admin_member_id: UUID
    action: str
    target_type: str
    target_id: UUID | None
    detail: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminAuditLogParams(BaseModel):
    """Query params for audit log list."""

    action: str | None = None
    target_type: str | None = None
    target_id: UUID | None = None
    offset: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=200)


# --- Products ---


class ProductResponse(BaseModel):
    """A formal product."""

    id: UUID
    name: str
    product_key: str
    description: str | None
    deliverable_id: UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeliverableResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    deliverable_link: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeliverableCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    deliverable_link: str | None = None


class DeliverableUpdate(BaseModel):
    name: str | None = Field(None, min_length=1)
    description: str | None = None
    deliverable_link: str | None = None


class ProductCreate(BaseModel):
    """Create a new product."""

    name: str = Field(..., min_length=1)
    product_key: str = Field(..., min_length=1)
    description: str | None = None
    deliverable_id: UUID | None = None


class ProductUpdate(BaseModel):
    """Update an existing product."""

    name: str | None = Field(None, min_length=1)
    description: str | None = None
    deliverable_id: UUID | None = None
    is_active: bool | None = None


class EntitlementGrantRequest(BaseModel):
    """Grant an entitlement to an org."""

    product_key: str = Field(..., min_length=1)
    expires_at: datetime | None = None
    max_compute_units: int | None = Field(None, ge=0)


# --- Dashboard stats ---


class AdminStatsResponse(BaseModel):
    """Dashboard counters for admin UI."""

    total_orgs: int
    active_orgs: int
    suspended_orgs: int
    archived_orgs: int
    active_subscriptions: int
    draft_invoices: int
    overdue_invoices: int
    total_members: int


# --- Subscription change plan ---


class SubscriptionChangePlanRequest(BaseModel):
    """Request body for POST /subscriptions/{sub_id}/change-plan."""

    new_plan_id: UUID
    new_billing_cycle_start: datetime
    new_billing_cycle_end: datetime


class SubscriptionStatusUpdate(BaseModel):
    """Request body for PATCH /subscriptions/{sub_id}/status."""

    status: str


# --- Plan update (admin) ---


class PlanUpdate(BaseModel):
    """Partial update for plan (admin)."""

    name: str | None = Field(None, min_length=1)
    monthly_price: int | None = Field(None, ge=0)
    included_compute_units: int | None = Field(None, ge=0)
    overage_rate: int | None = Field(None, ge=0)
    currency: str | None = Field(None, min_length=1)


# --- Quota actions (admin) ---


class AdminActionResponse(BaseModel):
    """Global quota action registry item."""

    id: UUID
    action_key: str
    domain: str
    unit_type: str
    description: str | None
    is_active: bool
    product_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminActionCreate(BaseModel):
    """Create one quota action and optionally set default pricing."""

    action_key: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    unit_type: str = Field(..., min_length=1)
    description: str | None = None
    product_id: UUID | None = None
    default_rate_cents_per_compute_unit: int = Field(1, ge=0)


class AdminActionUpdate(BaseModel):
    """Partial action update (currently supports soft-enable/disable + metadata + pricing)."""

    domain: str | None = Field(None, min_length=1)
    unit_type: str | None = Field(None, min_length=1)
    description: str | None = None
    is_active: bool | None = None
    product_id: UUID | None = None
    rate_cents_per_compute_unit: int | None = Field(None, ge=0)


# --- Global Members ---


class GlobalMemberResponse(BaseModel):
    """Global member response for super admin."""

    member_id: UUID
    email: str
    display_name: str | None
    organization_id: UUID | None
    global_role: str
    created_at: datetime


class GlobalMemberRoleUpdate(BaseModel):
    """Update org role (owner, member, or viewer)."""

    role: str = Field(..., description="Must be 'owner', 'member', or 'viewer'")
    organization_id: UUID | None = Field(None, description="Provide to assign a guest to an organization")
