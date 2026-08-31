"""OrganizationEntitlement model – dedicated entitlements table with expiry and limits."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrganizationEntitlement(Base):
    __tablename__ = "organization_entitlements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    max_compute_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="entitlements")
    product: Mapped["Product"] = relationship("Product")

    @property
    def product_key(self) -> str:
        return self.product.product_key if self.product else ""

    @property
    def product_name(self) -> str:
        return self.product.name if self.product else ""

    @property
    def is_active(self) -> bool:
        return self.product.is_active if self.product else False
