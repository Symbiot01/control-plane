"""QuotaActionPrice model – per-action pricing in cents per compute unit."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuotaActionPrice(Base):
    __tablename__ = "quota_action_prices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    action_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quota_actions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rate_cents_per_compute_unit: Mapped[int] = mapped_column(BigInteger, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    action: Mapped["QuotaAction"] = relationship("QuotaAction", back_populates="prices")

