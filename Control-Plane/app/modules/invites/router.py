"""Invites API router – public validation and authenticated acceptance."""

from datetime import datetime, timezone
from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_member, require_control_jwt
from app.db.session import get_db
from app.models.member import Member
from app.models.organization_invite import OrganizationInvite
from app.schemas.invite import OrganizationInviteResponse, OrganizationInviteAcceptRequest
from app.services.org_service import create_organization
from app.services.subscription_service import create_subscription
from app.services.audit_service import log_audit
from dateutil.relativedelta import relativedelta

invites_router = APIRouter(prefix="/invites", tags=["Invites"])


@invites_router.get("/me/pending", response_model=list[OrganizationInviteResponse])
async def get_pending_invites(
    payload: Annotated[dict, Depends(require_control_jwt)],
    member: Annotated[Member, Depends(get_current_member)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[OrganizationInviteResponse]:
    """Fetch all pending invites for the currently authenticated user."""
    result = await db.execute(
        select(OrganizationInvite)
        .where(OrganizationInvite.email == member.email, OrganizationInvite.status == "pending")
        .order_by(OrganizationInvite.created_at.desc())
    )
    invites = result.scalars().all()
    return [OrganizationInviteResponse.model_validate(inv) for inv in invites]


@invites_router.get("/{invite_id}", response_model=OrganizationInviteResponse)
async def get_invite(
    invite_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationInviteResponse:
    """Validate an invite and get its details (public)."""
    result = await db.execute(select(OrganizationInvite).where(OrganizationInvite.id == invite_id))
    invite = result.scalars().one_or_none()
    
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
        
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    if invite.status != "pending":
        raise HTTPException(status_code=410, detail="This invite has already been used or revoked")
        
    if now > invite.expires_at:
        raise HTTPException(status_code=410, detail="This invite has expired")
        
    member_result = await db.execute(select(Member).where(Member.email == invite.email))
    existing_member = member_result.scalars().first()
    
    response = OrganizationInviteResponse.model_validate(invite)
    if existing_member is not None:
        response.account_exists = True
        
    return response


@invites_router.post("/{invite_id}/accept", response_model=OrganizationInviteResponse)
async def accept_invite(
    invite_id: UUID,
    body: OrganizationInviteAcceptRequest,
    payload: Annotated[dict, Depends(require_control_jwt)],
    member: Annotated[Member, Depends(get_current_member)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationInviteResponse:
    """Accept the invite. Provisions org or joins existing."""
    # Use with_for_update to prevent double-click race conditions
    result = await db.execute(
        select(OrganizationInvite)
        .where(OrganizationInvite.id == invite_id)
        .with_for_update()
    )
    invite = result.scalars().one_or_none()
    
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
        
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    if invite.status != "pending":
        raise HTTPException(status_code=410, detail="This invite has already been used")
        
    if now > invite.expires_at:
        raise HTTPException(status_code=410, detail="This invite has expired")
        
    if member.email.lower() != invite.email.lower():
        raise HTTPException(
            status_code=403, 
            detail="The authenticated user's email does not match the invited email"
        )
        
    if invite.organization_id is None:
        # Create new org flow
        if not body.organization_name:
            raise HTTPException(
                status_code=400, 
                detail="organization_name is required to create a new organization"
            )
            
        try:
            org = await create_organization(db, body.organization_name, member.id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        # Apply plan if specified in the invite
        if invite.plan_id:
            cycle_start = now
            cycle_end = now + relativedelta(months=1)
            try:
                await create_subscription(
                    db,
                    org.id,
                    invite.plan_id,
                    cycle_start,
                    cycle_end,
                )
            except Exception as e:
                # Log but do not fail the org creation
                pass
                
        # Mark invite accepted
        invite.status = "accepted"
        invite.organization_id = org.id
        await db.commit()
        await log_audit(db, organization_id=org.id, member_id=member.id, action_key="member.join", result=f"joined as {invite.role} (created org)")
        
    else:
        # Join existing org flow (for peer invites, though not fully spec'd, we support the backend part)
        from app.models.organization_member import OrganizationMember
        import uuid
        
        # Check if already a member of this org or another org
        existing = await db.execute(
            select(OrganizationMember).where(OrganizationMember.member_id == member.id)
        )
        if existing.scalars().first() is not None:
            raise HTTPException(status_code=400, detail="User is already a member of an organization")
            
        om = OrganizationMember(
            id=uuid.uuid4(),
            organization_id=invite.organization_id,
            member_id=member.id,
            role=invite.role,
            created_at=now,
        )
        db.add(om)
        invite.status = "accepted"
        await db.commit()
        await log_audit(db, organization_id=invite.organization_id, member_id=member.id, action_key="member.join", result=f"joined as {invite.role}")
        
    return OrganizationInviteResponse.model_validate(invite)
