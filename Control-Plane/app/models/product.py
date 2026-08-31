"""Product model – name, product_key, description."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    product_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    deliverable_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("deliverables.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    actions: Mapped[list["QuotaAction"]] = relationship(
        "QuotaAction", back_populates="product", cascade="all, delete-orphan"
    )
    deliverable: Mapped["Deliverable | None"] = relationship("Deliverable", back_populates="products")
