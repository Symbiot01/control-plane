"""Viewer role: quota deny + operator dependency checks."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.constants import ROLE_MEMBER, ROLE_OWNER, ROLE_VIEWER
from app.core.dependencies import require_org_operator_for_path
from app.models.member import Member
from app.models.organization_member import OrganizationMember
from app.models.quota_usage_bucket import QuotaUsageBucket
from app.models.usage_ledger import UsageLedger
from app.services.quota_check_service import quota_check, quota_reserve


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_quota_check_denies_viewer(db_session, redis_client, seeded_org):
    org = seeded_org["org"]
    action = seeded_org["action"]
    now = _now()
    viewer = Member(
        id=uuid.uuid4(),
        firebase_uid=f"viewer-uid-{uuid.uuid4().hex[:8]}",
        email=f"viewer-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Viewer",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(viewer)
    await db_session.flush()
    # Replace owner membership constraint: member_id is UNIQUE — add second member as viewer
    # by creating a new org membership for the viewer (same org).
    db_session.add(
        OrganizationMember(
            id=uuid.uuid4(),
            organization_id=org.id,
            member_id=viewer.id,
            role=ROLE_VIEWER,
            created_at=now,
        )
    )
    await db_session.commit()

    req = f"check-viewer-{uuid.uuid4()}"
    result = await quota_check(
        redis_client,
        db_session,
        org_id=org.id,
        action_key=action.action_key,
        units=1,
        member_id=viewer.id,
        request_id=req,
    )
    await db_session.commit()

    assert result["allowed"] is False
    assert result["reason"] == "viewer_readonly"
    assert result["status"] == "denied"

    ledger = (
        await db_session.execute(
            select(UsageLedger).where(
                UsageLedger.organization_id == org.id,
                UsageLedger.request_id == req,
            )
        )
    ).scalars().one_or_none()
    assert ledger is None

    bucket = (
        await db_session.execute(
            select(QuotaUsageBucket).where(
                QuotaUsageBucket.organization_id == org.id,
                QuotaUsageBucket.action_id == action.id,
            )
        )
    ).scalars().one_or_none()
    if bucket is not None:
        assert bucket.used_units == 0


@pytest.mark.asyncio
async def test_quota_reserve_denies_viewer(db_session, redis_client, seeded_org):
    org = seeded_org["org"]
    action = seeded_org["action"]
    now = _now()
    viewer = Member(
        id=uuid.uuid4(),
        firebase_uid=f"viewer-res-{uuid.uuid4().hex[:8]}",
        email=f"viewer-res-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Viewer Reserve",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(viewer)
    await db_session.flush()
    db_session.add(
        OrganizationMember(
            id=uuid.uuid4(),
            organization_id=org.id,
            member_id=viewer.id,
            role=ROLE_VIEWER,
            created_at=now,
        )
    )
    await db_session.commit()

    req = f"reserve-viewer-{uuid.uuid4()}"
    result = await quota_reserve(
        redis_client,
        db_session,
        org_id=org.id,
        action_key=action.action_key,
        max_units=10,
        member_id=viewer.id,
        request_id=req,
    )
    await db_session.commit()

    assert result["allowed"] is False
    assert result["reason"] == "viewer_readonly"
    assert result["status"] == "denied"


@pytest.mark.asyncio
async def test_quota_check_allows_owner(db_session, redis_client, seeded_org):
    org = seeded_org["org"]
    action = seeded_org["action"]
    member = seeded_org["member"]
    req = f"check-owner-{uuid.uuid4()}"

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


@pytest.mark.asyncio
async def test_quota_check_denies_member_not_in_org(db_session, redis_client, seeded_org):
    org = seeded_org["org"]
    action = seeded_org["action"]
    now = _now()
    stranger = Member(
        id=uuid.uuid4(),
        firebase_uid=f"stranger-{uuid.uuid4().hex[:8]}",
        email=f"stranger-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Stranger",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(stranger)
    await db_session.commit()

    req = f"check-stranger-{uuid.uuid4()}"
    result = await quota_check(
        redis_client,
        db_session,
        org_id=org.id,
        action_key=action.action_key,
        units=1,
        member_id=stranger.id,
        request_id=req,
    )
    await db_session.commit()

    assert result["allowed"] is False
    assert result["reason"] == "member not in organization"
    assert result["status"] == "denied"


@pytest.mark.asyncio
async def test_require_org_operator_rejects_viewer():
    org_id = uuid.uuid4()
    member_id = uuid.uuid4()
    payload = {
        "sub": str(member_id),
        "org_id": str(org_id),
        "level_of_access": ROLE_VIEWER,
    }
    with pytest.raises(HTTPException) as exc:
        await require_org_operator_for_path(org_id, payload)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_org_operator_allows_member():
    org_id = uuid.uuid4()
    member_id = uuid.uuid4()
    payload = {
        "sub": str(member_id),
        "org_id": str(org_id),
        "level_of_access": ROLE_MEMBER,
    }
    membership = await require_org_operator_for_path(org_id, payload)
    assert membership.role == ROLE_MEMBER
    assert membership.organization_id == org_id


@pytest.mark.asyncio
async def test_require_org_operator_allows_owner():
    org_id = uuid.uuid4()
    member_id = uuid.uuid4()
    payload = {
        "sub": str(member_id),
        "org_id": str(org_id),
        "level_of_access": ROLE_OWNER,
    }
    membership = await require_org_operator_for_path(org_id, payload)
    assert membership.role == ROLE_OWNER
