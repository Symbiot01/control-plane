#!/usr/bin/env python3
"""
Seed plans, quota actions, subscription, and quota limits for a test user so e2e tests can run fully.

- Ensures plans and quota_actions (+ prices) exist.
- Finds member by email; uses their first org or creates one and adds them as owner.
- Creates an active subscription (starter plan) for the current month.
- Adds organization_quota_limits so internal quota/check can return allowed.

Usage:
  python scripts/seed_test_user.py [EMAIL]
  python scripts/seed_test_user.py sahil0111patel@gmail.com

Run from project root. Member must already exist (e.g. after one /auth/exchange with that email).
"""

import asyncio
import calendar
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import asyncpg_connect_args_for_sslmode, settings
from app.core.constants import (
    PERIOD_LIFETIME,
    PERIOD_PER_DAY,
    PERIOD_PER_MONTH,
    ROLE_OWNER,
    SUBSCRIPTION_STATUS_ACTIVE,
)
from app.models.member import Member
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.organization_quota_limit import OrganizationQuotaLimit
from app.models.organization_subscription import OrganizationSubscription
from app.models.plan import Plan
from app.models.quota_action import QuotaAction
from app.models.quota_action_price import QuotaActionPrice
from app.services.org_service import create_organization
from app.services.subscription_service import create_subscription

DEFAULT_EMAIL = "sahil0111patel@gmail.com"
PLAN_NAME = "starter"
ACTIONS_TO_LIMIT = [
    ("legal.case.analyze.v1", 100, 500, 10_000),   # per_day, per_month, lifetime
    ("medical.opinion.generate.v1", 50, 200, 5_000),
]


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


async def ensure_plans(session: AsyncSession) -> Plan | None:
    r = await session.execute(select(Plan).where(Plan.name == PLAN_NAME))
    plan = r.scalars().one_or_none()
    if plan is not None:
        print(f"Plan '{PLAN_NAME}' already exists.")
        return plan
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    plan = Plan(
        id=uuid4(),
        name=PLAN_NAME,
        monthly_price=2999,
        included_compute_units=10_000,
        overage_rate=5,
        currency="USD",
        created_at=now,
    )
    session.add(plan)
    await session.flush()
    print(f"Inserted plan: {PLAN_NAME}")
    return plan


async def ensure_actions_and_prices(session: AsyncSession) -> list[QuotaAction]:
    ACTIONS = [
        ("legal.case.analyze.v1", "legal", "count", "Legal case analysis"),
        ("medical.opinion.generate.v1", "medical", "tokens", "Medical opinion generation"),
        ("vision.defect.detect.v1", "vision", "count", "Vision defect detection"),
        ("core.member.create.v1", "core", "count", "Member creation"),
    ]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await session.execute(select(QuotaAction))
    existing = {a.action_key: a for a in result.scalars().all()}
    for action_key, domain, unit_type, description in ACTIONS:
        if action_key in existing:
            continue
        q = QuotaAction(
            id=uuid4(),
            action_key=action_key,
            domain=domain,
            unit_type=unit_type,
            description=description,
            is_active=True,
            created_at=now,
        )
        session.add(q)
        await session.flush()
        price = QuotaActionPrice(
            id=uuid4(),
            action_id=q.id,
            rate_cents_per_compute_unit=1,
            effective_from=now,
            created_at=now,
        )
        session.add(price)
        print(f"Inserted action + price: {action_key}")
        existing[action_key] = q
    await session.flush()
    result = await session.execute(select(QuotaAction))
    return list(result.scalars().all())


async def get_or_create_org_for_member(session: AsyncSession, member_id) -> Organization:
    result = await session.execute(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.member_id == member_id)
    )
    orgs = list(result.scalars().all())
    if orgs:
        print(f"Using existing org: {orgs[0].name} ({orgs[0].id})")
        return orgs[0]
    org = await create_organization(
        session,
        name="Test Org (seed)",
        owner_member_id=member_id,
        slug="test-org-seed",
    )
    await session.flush()
    print(f"Created org: {org.name} ({org.id})")
    return org


async def ensure_subscription(session: AsyncSession, org_id, plan_id) -> OrganizationSubscription:
    now = _naive_utc(datetime.now(timezone.utc))
    year, month = now.year, now.month
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    _, last_day = calendar.monthrange(year, month)
    end = start.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999_999)
    end_next = start.replace(month=month + 1 if month < 12 else 1, year=year if month < 12 else year + 1, day=1)
    try:
        sub = await create_subscription(session, org_id, plan_id, start, end_next)
        await session.flush()
        print(f"Created subscription: {sub.id} ({start.date()} to {end_next.date()})")
        return sub
    except ValueError as e:
        if "already has an active subscription" in str(e):
            r = await session.execute(
                select(OrganizationSubscription).where(
                    OrganizationSubscription.organization_id == org_id,
                    OrganizationSubscription.status == SUBSCRIPTION_STATUS_ACTIVE,
                )
            )
            sub = r.scalars().first()
            if sub:
                print(f"Subscription already exists: {sub.id}")
                return sub
        raise


async def ensure_quota_limits(session: AsyncSession, org_id, actions_by_key) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for action_key, per_day, per_month, lifetime in ACTIONS_TO_LIMIT:
        action = actions_by_key.get(action_key)
        if not action:
            continue
        for period, limit in [
            (PERIOD_PER_DAY, per_day),
            (PERIOD_PER_MONTH, per_month),
            (PERIOD_LIFETIME, lifetime),
        ]:
            r = await session.execute(
                select(OrganizationQuotaLimit).where(
                    OrganizationQuotaLimit.organization_id == org_id,
                    OrganizationQuotaLimit.action_id == action.id,
                    OrganizationQuotaLimit.period == period,
                )
            )
            if r.scalars().first() is not None:
                continue
            lim = OrganizationQuotaLimit(
                id=uuid4(),
                organization_id=org_id,
                action_id=action.id,
                limit_value=limit,
                period=period,
                created_at=now,
            )
            session.add(lim)
            print(f"  Limit: {action_key} {period}={limit}")
    await session.flush()


async def main():
    email = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EMAIL).strip().lower()
    engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args=asyncpg_connect_args_for_sslmode(settings.POSTGRES_SSLMODE),
        echo=False,
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await ensure_plans(session)
        actions = await ensure_actions_and_prices(session)
        actions_by_key = {a.action_key: a for a in actions}

        result = await session.execute(select(Member).where(Member.email == email))
        member = result.scalars().one_or_none()
        if member is None:
            print(f"No member found with email '{email}'. Auto-creating a fake one for testing...")
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            member = Member(
                id=uuid4(),
                firebase_uid=f"fake_uid_{uuid4()}",
                email=email,
                display_name="Test User",
                is_active=True,
                created_at=now,
                updated_at=now
            )
            session.add(member)
            await session.flush()
            
        print(f"Member: {member.email} ({member.id})")

        plan = (await session.execute(select(Plan).where(Plan.name == PLAN_NAME))).scalars().one()
        org = await get_or_create_org_for_member(session, member.id)
        
        # Give them $100 in prepaid credits so prepay endpoints work
        from app.services.credit_service import grant_credits
        await grant_credits(session, org.id, 10000, type="grant", reference_id="seed_bonus")

        await ensure_subscription(session, org.id, plan.id)
        await ensure_quota_limits(session, org.id, actions_by_key)

        await session.commit()
    await engine.dispose()
    print("Done. You can run test_endpoints.sh with ID_TOKEN; quota/check should allow for this org.")


if __name__ == "__main__":
    asyncio.run(main())
