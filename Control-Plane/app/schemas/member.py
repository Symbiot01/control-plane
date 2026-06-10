"""Member-related Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.organization import OrganizationWithRole


class MemberProfile(BaseModel):
    """Response for GET /members/me."""

    id: UUID
    email: str
    display_name: str | None
    is_active: bool
    created_at: datetime
    organization: OrganizationWithRole | None = None

    model_config = {"from_attributes": True}
