"""Cache org quota limits and org status in Redis; invalidate on update."""

import json
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.organization_quota_limit import OrganizationQuotaLimit
from app.utils.redis_keys import TTL_ORG_LIMITS, TTL_ORG_STATUS, org_limits_key, org_status_key


async def get_org_limits_from_db(db: AsyncSession, org_id: UUID) -> list[dict]:
    """Load org quota limits from DB as list of dicts (action_id, period, limit_value, action_key if joined)."""
    result = await db.execute(
        select(OrganizationQuotaLimit).where(OrganizationQuotaLimit.organization_id == org_id)
    )
    rows = result.scalars().all()
    return [
        {
            "action_id": str(r.action_id),
            "organization_id": str(r.organization_id),
            "limit_value": r.limit_value,
            "period": r.period,
        }
        for r in rows
    ]


async def get_org_limits(redis: Redis, db: AsyncSession, org_id: UUID) -> list[dict]:
    """Get org limits from Redis or DB; populate cache on miss."""
    key = org_limits_key(str(org_id))
    raw = await redis.get(key)
    if raw is not None:
        return json.loads(raw)
    limits = await get_org_limits_from_db(db, org_id)
    await redis.setex(key, TTL_ORG_LIMITS, json.dumps(limits))
    return limits


async def set_org_limits_cache(redis: Redis, org_id: UUID, limits: list[dict]) -> None:
    """Write org limits to Redis (e.g. after loading from DB for invalidation refresh)."""
    key = org_limits_key(str(org_id))
    await redis.setex(key, TTL_ORG_LIMITS, json.dumps(limits))


async def invalidate_org_limits(redis: Redis, org_id: UUID) -> None:
    """Delete org_limits key so next read refetches from DB."""
    await redis.delete(org_limits_key(str(org_id)))


async def get_org_status_from_db(db: AsyncSession, org_id: UUID) -> str | None:
    """Load organization status from DB."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalars().one_or_none()
    return org.status if org else None


async def get_org_status(redis: Redis, db: AsyncSession, org_id: UUID) -> str | None:
    """Get org status from Redis or DB; populate cache on miss."""
    key = org_status_key(str(org_id))
    raw = await redis.get(key)
    if raw is not None:
        return raw
    status = await get_org_status_from_db(db, org_id)
    if status is not None:
        await redis.setex(key, TTL_ORG_STATUS, status)
    return status


async def invalidate_org_status(redis: Redis, org_id: UUID) -> None:
    """Delete org_status key."""
    await redis.delete(org_status_key(str(org_id)))


async def invalidate_org(redis: Redis, org_id: UUID) -> None:
    """Invalidate both org_limits and org_status for an org."""
    await invalidate_org_limits(redis, org_id)
    await invalidate_org_status(redis, org_id)
