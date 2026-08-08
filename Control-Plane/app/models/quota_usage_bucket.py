"""PostgreSQL-authoritative quota usage and reservation capacity buckets."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.quota_check_request import QuotaCheckRequest


class QuotaUsageBucket(Base):
    """
    Authoritative usage counter for one org/action/period window.

    used_units: consumed (check allow or commit)
    reserved_units: capacity held by active reservations (status=held)
    Capacity check: used_units + reserved_units + delta <= limit_value
    """

    __tablename__ = "quota_usage_buckets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "action_id",
            "period",
            "window_start",
            name="uq_quota_usage_buckets_org_action_period_window",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quota_actions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period: Mapped[str] = mapped_column(String, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_units: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reserved_units: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    allocations: Mapped[list[QuotaReservationAllocation]] = relationship(
        "QuotaReservationAllocation",
        back_populates="bucket",
        cascade="all, delete-orphan",
    )


class QuotaReservationAllocation(Base):
    """Links a held reservation to the exact bucket capacity it reserved."""

    __tablename__ = "quota_reservation_allocations"
    __table_args__ = (
        UniqueConstraint(
            "reservation_id",
            "bucket_id",
            name="uq_quota_reservation_allocations_res_bucket",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reservation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quota_check_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bucket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quota_usage_buckets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    units: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    reservation: Mapped[QuotaCheckRequest] = relationship(
        "QuotaCheckRequest", back_populates="allocations"
    )
    bucket: Mapped[QuotaUsageBucket] = relationship(
        "QuotaUsageBucket", back_populates="allocations"
    )
