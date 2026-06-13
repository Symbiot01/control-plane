"""Record usage to usage_ledger for billing aggregation."""

import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_ledger import UsageLedger


async def record_usage(
    db: AsyncSession,
    organization_id: UUID,
    action_id: UUID,
    units: int,
    unit_type: str,
    compute_units: int,
    cost_cents: int,
    member_id: UUID | None = None,
    request_id: str | None = None,
) -> None:
    """Insert one row into usage_ledger. Call after quota check allows."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = UsageLedger(
        id=uuid.uuid4(),
        organization_id=organization_id,
        member_id=member_id,
        action_id=action_id,
        units=units,
        unit_type=unit_type,
        compute_units=compute_units,
        cost_cents=cost_cents,
        request_id=request_id,
        created_at=now,
    )
    db.add(row)
    await db.flush()
