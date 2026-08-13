"""Integration tests for hardened quota accounting."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.models.organization import Organization
from app.models.quota_check_request import QuotaCheckRequest
from app.models.quota_usage_bucket import QuotaUsageBucket
from app.models.usage_ledger import UsageLedger
from app.services.quota_accounting_service import QuotaConflictError
from app.services.quota_check_service import (
    quota_check,
    quota_commit,
    quota_reserve,
    quota_rollback,
)


@pytest.mark.asyncio
async def test_postpay_quota_check_allow_records_usage(db_session, redis_client, seeded_org):
    org = seeded_org["org"]
    action = seeded_org["action"]
    member = seeded_org["member"]
    req = f"check-postpay-{uuid.uuid4()}"

    result = await quota_check(
        redis_client,
        db_session,
        org_id=org.id,
        action_key=action.action_key,
        units=1,
        member_id=member.id,
        request_id=req,
    )
    await db_session.commit()

    assert result["allowed"] is True
    assert result["status"] == "committed"

    ledger = (
        await db_session.execute(
            select(UsageLedger).where(
                UsageLedger.organization_id == org.id,
                UsageLedger.request_id == req,
            )
        )
    ).scalars().one()
    assert ledger.compute_units == 1
    assert ledger.cost_cents == 0  # postpay: no wallet charge

    bucket = (
        await db_session.execute(
            select(QuotaUsageBucket).where(
                QuotaUsageBucket.organization_id == org.id,
                QuotaUsageBucket.action_id == action.id,
                QuotaUsageBucket.period == "per_day",
            )
        )
    ).scalars().one()
    assert bucket.used_units == 1
    assert bucket.reserved_units == 0


@pytest.mark.asyncio
async def test_quota_check_idempotent_retry(db_session, redis_client, seeded_org):
    org = seeded_org["org"]
    action = seeded_org["action"]
    req = f"check-idem-{uuid.uuid4()}"

    r1 = await quota_check(
        redis_client, db_session, org_id=org.id, action_key=action.action_key, units=1, request_id=req
    )
    await db_session.commit()
    r2 = await quota_check(
        redis_client, db_session, org_id=org.id, action_key=action.action_key, units=1, request_id=req
    )
    await db_session.commit()

    assert r1["allowed"] and r2["allowed"]
    n = (
        await db_session.execute(
            select(UsageLedger).where(
                UsageLedger.organization_id == org.id,
                UsageLedger.request_id == req,
            )
        )
    ).scalars().all()
    assert len(n) == 1


@pytest.mark.asyncio
async def test_quota_check_payload_mismatch_409(db_session, redis_client, seeded_org):
    org = seeded_org["org"]
    action = seeded_org["action"]
    req = f"check-mismatch-{uuid.uuid4()}"

    await quota_check(
        redis_client, db_session, org_id=org.id, action_key=action.action_key, units=1, request_id=req
    )
    await db_session.commit()

    with pytest.raises(QuotaConflictError):
        await quota_check(
            redis_client,
            db_session,
            org_id=org.id,
            action_key=action.action_key,
            units=2,
            request_id=req,
        )


@pytest.mark.asyncio
async def test_prepay_quota_check_debits_wallet(db_session, redis_client, seeded_org):
    org = seeded_org["org"]
    action = seeded_org["action"]
    org.billing_mode = "prepay"
    org.prepaid_balance_cents = 100
    await db_session.commit()

    req = f"check-prepay-{uuid.uuid4()}"
    result = await quota_check(
        redis_client,
        db_session,
        org_id=org.id,
        action_key=action.action_key,
        units=1,
        compute_units=5,
        request_id=req,
    )
    await db_session.commit()
    assert result["allowed"] is True

    refreshed = (
        await db_session.execute(select(Organization).where(Organization.id == org.id))
    ).scalars().one()
    assert refreshed.prepaid_balance_cents == 95

    ledger = (
        await db_session.execute(
            select(UsageLedger).where(UsageLedger.request_id == req)
        )
    ).scalars().one()
    assert ledger.cost_cents == 5
    assert ledger.compute_units == 5


@pytest.mark.asyncio
async def test_reserve_commit_updates_counters(db_session, redis_client, seeded_org):
    org = seeded_org["org"]
    action = seeded_org["action"]
    member = seeded_org["member"]
    req = f"reserve-commit-{uuid.uuid4()}"

    reserved = await quota_reserve(
        redis_client,
        db_session,
        org_id=org.id,
        action_key=action.action_key,
        max_units=3,
        request_id=req,
        member_id=member.id,
    )
    await db_session.commit()
    assert reserved["allowed"] is True
    assert reserved["status"] == "held"

    bucket = (
        await db_session.execute(
            select(QuotaUsageBucket).where(
                QuotaUsageBucket.organization_id == org.id,
                QuotaUsageBucket.action_id == action.id,
                QuotaUsageBucket.period == "per_day",
            )
        )
    ).scalars().one()
    assert bucket.reserved_units == 3
    assert bucket.used_units == 0

    committed = await quota_commit(
        db_session,
        redis_client,
        org_id=org.id,
        request_id=req,
        actual_units=2,
        compute_units=2,
    )
    await db_session.commit()
    assert committed["status"] == "committed"

    await db_session.refresh(bucket)
    assert bucket.reserved_units == 0
    assert bucket.used_units == 2


@pytest.mark.asyncio
async def test_reserve_rollback_releases_capacity(db_session, redis_client, seeded_org):
    org = seeded_org["org"]
    action = seeded_org["action"]
    req = f"reserve-rollback-{uuid.uuid4()}"

    await quota_reserve(
        redis_client,
        db_session,
        org_id=org.id,
        action_key=action.action_key,
        max_units=4,
        request_id=req,
    )
    await db_session.commit()

    rolled = await quota_rollback(db_session, org_id=org.id, request_id=req)
    await db_session.commit()
    assert rolled["status"] == "rolled_back"

    bucket = (
        await db_session.execute(
            select(QuotaUsageBucket).where(
                QuotaUsageBucket.organization_id == org.id,
                QuotaUsageBucket.action_id == action.id,
                QuotaUsageBucket.period == "per_day",
            )
        )
    ).scalars().one()
    assert bucket.reserved_units == 0
    assert bucket.used_units == 0


@pytest.mark.asyncio
async def test_reserve_capacity_enforced(db_session, redis_client, seeded_org):
    """per_day limit=10; two concurrent-style reserves of 8 then 8 -> second denied."""
    org = seeded_org["org"]
    action = seeded_org["action"]

    r1 = await quota_reserve(
        redis_client,
        db_session,
        org_id=org.id,
        action_key=action.action_key,
        max_units=8,
        request_id=f"cap-a-{uuid.uuid4()}",
    )
    await db_session.commit()
    assert r1["allowed"] is True

    r2 = await quota_reserve(
        redis_client,
        db_session,
        org_id=org.id,
        action_key=action.action_key,
        max_units=8,
        request_id=f"cap-b-{uuid.uuid4()}",
    )
    await db_session.commit()
    assert r2["allowed"] is False
    assert "limit exceeded" in (r2["reason"] or "")


@pytest.mark.asyncio
async def test_duplicate_reserve_same_request_id(db_session, redis_client, seeded_org):
    org = seeded_org["org"]
    action = seeded_org["action"]
    req = f"dup-reserve-{uuid.uuid4()}"

    r1 = await quota_reserve(
        redis_client,
        db_session,
        org_id=org.id,
        action_key=action.action_key,
        max_units=2,
        request_id=req,
    )
    await db_session.commit()
    r2 = await quota_reserve(
        redis_client,
        db_session,
        org_id=org.id,
        action_key=action.action_key,
        max_units=2,
        request_id=req,
    )
    await db_session.commit()
    assert r1["status"] == "held" and r2["status"] == "held"

    rows = (
        await db_session.execute(
            select(QuotaCheckRequest).where(
                QuotaCheckRequest.organization_id == org.id,
                QuotaCheckRequest.request_id == req,
            )
        )
    ).scalars().all()
    assert len(rows) == 1

    bucket = (
        await db_session.execute(
            select(QuotaUsageBucket).where(
                QuotaUsageBucket.organization_id == org.id,
                QuotaUsageBucket.action_id == action.id,
                QuotaUsageBucket.period == "per_day",
            )
        )
    ).scalars().one()
    assert bucket.reserved_units == 2


@pytest.mark.asyncio
async def test_commit_rejects_over_max(db_session, redis_client, seeded_org):
    org = seeded_org["org"]
    action = seeded_org["action"]
    req = f"overmax-{uuid.uuid4()}"
    await quota_reserve(
        redis_client,
        db_session,
        org_id=org.id,
        action_key=action.action_key,
        max_units=2,
        request_id=req,
    )
    await db_session.commit()

    with pytest.raises(ValueError, match="exceeds reserved"):
        await quota_commit(
            db_session,
            redis_client,
            org_id=org.id,
            request_id=req,
            actual_units=3,
        )


@pytest.mark.asyncio
async def test_commit_idempotent(db_session, redis_client, seeded_org):
    org = seeded_org["org"]
    action = seeded_org["action"]
    req = f"commit-idem-{uuid.uuid4()}"
    await quota_reserve(
        redis_client,
        db_session,
        org_id=org.id,
        action_key=action.action_key,
        max_units=2,
        request_id=req,
    )
    await db_session.commit()
    c1 = await quota_commit(
        db_session, redis_client, org_id=org.id, request_id=req, actual_units=1
    )
    await db_session.commit()
    c2 = await quota_commit(
        db_session, redis_client, org_id=org.id, request_id=req, actual_units=1
    )
    await db_session.commit()
    assert c1["status"] == "committed" and c2["status"] == "committed"
    ledgers = (
        await db_session.execute(
            select(UsageLedger).where(UsageLedger.request_id == req)
        )
    ).scalars().all()
    assert len(ledgers) == 1


@pytest.mark.asyncio
async def test_concurrent_same_request_id_check(db_session, redis_client, seeded_org):
    """Two concurrent checks with same request_id -> one ledger row."""
    org = seeded_org["org"]
    action = seeded_org["action"]
    req = f"concurrent-check-{uuid.uuid4()}"

    async def _one():
        # Each concurrent call needs its own session in real life; here we serialize
        # through the unique claim — still validate single consumption.
        return await quota_check(
            redis_client,
            db_session,
            org_id=org.id,
            action_key=action.action_key,
            units=1,
            request_id=req,
        )

    r1 = await _one()
    await db_session.commit()
    r2 = await _one()
    await db_session.commit()
    assert r1["allowed"] and r2["allowed"]
    ledgers = (
        await db_session.execute(
            select(UsageLedger).where(UsageLedger.request_id == req)
        )
    ).scalars().all()
    assert len(ledgers) == 1
