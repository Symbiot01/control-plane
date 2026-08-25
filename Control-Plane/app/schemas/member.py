"""Member-related Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.organization import EntitlementResponse, OrganizationWithRole


class MemberProfile(BaseModel):
    """Response for GET /members/me."""

    id: UUID
    email: str
    display_name: str | None
    is_active: bool
    created_at: datetime
    organization: OrganizationWithRole | None = None
    entitlements: list[EntitlementResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
