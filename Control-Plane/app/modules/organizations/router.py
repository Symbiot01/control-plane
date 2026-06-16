"""Organization routes."""

from uuid import UUID
from typing import Annotated
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ROLES
from app.core.dependencies import (
    get_current_member,
    rate_limit_per_org,
    require_org_owner_for_path,
    require_org_member_for_path,
)
from app.db.session import get_db
from app.core.config import settings
from app.models.member import Member
from app.models.organization import Organization
from app.models.organization_invite import OrganizationInvite
from app.models.organization_member import OrganizationMember
from app.schemas.invite import OrganizationInviteResponse
from app.schemas.organization import (
    InviteMemberRequest,
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationProductResponse,
    OrganizationResponse,
    OrganizationWithRole,
    UpdateMemberRoleRequest,
    OrganizationMemberResponse,
    PendingInviteResponse,
    AuditLogResponse,
)
from app.services.audit_service import log_audit, get_organization_audit_logs
from app.services.org_service import (
    create_organization,
    get_organization,
    list_organizations_for_member,
    update_member_role,
    remove_member,
    get_organization_members,
    get_pending_invites,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])



@router.get("/me", response_model=list[OrganizationWithRole])
async def get_organizations_me(
    db: Annotated[AsyncSession, Depends(get_db)],
    member: Annotated[Member, Depends(get_current_member)],
    _rl: Annotated[None, Depends(rate_limit_per_org)],
):
    """List organizations for current member with role."""
    pairs = await list_organizations_for_member(db, member.id)
    out = []
    for org, role in pairs:
        data = OrganizationResponse.model_validate(org)
        out.append(OrganizationWithRole(**data.model_dump(), role=role))
    return out


@router.get("/{org_id}/products", response_model=list[OrganizationProductResponse])
async def get_organization_products(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    membership: Annotated[OrganizationMember, Depends(require_org_member_for_path)],
):
    """Get all products this organization is entitled to use."""
    from app.models.organization_entitlement import OrganizationEntitlement
    from app.models.product import Product
    
    result = await db.execute(
        select(OrganizationEntitlement, Product)
        .join(Product, OrganizationEntitlement.product_id == Product.id)
        .where(OrganizationEntitlement.organization_id == org_id)
    )
    
    products = []
    for ent, prod in result.all():
        products.append(
            OrganizationProductResponse(
                product_key=prod.product_key,
                name=prod.name,
                description=prod.description,
                product_link=prod.product_link,
                is_active=prod.is_active,
                expires_at=ent.expires_at,
                max_compute_units=ent.max_compute_units,
            )
        )
    return products


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization_by_id(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    membership: Annotated[OrganizationMember, Depends(require_org_member_for_path)],
    _rl: Annotated[None, Depends(rate_limit_per_org)],
):
    """Get organization by id; requires membership (path org_id must match JWT org_id)."""
    org = await get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return OrganizationResponse.model_validate(org)


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization_info(
    org_id: UUID,
    body: OrganizationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    membership: Annotated[OrganizationMember, Depends(require_org_owner_for_path)],
    _rl: Annotated[None, Depends(rate_limit_per_org)],
):
    """Update organization name and slug (owner only)."""
    org = await get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
        
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    updates = {"updated_at": now}
    
    if body.name is not None:
        updates["name"] = body.name
        
    if len(updates) > 1:
        await db.execute(update(Organization).where(Organization.id == org_id).values(**updates))
        await db.commit()
        await log_audit(db, organization_id=org_id, member_id=membership.member_id, action_key="org.update", result="updated")
        
    updated_org = await get_organization(db, org_id)
    return OrganizationResponse.model_validate(updated_org)


