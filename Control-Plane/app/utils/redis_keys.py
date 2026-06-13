"""Redis key builders and TTL constants for rate limits, quota counters, and cache."""

from datetime import datetime

# TTLs (seconds)
TTL_RATE_MINUTE = 60
TTL_QUOTA_DAY = 86400 + 3600   # 25h
TTL_QUOTA_MONTH = 31 * 86400  # ~31 days
TTL_ORG_LIMITS = 300           # 5 min
TTL_ORG_STATUS = 600           # 10 min


def rate_key(org_id: str, action_key: str, minute_ts: int) -> str:
    """Rate limit key: org + action + minute window."""
    return f"rate:{org_id}:{action_key}:{minute_ts}"


def rate_limit_api_key(org_id: str, ts: int) -> str:
    """General API rate limit key per org per minute."""
    return f"rate:api:{org_id}:{ts}"


def quota_daily_key(org_id: str, action_key: str, yyyymmdd: str) -> str:
    """Daily quota counter key. yyyymmdd e.g. 20250216."""
    return f"quota:day:{org_id}:{action_key}:{yyyymmdd}"


def quota_monthly_key(org_id: str, action_key: str, yyyymm: str) -> str:
    """Monthly quota counter key. yyyymm e.g. 202502."""
    return f"quota:month:{org_id}:{action_key}:{yyyymm}"


def org_limits_key(org_id: str) -> str:
    """Cache key for org quota limits (serialized from DB)."""
    return f"org_limits:{org_id}"


def org_status_key(org_id: str) -> str:
    """Cache key for org status (active/suspended/archived)."""
    return f"org_status:{org_id}"


def minute_ts(dt: datetime | None = None) -> int:
    """Unix minute timestamp for rate window."""
    from datetime import timezone
    t = (dt or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    return int(t.timestamp())


def yyyymmdd(dt: datetime | None = None) -> str:
    """Date string YYYYMMDD."""
    from datetime import timezone
    t = dt or datetime.now(timezone.utc)
    return t.strftime("%Y%m%d")


def yyyymm(dt: datetime | None = None) -> str:
    """Month string YYYYMM."""
    from datetime import timezone
    t = dt or datetime.now(timezone.utc)
    return t.strftime("%Y%m")
