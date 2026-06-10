"""Quota-related Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class QuotaLimitResponse(BaseModel):
    """Single org quota limit (action + period + value)."""

    id: UUID
    organization_id: UUID
    action_id: UUID
    action_key: str | None = None  # Optional, from join
    limit_value: int
    period: str
    created_at: datetime

    model_config = {"from_attributes": True}


class QuotaLimitsUpdate(BaseModel):
    """Request body for PATCH /quotas/:org_id – set or update limits."""

    action_id: UUID = Field(..., description="Quota action ID")
    period: str = Field(..., description="per_minute, per_hour, per_day, per_month, lifetime")
    limit_value: int = Field(..., ge=0, description="Limit value")
