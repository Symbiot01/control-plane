"""Internal API request/response schemas (quota check)."""

from uuid import UUID

from pydantic import BaseModel, Field


class QuotaCheckRequest(BaseModel):
    """Request body for POST /internal/v1/quota/check."""

    organization_id: UUID = Field(..., description="Organization ID")
    action_key: str = Field(..., description="Action key (e.g. medical.case.analyze.v1)")
    units: int = Field(1, ge=1, description="Units to consume")
    member_id: UUID | None = Field(None, description="Optional member ID for usage attribution")
    request_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
        description="Required idempotency/correlation id (no PHI)",
    )
    compute_units: int | None = Field(
        None, description="Compute units for billing; defaults to units if omitted"
    )


class QuotaCheckResponse(BaseModel):
    """Response from quota check."""

    allowed: bool
    reason: str | None = None
    status: str | None = None
    request_id: str | None = None
    current_usage: int | None = None
    limit: int | None = None
    actual_cost_cents: int | None = None


class QuotaReserveRequest(BaseModel):
    """Request body for POST /internal/v1/quota/reserve."""

    organization_id: UUID = Field(..., description="Organization ID")
    action_key: str = Field(..., description="Action key (e.g. medical.chat.message.v1)")
    max_units: int = Field(1, ge=1, description="Maximum units to reserve")
    member_id: UUID | None = Field(None, description="Optional member ID for usage attribution")
    request_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
        description="Unique idempotency ID for this reservation",
    )
    compute_units: int | None = Field(
        None, description="Max compute units for billing; defaults to max_units if omitted"
    )


class QuotaReserveResponse(BaseModel):
    """Response from quota reserve."""

    allowed: bool
    reason: str | None = None
    status: str | None = None
    request_id: str | None = None
    expires_at: str | None = None
    current_usage: int | None = None
    limit: int | None = None


class QuotaCommitRequest(BaseModel):
    """Request body for POST /internal/v1/quota/commit."""

    organization_id: UUID = Field(..., description="Organization ID")
    request_id: str = Field(..., description="Idempotency ID used in the reserve call")
    actual_units: int = Field(0, ge=0, description="Actual units consumed")
    compute_units: int | None = Field(
        None, description="Actual compute units for billing; defaults to actual_units"
    )


class QuotaCommitResponse(BaseModel):
    """Response from quota commit."""

    status: str
    request_id: str | None = None
    allowed: bool | None = None
    reason: str | None = None
    actual_cost_cents: int | None = None


class QuotaRollbackRequest(BaseModel):
    """Request body for POST /internal/v1/quota/rollback."""

    organization_id: UUID = Field(..., description="Organization ID")
    request_id: str = Field(..., description="Idempotency ID used in the reserve call")


class QuotaRollbackResponse(BaseModel):
    """Response from quota rollback."""

    status: str
    request_id: str | None = None
    allowed: bool | None = None
    reason: str | None = None
