"""Organization model – name, slug, status, tier."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active", index=True)
    tier: Mapped[str] = mapped_column(String, nullable=False, default="starter")
    prepaid_balance_cents: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    held_balance_cents: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    billing_mode: Mapped[str] = mapped_column(String, nullable=False, default="postpay")
    overdraft_limit_cents: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    organization_members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember", back_populates="organization", cascade="all, delete-orphan"
    )
    organization_quota_limits: Mapped[list["OrganizationQuotaLimit"]] = relationship(
        "OrganizationQuotaLimit", back_populates="organization", cascade="all, delete-orphan"
    )
    organization_usage_lifetime: Mapped[list["OrganizationUsageLifetime"]] = relationship(
        "OrganizationUsageLifetime", back_populates="organization", cascade="all, delete-orphan"
    )
    organization_subscriptions: Mapped[list["OrganizationSubscription"]] = relationship(
        "OrganizationSubscription", back_populates="organization", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="organization", cascade="all, delete-orphan"
    )
    entitlements: Mapped[list["OrganizationEntitlement"]] = relationship(
        "OrganizationEntitlement", back_populates="organization", cascade="all, delete-orphan"
    )
