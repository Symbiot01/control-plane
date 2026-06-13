"""Aggregate usage_ledger for org usage summary API."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quota_action import QuotaAction
from app.models.usage_ledger import UsageLedger
from app.schemas.usage import UsageActionBreakdown, UsageSummaryResponse


def resolve_usage_period(
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> tuple[datetime, datetime]:
    """
    Half-open window [start, end) in naive UTC.

    If both from_dt and to_dt are None: last 30 days ending now (UTC).
    If both set: use them (coerced to naive UTC).
    If only one is set: raises ValueError.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if from_dt is None and to_dt is None:
        return now - timedelta(days=30), now
    if from_dt is None or to_dt is None:
        raise ValueError("Provide both from and to query parameters, or neither")

    def _naive_utc(dt: datetime) -> datetime:
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    start = _naive_utc(from_dt)
    end = _naive_utc(to_dt)
    if start >= end:
        raise ValueError("from must be strictly before to")
    return start, end


async def summarize_usage_for_org(
    db: AsyncSession,
    organization_id: UUID,
    period_start: datetime,
    period_end: datetime,
) -> UsageSummaryResponse:
    """Sum usage_ledger for org in [period_start, period_end); breakdown by action_id."""
    base_filter = (
        UsageLedger.organization_id == organization_id,
        UsageLedger.created_at >= period_start,
        UsageLedger.created_at < period_end,
    )

    totals_row = await db.execute(
        select(
            func.coalesce(func.sum(UsageLedger.compute_units), 0),
            func.coalesce(func.sum(UsageLedger.units), 0),
        ).where(*base_filter)
    )
    total_compute_units, total_units = totals_row.one()

    agg = await db.execute(
        select(
            UsageLedger.action_id,
            QuotaAction.action_key,
            func.sum(UsageLedger.units).label("units"),
            func.sum(UsageLedger.compute_units).label("compute_units"),
        )
        .outerjoin(QuotaAction, QuotaAction.id == UsageLedger.action_id)
        .where(*base_filter)
        .group_by(UsageLedger.action_id, QuotaAction.action_key)
        .order_by(func.sum(UsageLedger.compute_units).desc())
    )
    rows = agg.all()
    by_action = [
        UsageActionBreakdown(
            action_id=r.action_id,
            action_key=r.action_key,
            units=int(r.units or 0),
            compute_units=int(r.compute_units or 0),
        )
        for r in rows
    ]

    return UsageSummaryResponse(
        organization_id=organization_id,
        period_start=period_start,
        period_end=period_end,
        total_compute_units=int(total_compute_units),
        total_units=int(total_units),
        by_action=by_action,
    )
