"""QuotaAction model – global action registry."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuotaAction(Base):
    __tablename__ = "quota_actions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    action_key: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=False)
    domain: Mapped[str] = mapped_column(String, nullable=False, index=True)
    unit_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    product: Mapped["Product | None"] = relationship("Product", back_populates="actions")

    organization_quota_limits: Mapped[list["OrganizationQuotaLimit"]] = relationship(
        "OrganizationQuotaLimit", back_populates="action", cascade="all, delete-orphan"
    )
    organization_usage_lifetime: Mapped[list["OrganizationUsageLifetime"]] = relationship(
        "OrganizationUsageLifetime", back_populates="action", cascade="all, delete-orphan"
    )
    prices: Mapped[list["QuotaActionPrice"]] = relationship(
        "QuotaActionPrice", back_populates="action", cascade="all, delete-orphan"
    )