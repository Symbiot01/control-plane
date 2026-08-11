"""Internal API (Product Plane): quota check. Protected by INTERNAL_API_KEY."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_internal_api_key
from app.db.session import get_db
from app.schemas.internal import (
    QuotaCheckRequest,
    QuotaCheckResponse,
    QuotaCommitRequest,
    QuotaCommitResponse,
    QuotaReserveRequest,
    QuotaReserveResponse,
    QuotaRollbackRequest,
    QuotaRollbackResponse,
)
from app.services.quota_accounting_service import QuotaConflictError, QuotaStateError
from app.services.quota_check_service import (
    quota_check,
    quota_commit,
    quota_reserve,
    quota_rollback,
)

router = APIRouter(prefix="/internal/v1", tags=["internal"])


def _map_quota_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, QuotaConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": exc.detail, "code": exc.code},
        )
    if isinstance(exc, QuotaStateError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": exc.detail, "status": exc.status},
        )
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.post("/quota/check", response_model=QuotaCheckResponse)
async def post_quota_check(
    body: QuotaCheckRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_internal_api_key)],
) -> QuotaCheckResponse:
    """Check and consume quota for org/action/units. Returns allow/deny and optional usage/limit."""
    redis = request.app.state.redis
    try:
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
        await db.commit()
    except Exception as e:
        await db.rollback()
        if isinstance(e, (LookupError, QuotaConflictError, QuotaStateError, ValueError)):
            raise _map_quota_error(e) from e
        raise
    return QuotaCheckResponse(
        allowed=result["allowed"],
        reason=result.get("reason"),
        status=result.get("status"),
        request_id=result.get("request_id"),
        current_usage=result.get("current_usage"),
        limit=result.get("limit"),
        actual_cost_cents=result.get("actual_cost_cents"),
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
    try:
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
        await db.commit()
    except Exception as e:
        await db.rollback()
        if isinstance(e, (LookupError, QuotaConflictError, QuotaStateError, ValueError)):
            raise _map_quota_error(e) from e
        raise

    return QuotaReserveResponse(
        allowed=result["allowed"],
        reason=result.get("reason"),
        status=result.get("status"),
        request_id=result.get("request_id"),
        expires_at=result.get("expires_at"),
        current_usage=result.get("current_usage"),
        limit=result.get("limit"),
    )


@router.post("/quota/commit", response_model=QuotaCommitResponse)
async def post_quota_commit(
    body: QuotaCommitRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_internal_api_key)],
) -> QuotaCommitResponse:
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
    except Exception as e:
        await db.rollback()
        if isinstance(e, (LookupError, QuotaConflictError, QuotaStateError, ValueError)):
            raise _map_quota_error(e) from e
        raise
    return QuotaCommitResponse(
        status=result["status"],
        request_id=result.get("request_id"),
        allowed=result.get("allowed"),
        reason=result.get("reason"),
        actual_cost_cents=result.get("actual_cost_cents"),
    )


@router.post("/quota/rollback", response_model=QuotaRollbackResponse)
async def post_quota_rollback(
    body: QuotaRollbackRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[None, Depends(require_internal_api_key)],
) -> QuotaRollbackResponse:
    """Rollback previously reserved quota (Phase 2 Alternative)."""
    try:
        result = await quota_rollback(
            db,
            org_id=body.organization_id,
            request_id=body.request_id,
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        if isinstance(e, (LookupError, QuotaConflictError, QuotaStateError, ValueError)):
            raise _map_quota_error(e) from e
        raise
    return QuotaRollbackResponse(
        status=result["status"],
        request_id=result.get("request_id"),
        allowed=result.get("allowed"),
        reason=result.get("reason"),
    )
