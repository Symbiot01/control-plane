"""OrganizationInvite model – onboarding tickets."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrganizationInvite(Base):
    __tablename__ = "organization_invites"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # If set, the user is joining this existing organization. 
    # If NULL, this is a ticket to create a brand new organization.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    
    # If the invite is to create an org, the super admin can pre-select a plan
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL"), nullable=True
    )
    
    # Amount of credits (in cents) to grant to the org upon creation
    initial_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    role: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", index=True)
    
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
