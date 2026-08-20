"""Shared fixtures for PostgreSQL-backed quota tests."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Load .env before importing app settings
_root = Path(__file__).resolve().parent.parent
_env = _root / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# Use a dedicated test DB if provided
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

# Ensure Settings can construct even if local .env has a broken GCP JSON blob.
_dummy_sa = {
    "type": "service_account",
    "project_id": "test",
    "private_key_id": "x",
    "private_key": "-----BEGIN PRIVATE KEY----- PLACEHOLDER -----END PRIVATE KEY-----",
    "client_email": "test@test.iam.gserviceaccount.com",
    "client_id": "1",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
}
# Always override for tests so malformed Coolify-escaped JSON does not break CI
os.environ["GCP_SERVICE_ACCOUNT_JSON"] = json.dumps(_dummy_sa)

# Clear cached settings if previously imported
import app.core.config as _cfg  # noqa: E402

_cfg.get_settings.cache_clear()
_cfg.settings = _cfg.get_settings()

from app.core.config import asyncpg_connect_args_for_sslmode, settings  # noqa: E402
from app.core.constants import (  # noqa: E402
    ORG_STATUS_ACTIVE,
    PERIOD_PER_DAY,
    ROLE_OWNER,
    SUBSCRIPTION_STATUS_ACTIVE,
    TIER_STARTER,
)
from app.models.organization import Organization  # noqa: E402
from app.models.organization_member import OrganizationMember  # noqa: E402
from app.models.organization_quota_limit import OrganizationQuotaLimit  # noqa: E402
from app.models.organization_subscription import OrganizationSubscription  # noqa: E402
from app.models.member import Member  # noqa: E402
from app.models.plan import Plan  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.quota_action import QuotaAction  # noqa: E402
from app.models.quota_action_price import QuotaActionPrice  # noqa: E402
from app.models.organization_entitlement import OrganizationEntitlement  # noqa: E402


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args=asyncpg_connect_args_for_sslmode(settings.POSTGRES_SSLMODE),
        echo=False,
    )
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def redis_client():
    from redis.asyncio import Redis

    client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def seeded_org(db_session: AsyncSession):
    """Create an isolated org + action + entitlement + limits + price for tests."""
    now = _now()
    suffix = uuid.uuid4().hex[:8]
    member = Member(
        id=uuid.uuid4(),
        firebase_uid=f"test-uid-{suffix}",
        email=f"quota-test-{suffix}@example.com",
        display_name="Quota Tester",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    org = Organization(
        id=uuid.uuid4(),
        name=f"Quota Test Org {suffix}",
        slug=f"quota-test-{suffix}",
        status=ORG_STATUS_ACTIVE,
        tier=TIER_STARTER,
        prepaid_balance_cents=10_000,
        held_balance_cents=0,
        billing_mode="postpay",
        overdraft_limit_cents=0,
        created_at=now,
        updated_at=now,
    )
    product = Product(
        id=uuid.uuid4(),
        name=f"Medical {suffix}",
        product_key=f"medical_test_{suffix}",
        description="test",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    action = QuotaAction(
        id=uuid.uuid4(),
        action_key=f"medical.test.action.{suffix}",
        domain="medical",
        unit_type="count",
        product_id=product.id,
        is_active=True,
        created_at=now,
    )
    plan = Plan(
        id=uuid.uuid4(),
        name=f"Test Plan {suffix}",
        monthly_price=0,
        included_compute_units=1_000_000,
        overage_rate=1,
        created_at=now,
    )
    db_session.add_all([member, org, product, action, plan])
    await db_session.flush()

    db_session.add_all(
        [
            OrganizationMember(
                id=uuid.uuid4(),
                organization_id=org.id,
                member_id=member.id,
                role=ROLE_OWNER,
                created_at=now,
            ),
            OrganizationEntitlement(
                id=uuid.uuid4(),
                organization_id=org.id,
                product_id=product.id,
                created_at=now,
            ),
            OrganizationSubscription(
                id=uuid.uuid4(),
                organization_id=org.id,
                plan_id=plan.id,
                status=SUBSCRIPTION_STATUS_ACTIVE,
                billing_cycle_start=now - timedelta(days=1),
                billing_cycle_end=now + timedelta(days=30),
                created_at=now,
            ),
            OrganizationQuotaLimit(
                id=uuid.uuid4(),
                organization_id=org.id,
                action_id=action.id,
                period=PERIOD_PER_DAY,
                limit_value=10,
                created_at=now,
            ),
            QuotaActionPrice(
                id=uuid.uuid4(),
                action_id=action.id,
                rate_cents_per_compute_unit=1,
                effective_from=now - timedelta(days=1),
                created_at=now,
            ),
        ]
    )
    await db_session.commit()

    yield {
        "org": org,
        "member": member,
        "action": action,
        "product": product,
        "plan": plan,
    }

    # Best-effort cleanup
    await db_session.delete(org)
    await db_session.delete(action)
    await db_session.delete(product)
    await db_session.delete(plan)
    await db_session.delete(member)
    await db_session.commit()
