"""Auth routes: exchange Firebase token for Control JWT."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.firebase import verify_id_token
from app.core.jwt import issue_control_jwt
from app.db.session import get_db
from app.models.member import Member
from app.models.organization import Organization
from app.models.organization_invite import OrganizationInvite
from app.models.organization_member import OrganizationMember
from app.modules.admin.models import SuperAdmin
from app.schemas.auth import AuthExchangeRequest, AuthExchangeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


async def get_or_create_member(
    db: AsyncSession,
    firebase_uid: str,
    email: str,
    display_name: str | None = None,
) -> Member:
    """Get member by firebase_uid or create with email."""
    result = await db.execute(select(Member).where(Member.firebase_uid == firebase_uid))
    member = result.scalars().one_or_none()
    if member is not None:
        if member.display_name is None and display_name is not None:
            member.display_name = display_name
            db.add(member)
        return member
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for TIMESTAMP WITHOUT TIME ZONE
    member = Member(
        id=uuid4(),
        firebase_uid=firebase_uid,
        email=email,
        display_name=display_name,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(member)
    await db.flush()
    return member


@router.post("/exchange", response_model=AuthExchangeResponse)
async def auth_exchange(
    body: AuthExchangeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Exchange Firebase ID token for Control JWT."""
    try:
        decoded = verify_id_token(body.id_token)
    except Exception as e:
        print(f"FIREBASE TOKEN VERIFICATION FAILED: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase token",
        ) from e
    uid = decoded.get("uid")
    email = decoded.get("email") or decoded.get("firebase", {}).get("identities", {}).get("email", [None])[0]
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")
    if not email:
        email = f"{uid}@firebase.local"

    provided_name = body.display_name or decoded.get("name")
    member = await get_or_create_member(
        db,
        firebase_uid=uid,
        email=email,
        display_name=provided_name,
    )
    await db.flush()

    # Check for pending invites and freeze their timers
    has_pending_invites = False
    invite_result = await db.execute(
        select(OrganizationInvite)
        .where(OrganizationInvite.email == member.email, OrganizationInvite.status == "pending")
    )
    if invite_result.scalars().first() is not None:
        has_pending_invites = True
        await db.execute(
            update(OrganizationInvite)
            .where(OrganizationInvite.email == member.email, OrganizationInvite.status == "pending")
            .values(expires_at=datetime(2099, 12, 31, tzinfo=timezone.utc).replace(tzinfo=None))
        )
        await db.flush()

    # Check SuperAdmin first
    admin_result = await db.execute(select(SuperAdmin).where(SuperAdmin.member_id == member.id))
    if admin_result.scalars().first():
        org_id = None
        level_of_access = "super_admin"
    else:
        # Check OrganizationMember
        result = await db.execute(
            select(OrganizationMember)
            .where(OrganizationMember.member_id == member.id)
            .limit(1)
        )
        row = result.scalars().first()
        if row:
            org_id = str(row.organization_id)
            level_of_access = row.role
        else:
            org_id = None
            level_of_access = "guest"

    token = issue_control_jwt(sub=str(member.id), org_id=org_id, level_of_access=level_of_access)
    return AuthExchangeResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=settings.JWT_EXPIRATION_MINUTES * 60,
        has_pending_invites=has_pending_invites,
    )
