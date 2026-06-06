"""Invoice model – billing period and amount due."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    billing_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    billing_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_compute_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    included_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    overage_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_due: Mapped[int] = mapped_column(BigInteger, nullable=False)
    credits_applied_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    amount_paid_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="invoices")
    line_items: Mapped[list["InvoiceLineItem"]] = relationship(
        "InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan"
    )
