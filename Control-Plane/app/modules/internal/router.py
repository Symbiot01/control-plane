"""Internal API (Product Plane): quota check. Protected by INTERNAL_API_KEY."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_internal_api_key
from app.db.session import get_db
from app.schemas.internal import (
    QuotaCheckRequest, QuotaCheckResponse,
    QuotaReserveRequest, QuotaReserveResponse,
    QuotaCommitRequest, QuotaRollbackRequest
)
from app.services.quota_check_service import quota_check, quota_reserve, quota_commit, quota_rollback

router = APIRouter(prefix="/internal/v1", tags=["internal"])


@router.post("/quota/check", response_model=QuotaCheckResponse)
async def post_quota_check(
    body: QuotaCheckRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_internal_api_key)],
) -> QuotaCheckResponse:
    """Check and consume quota for org/action/units. Returns allow/deny and optional usage/limit."""
    redis = request.app.state.redis
    result = await quota_check(
        redis,
        db,
        org_id=body.organization_id,
        action_key=body.action_key,
        units=body.units,
        member_id=body.member_id,
        request_id=body.request_id,
        compute_units=body.compute_units,
    )
    return QuotaCheckResponse(
        allowed=result["allowed"],
        reason=result.get("reason"),
        current_usage=result.get("current_usage"),
        limit=result.get("limit"),
    )


@router.post("/quota/reserve", response_model=QuotaReserveResponse)
async def post_quota_reserve(
    body: QuotaReserveRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_internal_api_key)],
) -> QuotaReserveResponse:
    """Reserve quota for an action (Phase 1)."""
    redis = request.app.state.redis
    result = await quota_reserve(
        redis,
        db,
        org_id=body.organization_id,
        action_key=body.action_key,
        max_units=body.max_units,
        request_id=body.request_id,
        member_id=body.member_id,
        compute_units=body.compute_units,
    )
    # Explicitly commit the transaction before sending the response
    # Otherwise, the client might send a commit request before the DB finishes committing the reservation!
    await db.commit()
    
    return QuotaReserveResponse(
        allowed=result["allowed"],
        reason=result.get("reason"),
    )


@router.post("/quota/commit")
async def post_quota_commit(
    body: QuotaCommitRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_internal_api_key)],
) -> dict:
    """Commit previously reserved quota (Phase 2)."""
    redis = request.app.state.redis
    try:
        result = await quota_commit(
            db,
            redis,
            org_id=body.organization_id,
            request_id=body.request_id,
            actual_units=body.actual_units,
            compute_units=body.compute_units,
        )
        await db.commit()
        return result
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/quota/rollback")
async def post_quota_rollback(
    body: QuotaRollbackRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_internal_api_key)],
) -> dict:
    """Rollback previously reserved quota (Phase 2 Alternative)."""
    try:
        result = await quota_rollback(
            db,
            org_id=body.organization_id,
            request_id=body.request_id,
        )
        return result
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))

