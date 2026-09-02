"""Organization routes."""

from uuid import UUID
from typing import Annotated
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ROLE_OWNER, ROLES
from app.core.dependencies import (
    get_current_member,
    rate_limit_per_org,
    require_org_owner_for_path,
    require_org_member_for_path,
    require_org_operator_for_path,
    require_control_jwt,
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
    OrganizationProductAccessResponse,
    OrganizationDeliverableResponse,
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
    membership: Annotated[OrganizationMember, Depends(require_org_operator_for_path)],
):
    """Get all products this organization is entitled to use. Owner/member only (not viewer)."""
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
                is_active=prod.is_active,
                expires_at=ent.expires_at,
                max_compute_units=ent.max_compute_units,
            )
        )
    return products


@router.get("/{org_id}/deliverables", response_model=list[OrganizationDeliverableResponse])
async def get_organization_deliverables(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    membership: Annotated[OrganizationMember, Depends(require_org_operator_for_path)],
):
    """Get all unique deliverables this organization has access to."""
    from app.models.organization_entitlement import OrganizationEntitlement
    from app.models.product import Product
    from app.models.deliverable import Deliverable
    
    result = await db.execute(
        select(Deliverable)
        .join(Product, Product.deliverable_id == Deliverable.id)
        .join(OrganizationEntitlement, OrganizationEntitlement.product_id == Product.id)
        .where(OrganizationEntitlement.organization_id == org_id)
        .group_by(Deliverable.id)
    )
    
    deliverables = []
    for dev in result.scalars().all():
        deliverables.append(
            OrganizationDeliverableResponse(
                id=dev.id,
                name=dev.name,
                description=dev.description,
                deliverable_link=dev.deliverable_link,
                created_at=dev.created_at,
            )
        )
    return deliverables


@router.get("/my-access/{product_key}", response_model=OrganizationProductAccessResponse)
async def get_my_product_access(
    product_key: str,
    payload: Annotated[dict, Depends(require_control_jwt)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Check if the currently authenticated user's organization has access to a specific product."""
    org_id_str = payload.get("org_id")
    if not org_id_str:
        return OrganizationProductAccessResponse(
            has_access=False,
            reason="This is a guest account with no access. Please create or join an organization.",
            expires_at=None,
        )

    try:
        org_id = UUID(org_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID format in token")

    from app.models.organization_entitlement import OrganizationEntitlement
    from app.models.product import Product

    result = await db.execute(
        select(OrganizationEntitlement)
        .join(Product, OrganizationEntitlement.product_id == Product.id)
        .where(
            OrganizationEntitlement.organization_id == org_id,
            Product.product_key == product_key,
            Product.is_active == True
        )
    )
    entitlement = result.scalars().first()

    if not entitlement:
        return OrganizationProductAccessResponse(
            has_access=False,
            reason="Your organization does not have access to this product.",
            expires_at=None,
        )

    return OrganizationProductAccessResponse(
        has_access=True,
        reason="Access granted.",
        expires_at=entitlement.expires_at,
    )


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
        
    body.email = body.email.lower()
        
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    existing_invite = await db.execute(
        select(OrganizationInvite)
        .where(
            OrganizationInvite.email == body.email,
            OrganizationInvite.organization_id == org_id,
            OrganizationInvite.status == "pending",
            OrganizationInvite.expires_at > now
        )
    )
    if existing_invite.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An active invite already exists for this email in this organization")
    
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
    
    # Send email
    from app.services.email_service import send_invite_email
    from app.services.org_service import get_organization
    from app.models.member import Member
    
    org = await get_organization(db, org_id)
    inviter_res = await db.execute(select(Member).where(Member.id == membership.member_id))
    inviter = inviter_res.scalars().first()
    
    inviter_name = inviter.display_name if inviter and inviter.display_name else inviter.email if inviter else "An admin"
    org_name = org.name if org else "the organization"
    
    await send_invite_email(
        to_email=body.email,
        invite_url=invite_url,
        inviter_name=inviter_name,
        role=body.role,
        expires_at=expires_at,
        org_name=org_name
    )
    
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
    """List all members of the org. Restricted to owner."""
    if membership.role != ROLE_OWNER:
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

@router.delete("/{org_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organizations_invite(
    org_id: UUID,
    invite_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    membership: Annotated[OrganizationMember, Depends(require_org_owner_for_path)],
):
    """Revoke a pending invite (owner only)."""
    result = await db.execute(
        select(OrganizationInvite).where(
            OrganizationInvite.id == invite_id,
            OrganizationInvite.organization_id == org_id,
            OrganizationInvite.status == "pending"
        )
    )
    invite = result.scalars().first()
    
    if not invite:
        raise HTTPException(status_code=404, detail="Pending invite not found")
        
    await db.delete(invite)
    await db.commit()
    await log_audit(db, organization_id=org_id, member_id=membership.member_id, action_key="member.invite_revoked", result=f"revoked invite for {invite.email}")


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

