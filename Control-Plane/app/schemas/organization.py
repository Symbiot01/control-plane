"""Organization-related Pydantic schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.constants import ROLE_MEMBER, ROLE_OWNER, ROLE_VIEWER

OrgRoleLiteral = Literal["owner", "member", "viewer"]


class OrganizationCreate(BaseModel):
    """Request body for POST /organizations."""

    name: str = Field(..., min_length=1)
    slug: str | None = Field(None, description="Optional; derived from name if not set")


class OrganizationUpdate(BaseModel):
    """Request body for PATCH /organizations/:id."""

    name: str | None = Field(None, min_length=1)


class EntitlementResponse(BaseModel):
    product_key: str
    product_name: str | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None
    max_compute_units: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationProductResponse(BaseModel):
    product_key: str
    name: str
    description: str | None
    is_active: bool
    expires_at: datetime | None
    max_compute_units: int | None


class OrganizationDeliverableResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    deliverable_link: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationProductAccessResponse(BaseModel):
    has_access: bool
    reason: str = Field(..., description="Explanation of the access state")
    expires_at: datetime | None = None


class OrganizationResponse(BaseModel):
    """Organization in API responses."""

    id: UUID
    name: str
    slug: str
    status: str
    tier: str
    prepaid_balance_cents: int
    entitlements: list[EntitlementResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationWithRole(OrganizationResponse):
    """Organization plus current member's role."""

    role: str


class InviteMemberRequest(BaseModel):
    """Request body for POST /organizations/:id/invite."""

    name: str = Field(..., description="Name of the person being invited")
    email: str = Field(..., description="Email address to invite")
    role: OrgRoleLiteral = Field(
        ...,
        description=f"Role to assign ({ROLE_OWNER}, {ROLE_MEMBER}, or {ROLE_VIEWER})",
    )
    expiration_hours: int = Field(72, description="How many hours until the invite expires.")


class UpdateMemberRoleRequest(BaseModel):
    """Request body for PATCH /organizations/:id/member/:member_id."""

    role: OrgRoleLiteral = Field(
        ...,
        description=f"New role ({ROLE_OWNER}, {ROLE_MEMBER}, or {ROLE_VIEWER})",
    )


class OrganizationMemberResponse(BaseModel):
    """Response for GET /organizations/:id/members."""

    id: UUID
    email: str
    display_name: str | None
    role: str
    created_at: datetime


class PendingInviteResponse(BaseModel):
    """Response for GET /organizations/:id/invites."""

    id: UUID
    email: str
    role: str
    status: str
    invited_by: UUID | None
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    """Response for GET /organizations/:id/audit-logs."""

    id: UUID
    action_key: str | None
    result: str | None
    member_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}

