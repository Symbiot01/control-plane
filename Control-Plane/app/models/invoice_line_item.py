"""InvoiceLineItem model – per-action line on an invoice."""

import uuid

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quota_actions.id", ondelete="RESTRICT"), nullable=False
    )
    units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compute_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="line_items")
    action: Mapped["QuotaAction"] = relationship("QuotaAction")
