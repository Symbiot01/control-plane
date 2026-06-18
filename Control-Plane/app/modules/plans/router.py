"""Plans routes: list billing plans."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.plan import Plan
from app.schemas.billing import PlanResponse

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanResponse])
async def list_plans(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all plans (catalog). No auth required for read."""
    result = await db.execute(select(Plan).order_by(Plan.name))
    plans = result.scalars().all()
    return [PlanResponse.model_validate(p) for p in plans]
