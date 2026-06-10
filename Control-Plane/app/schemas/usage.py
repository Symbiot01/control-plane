"""Usage summary schemas (aggregates from usage_ledger)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UsageActionBreakdown(BaseModel):
    """Per-action_id totals in a period."""

    action_id: UUID | None = Field(None, description="Null for legacy rows without action_id")
    action_key: str | None = None
    units: int
    compute_units: int


class UsageSummaryResponse(BaseModel):
    """Aggregated usage for an organization over [period_start, period_end)."""

    organization_id: UUID
    period_start: datetime
    period_end: datetime
    total_compute_units: int
    total_units: int
    by_action: list[UsageActionBreakdown]
