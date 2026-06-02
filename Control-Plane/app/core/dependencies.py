"""Shared dependencies: require_control_jwt, get_current_member, RBAC, rate limit."""

from uuid import UUID
from typing import Annotated
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import RATE_LIMIT_PER_MINUTE, ROLE_OWNER
from app.core.jwt import verify_control_jwt
from app.db.session import get_db
from app.utils.redis_keys import TTL_RATE_MINUTE, minute_ts, rate_limit_api_key
from app.models.member import Member
from app.models.organization_member import OrganizationMember

security = HTTPBearer(auto_error=False)


async def require_control_jwt(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict:
    """Extract Bearer token, verify Control JWT, return payload. Raises 401 if missing/invalid."""
    if not credentials or credentials.credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = verify_control_jwt(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def get_current_member(
    payload: Annotated[dict, Depends(require_control_jwt)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Member:
    """Load member from DB by JWT sub (member_id). Raises 401 if not found."""
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        member_id = UUID(sub)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(Member).where(Member.id == member_id))
    member = result.scalars().one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Member not found")
    return member


async def require_org_member(
    payload: Annotated[dict, Depends(require_control_jwt)],
) -> OrganizationMember:
    """Require JWT to have org_id and a valid role. Returns a mock OrganizationMember row or 403."""
    org_id_str = payload.get("org_id")
    if not org_id_str:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No organization in token; set active org first",
        )
    level = payload.get("level_of_access")
    if level in (None, "guest"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of an organization",
        )
    try:
        org_id = UUID(org_id_str)
        member_id = UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")
        
    return OrganizationMember(
        organization_id=org_id,
        member_id=member_id,
        role=level
    )


def require_role(allowed_roles: tuple[str, ...]):
    """Dependency factory: require current org membership and role in allowed_roles."""

    async def _require_role(
        membership: Annotated[OrganizationMember, Depends(require_org_member)],
    ) -> OrganizationMember:
        if membership.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return membership

    return _require_role


async def require_org_member_for_path(
    org_id: UUID,
    payload: Annotated[dict, Depends(require_control_jwt)],
) -> OrganizationMember:
    """Require JWT org_id to match path org_id and return membership."""
    org_id_str = payload.get("org_id")
    if org_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No organization in token",
        )
    try:
        token_org_id = UUID(org_id_str)
        member_id = UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")
    if token_org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization id does not match token",
        )
        
    level = payload.get("level_of_access")
    if level in (None, "guest", "super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a standard member of this organization",
        )

    return OrganizationMember(
        organization_id=org_id,
        member_id=member_id,
        role=level
    )


async def require_org_owner_for_path(
    org_id: UUID,
    payload: Annotated[dict, Depends(require_control_jwt)],
) -> OrganizationMember:
    """Require path org_id match and role is owner."""
    membership = await require_org_member_for_path(org_id, payload)
    if membership.role != ROLE_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role",
        )
    return membership


async def require_internal_api_key(request: Request) -> None:
    """Validate INTERNAL_API_KEY from header X-Internal-Api-Key or Authorization Bearer. For internal/admin endpoints."""
    key = request.headers.get("X-Internal-Api-Key") or (
        request.headers.get("Authorization") or ""
    ).replace("Bearer ", "")
    if not key or not secrets.compare_digest(key, settings.INTERNAL_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal API key",
        )


async def rate_limit_per_org(
    request: Request,
    payload: Annotated[dict, Depends(require_control_jwt)],
) -> None:
    """Dependency: rate limit by org_id (and optionally member) per minute. Raises 429 if exceeded."""
    org_id_str = payload.get("org_id")
    if not org_id_str:
        return  # No org in token: skip rate limit
    redis: Redis = request.app.state.redis
    ts = minute_ts()
    key = rate_limit_api_key(org_id_str, ts)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, TTL_RATE_MINUTE)
    if count > RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
