"""OrganizationQuotaLimit model – per-org, per-action, per-period limits."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrganizationQuotaLimit(Base):
    __tablename__ = "organization_quota_limits"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "action_id", "period", name="uq_organization_quota_limits_org_action_period"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quota_actions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    limit_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    period: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="organization_quota_limits")
    action: Mapped["QuotaAction"] = relationship("QuotaAction", back_populates="organization_quota_limits")
