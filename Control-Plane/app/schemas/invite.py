from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OrganizationInviteCreate(BaseModel):
    name: str = Field(..., description="Name of the person being invited")
    email: EmailStr = Field(..., description="Email address to invite")
    organization_id: Optional[UUID] = Field(None, description="If null, this is an org-creation invite.")
    plan_id: Optional[UUID] = Field(None, description="Pre-selected plan for org-creation invites.")
    initial_credits: Optional[int] = Field(15000, le=100000, description="Initial credits (in cents) to grant to the org upon creation.")
    role: str = Field("owner", description="Role to grant to the user.")
    expiration_hours: int = Field(72, description="How many hours until the invite expires.")


class OrganizationInviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: Optional[str] = None
    email: str
    organization_id: Optional[UUID] = None
    plan_id: Optional[UUID] = None
    initial_credits: Optional[int] = None
    role: str
    status: str
    invited_by: Optional[UUID] = None
    expires_at: datetime
    created_at: datetime
    invite_url: Optional[str] = None
    email_sent: Optional[bool] = None
    account_exists: bool = Field(default=False, description="True if a member account already exists for this email")


class OrganizationInviteAcceptRequest(BaseModel):
    organization_name: Optional[str] = Field(
        None, 
        description="Required if this is an org-creation ticket (organization_id was null)."
    )
