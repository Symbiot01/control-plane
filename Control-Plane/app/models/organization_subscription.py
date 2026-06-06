"""OrganizationSubscription model – org subscription to a plan."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrganizationSubscription(Base):
    __tablename__ = "organization_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    billing_cycle_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    billing_cycle_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="organization_subscriptions"
    )
    plan: Mapped["Plan"] = relationship("Plan", back_populates="organization_subscriptions")
