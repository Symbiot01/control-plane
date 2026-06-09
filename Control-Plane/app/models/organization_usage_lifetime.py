"""OrganizationUsageLifetime model – persistent lifetime usage per org/action."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrganizationUsageLifetime(Base):
    __tablename__ = "organization_usage_lifetime"
    __table_args__ = (
        UniqueConstraint("organization_id", "action_id", name="uq_organization_usage_lifetime_org_action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quota_actions.id", ondelete="CASCADE"), nullable=False
    )
    used_units: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="organization_usage_lifetime"
    )
    action: Mapped["QuotaAction"] = relationship(
        "QuotaAction", back_populates="organization_usage_lifetime"
    )