@router.post("/{org_id}/invite", response_model=OrganizationInviteResponse)
async def post_organizations_invite(
    org_id: UUID,
    body: InviteMemberRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    membership: Annotated[OrganizationMember, Depends(require_org_owner_for_path)],
    _rl: Annotated[None, Depends(rate_limit_per_org)],
):
    """Invite member by email (admin/owner only)."""
    if body.role not in ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
        
    existing_invite = await db.execute(
        select(OrganizationInvite)
        .where(
            OrganizationInvite.email == body.email,
            OrganizationInvite.organization_id == org_id,
            OrganizationInvite.status == "pending"
        )
    )
    if existing_invite.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An active invite already exists for this email in this organization")
    
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_at = now + timedelta(hours=body.expiration_hours)
    
    invite = OrganizationInvite(
        email=body.email,
        organization_id=org_id,
        plan_id=None,
        role=body.role,
        status="pending",
        invited_by=membership.member_id,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(invite)
    await db.commit()
    await log_audit(db, organization_id=org_id, member_id=membership.member_id, action_key="member.invite", result=f"invited {body.email}")
    
    invite_url = f"{settings.ORG_CONSOLE_URL}/invite?token={invite.id}"
    
    response = OrganizationInviteResponse.model_validate(invite)
    response.invite_url = invite_url
    return response


@router.patch("/{org_id}/member/{member_id}")
async def patch_organizations_member(
    org_id: UUID,
    member_id: UUID,
    body: UpdateMemberRoleRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    membership: Annotated[OrganizationMember, Depends(require_org_owner_for_path)],
    _rl: Annotated[None, Depends(rate_limit_per_org)],
):
    """Update member role (admin/owner only); cannot demote last owner."""
    if body.role not in ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    updated = await update_member_role(db, org_id, member_id, body.role)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot demote last owner or member not found",
        )
    await log_audit(db, organization_id=org_id, member_id=membership.member_id, action_key="member.role_update", result="updated")
    return {"status": "updated", "member_id": str(member_id), "role": body.role}


@router.delete("/{org_id}/member/{member_id}")
async def delete_organizations_member(
    org_id: UUID,
    member_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    membership: Annotated[OrganizationMember, Depends(require_org_owner_for_path)],
    _rl: Annotated[None, Depends(rate_limit_per_org)],
):
    """Remove member from org (admin/owner only); cannot remove last owner."""
    ok = await remove_member(db, org_id, member_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot remove last owner",
        )
    await log_audit(db, organization_id=org_id, member_id=membership.member_id, action_key="member.remove", result="removed")
    return {"status": "removed", "member_id": str(member_id)}


@router.get("/{org_id}/members", response_model=list[OrganizationMemberResponse])
async def get_org_members(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    membership: Annotated[OrganizationMember, Depends(require_org_member_for_path)],
    _rl: Annotated[None, Depends(rate_limit_per_org)],
):
    """List all members of the org. Restricted to owner and admin."""
    if membership.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role to view members",
        )
    members_data = await get_organization_members(db, org_id)
    return [
        OrganizationMemberResponse(
            id=m.id,
            email=m.email,
            display_name=m.display_name,
            role=role,
            created_at=m.created_at,
        )
        for m, role in members_data
    ]


@router.get("/{org_id}/invites", response_model=list[PendingInviteResponse])
async def get_org_invites(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    membership: Annotated[OrganizationMember, Depends(require_org_owner_for_path)],
    _rl: Annotated[None, Depends(rate_limit_per_org)],
):
    """List all pending invites for the org (owner only)."""
    invites = await get_pending_invites(db, org_id)
    return [
        PendingInviteResponse.model_validate(invite)
        for invite in invites
    ]


@router.get("/{org_id}/audit-logs", response_model=list[AuditLogResponse])
async def get_org_audit_logs(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    membership: Annotated[OrganizationMember, Depends(require_org_owner_for_path)],
    _rl: Annotated[None, Depends(rate_limit_per_org)],
):
    """List recent audit logs for the org (owner only)."""
    logs = await get_organization_audit_logs(db, org_id)
    return [
        AuditLogResponse.model_validate(log)
        for log in logs
    ]

