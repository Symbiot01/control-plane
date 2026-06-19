"""Quotas routes: list and update org quota limits."""

from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import PERIODS
from app.core.dependencies import rate_limit_per_org, require_org_owner_for_path
from app.db.session import get_db
from app.models.organization_member import OrganizationMember
from app.models.organization_quota_limit import OrganizationQuotaLimit
from app.models.quota_action import QuotaAction
from app.schemas.quota import QuotaLimitResponse, QuotaLimitsUpdate
from app.services.quota_cache_service import invalidate_org_limits

router = APIRouter(prefix="/quotas", tags=["quotas"])


@router.get("/{org_id}", response_model=list[QuotaLimitResponse])
async def get_quotas(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _membership: Annotated[OrganizationMember, Depends(require_org_owner_for_path)],
    _rl: Annotated[None, Depends(rate_limit_per_org)],
):
    """List quota limits for org (admin/owner). Path org_id must match JWT org."""
    result = await db.execute(
        select(OrganizationQuotaLimit, QuotaAction.action_key)
        .join(QuotaAction, QuotaAction.id == OrganizationQuotaLimit.action_id)
        .where(OrganizationQuotaLimit.organization_id == org_id)
    )
    rows = result.all()
    return [
        QuotaLimitResponse(
            id=limit.id,
            organization_id=limit.organization_id,
            action_id=limit.action_id,
            action_key=action_key,
            limit_value=limit.limit_value,
            period=limit.period,
            created_at=limit.created_at,
        )
        for limit, action_key in rows
    ]


@router.patch("/{org_id}")
async def patch_quotas(
    org_id: UUID,
    body: QuotaLimitsUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _membership: Annotated[OrganizationMember, Depends(require_org_owner_for_path)],
    _rl: Annotated[None, Depends(rate_limit_per_org)],
):
    """Set or update one quota limit (admin/owner). Invalidates cache."""
    if body.period not in PERIODS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid period")
    from datetime import datetime, timezone
    from uuid import uuid4
    result = await db.execute(
        select(OrganizationQuotaLimit).where(
            OrganizationQuotaLimit.organization_id == org_id,
            OrganizationQuotaLimit.action_id == body.action_id,
            OrganizationQuotaLimit.period == body.period,
        )
    )
    existing = result.scalars().one_or_none()
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for TIMESTAMP WITHOUT TIME ZONE
    if existing is not None:
        existing.limit_value = body.limit_value
        await db.flush()
    else:
        limit = OrganizationQuotaLimit(
            id=uuid4(),
            organization_id=org_id,
            action_id=body.action_id,
            limit_value=body.limit_value,
            period=body.period,
            created_at=now,
        )
        db.add(limit)
        await db.flush()
    redis = request.app.state.redis
    await invalidate_org_limits(redis, org_id)
    return {"status": "updated", "action_id": str(body.action_id), "period": body.period, "limit_value": body.limit_value}
