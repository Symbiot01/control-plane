"""UsageLedger model – per-event usage for billing."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UsageLedger(Base):
    __tablename__ = "usage_ledger"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    action_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("quota_actions.id", ondelete="SET NULL"), nullable=True
    )
    units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_type: Mapped[str] = mapped_column(String, nullable=False)
    compute_units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
