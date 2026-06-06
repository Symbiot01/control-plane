"""Plan model – billing plan (name, price, included/overage)."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=False)
    monthly_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    included_compute_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    overage_rate: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    organization_subscriptions: Mapped[list["OrganizationSubscription"]] = relationship(
        "OrganizationSubscription", back_populates="plan", cascade="all, delete-orphan"
    )
