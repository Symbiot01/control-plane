"""Admin auth: require_super_admin – JWT member must be a super admin."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_member, require_control_jwt
from app.models.member import Member


async def require_super_admin(
    payload: Annotated[dict, Depends(require_control_jwt)],
    member: Annotated[Member, Depends(get_current_member)],
) -> Member:
    """Require caller to be a super admin based on JWT. Returns the Member."""
    if payload.get("level_of_access") != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a super admin",
        )
    return member
