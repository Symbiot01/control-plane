"""QuotaCheckRequest model – idempotency and reservation state machine."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.quota_usage_bucket import QuotaReservationAllocation


class QuotaCheckRequest(Base):
    __tablename__ = "quota_check_requests"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "request_id",
            name="uq_quota_check_requests_org_request",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("quota_actions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    request_id: Mapped[str] = mapped_column(String, nullable=False)
    operation: Mapped[str] = mapped_column(String, nullable=False, default="check")
    request_fingerprint: Mapped[str] = mapped_column(String, nullable=False, default="")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    held_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    held_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    held_compute_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rate_cents_per_compute_unit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actual_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actual_compute_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actual_cost_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    allocations: Mapped[list[QuotaReservationAllocation]] = relationship(
        "QuotaReservationAllocation",
        back_populates="reservation",
        cascade="all, delete-orphan",
    )
