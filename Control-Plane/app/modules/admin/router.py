"""Admin API router – all /admin/v1/* endpoints. Requires super admin."""

from datetime import datetime, timezone
from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import (
    INVOICE_STATUS_DRAFT,
    INVOICE_STATUS_OVERDUE,
    ORG_STATUS_ACTIVE,
    ORG_STATUS_ARCHIVED,
    ORG_STATUS_SUSPENDED,
    SUBSCRIPTION_STATUS_ACTIVE,
    SUBSCRIPTION_STATUS_CANCELED,
)
from app.db.session import get_db
from app.models.credit_ledger import CreditLedger
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.member import Member
from app.models.organization import Organization
from app.models.organization_entitlement import OrganizationEntitlement
from app.models.organization_member import OrganizationMember
from app.models.organization_subscription import OrganizationSubscription
from app.models.plan import Plan
from app.models.product import Product
from app.models.quota_action import QuotaAction
from app.models.quota_action_price import QuotaActionPrice
from app.services.org_service import create_organization, update_member_role
from app.services.credit_service import grant_credits
from app.services.invoice_service import generate_invoice_for_org, set_org_suspended_for_invoice
from app.services.subscription_service import (
    change_plan as sub_change_plan,
    create_subscription,
    get_current_subscription,
    update_subscription_status,
)

from app.core.firebase import delete_firebase_user
from app.modules.admin.audit import log_admin_action
from app.modules.admin.dependencies import require_super_admin
from app.modules.admin.models import SuperAdmin, SuperAdminAuditLog
from app.modules.admin.schemas import (
    AdminAuditLogParams,
    AdminAuditLogResponse,
    AdminInvoiceResponse,
    AdminInvoiceLineItemResponse,
    AdminOrgCreate,
    AdminOrgListParams,
    AdminOrgResponse,
    AdminOrgUpdate,
    AdminStatsResponse,
    AdminActionCreate,
    AdminActionResponse,
    AdminActionUpdate,
    CreditBalanceResponse,
    CreditGrantRequest,
    CreditLedgerEntry,
    GlobalMemberResponse,
    GlobalMemberRoleUpdate,
    InvoiceGenerateRequest,
    InvoicePaymentUpdate,
    SuperAdminCreate,
    SuperAdminResponse,
    PlanUpdate,
    ProductResponse,
    ProductCreate,
    ProductUpdate,
    EntitlementGrantRequest,
    SubscriptionChangePlanRequest,
    SubscriptionStatusUpdate,
)
from app.schemas.billing import (
    InvoiceStatusUpdate,
    PlanCreate,
    PlanResponse,
    SubscriptionCreate,
    SubscriptionResponse,
)
from app.schemas.usage import UsageSummaryResponse
from app.services.usage_summary_service import (
    resolve_usage_period,
    summarize_usage_for_org,
)

admin_router = APIRouter(dependencies=[Depends(require_super_admin)])


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# --- Block 14: Stats ---


@admin_router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminStatsResponse:
    """Dashboard counters."""
    total_orgs = (await db.execute(select(func.count()).select_from(Organization))).scalar() or 0
    active_orgs = (
        await db.execute(
            select(func.count()).select_from(Organization).where(Organization.status == ORG_STATUS_ACTIVE)
        )
    ).scalar() or 0
    suspended_orgs = (
        await db.execute(
            select(func.count()).select_from(Organization).where(Organization.status == ORG_STATUS_SUSPENDED)
        )
    ).scalar() or 0
    archived_orgs = (
        await db.execute(
            select(func.count()).select_from(Organization).where(Organization.status == ORG_STATUS_ARCHIVED)
        )
    ).scalar() or 0
    active_subs = (
        await db.execute(
            select(func.count()).select_from(OrganizationSubscription).where(
                OrganizationSubscription.status == SUBSCRIPTION_STATUS_ACTIVE
            )
        )
    ).scalar() or 0
    draft_inv = (
        await db.execute(
            select(func.count()).select_from(Invoice).where(Invoice.status == INVOICE_STATUS_DRAFT)
        )
    ).scalar() or 0
    overdue_inv = (
        await db.execute(
            select(func.count()).select_from(Invoice).where(Invoice.status == INVOICE_STATUS_OVERDUE)
        )
    ).scalar() or 0
    total_members = (await db.execute(select(func.count()).select_from(Member))).scalar() or 0
    return AdminStatsResponse(
        total_orgs=total_orgs,
        active_orgs=active_orgs,
        suspended_orgs=suspended_orgs,
        archived_orgs=archived_orgs,
        active_subscriptions=active_subs,
        draft_invoices=draft_inv,
        overdue_invoices=overdue_inv,
        total_members=total_members,
    )


# --- Block 15: Global Members ---


@admin_router.get("/members", response_model=list[GlobalMemberResponse])
async def list_global_members(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[GlobalMemberResponse]:
    """List all accounts in the system."""
    q = (
        select(Member, OrganizationMember, SuperAdmin)
        .outerjoin(OrganizationMember, Member.id == OrganizationMember.member_id)
        .outerjoin(SuperAdmin, Member.id == SuperAdmin.member_id)
        .order_by(Member.created_at.desc())
    )
    if search:
        q = q.where(
            (Member.email.ilike(f"%{search}%")) | (Member.display_name.ilike(f"%{search}%"))
        )
    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    rows = result.all()
    
    out = []
    for m, om, pa in rows:
        if pa is not None:
            global_role = "super_admin"
        elif om is not None:
            global_role = om.role
        else:
            global_role = "guest"
            
        out.append(
            GlobalMemberResponse(
                member_id=m.id,
                email=m.email,
                display_name=m.display_name,
                organization_id=om.organization_id if om else None,
                global_role=global_role,
                created_at=m.created_at,
            )
        )
    return out


@admin_router.patch("/members/{member_id}/role", response_model=GlobalMemberResponse)
async def update_global_member_role(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    member_id: UUID,
    body: GlobalMemberRoleUpdate,
) -> GlobalMemberResponse:
    """Update role (owner/member only). Rejects super_admin."""
    if body.role not in ("owner", "member"):
        raise HTTPException(status_code=400, detail="Role must be 'owner' or 'member'")

    # Check if they belong to an org
    result = await db.execute(select(OrganizationMember).where(OrganizationMember.member_id == member_id))
    om = result.scalars().one_or_none()
    
    if not om:
        if not body.organization_id:
            raise HTTPException(status_code=400, detail="User does not belong to an organization. Provide organization_id to assign them.")
            
        # Verify the organization exists
        from app.models.organization import Organization
        org_res = await db.execute(select(Organization).where(Organization.id == body.organization_id))
        if not org_res.scalars().first():
            raise HTTPException(status_code=404, detail="Organization not found")
            
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        new_om = OrganizationMember(
            organization_id=body.organization_id,
            member_id=member_id,
            role=body.role,
            created_at=now,
        )
        db.add(new_om)
        await db.commit()
        await log_admin_action(db, admin.id, "member.assign_org", "member", member_id, detail=f"Assigned to org {body.organization_id} as {body.role}")
        
    else:
        if body.organization_id and body.organization_id != om.organization_id:
            raise HTTPException(status_code=400, detail="User already belongs to a different organization.")
            
        org_id = om.organization_id
        
        try:
            updated = await update_member_role(db, org_id, member_id, body.role)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        await db.commit()
        await log_admin_action(db, admin.id, "member.update_role", "member", member_id, detail=f"New role: {body.role}")
    
    # Reload to build response
    q = (
        select(Member, OrganizationMember, SuperAdmin)
        .outerjoin(OrganizationMember, Member.id == OrganizationMember.member_id)
        .outerjoin(SuperAdmin, Member.id == SuperAdmin.member_id)
        .where(Member.id == member_id)
    )
    result = await db.execute(q)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Member not found")
        
    m, om, pa = row
    if pa is not None:
        global_role = "super_admin"
    elif om is not None:
        global_role = om.role
    else:
        global_role = "guest"
        
    return GlobalMemberResponse(
        member_id=m.id,
        email=m.email,
        display_name=m.display_name,
        organization_id=om.organization_id if om else None,
        global_role=global_role,
        created_at=m.created_at,
    )


@admin_router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    member_id: UUID,
) -> None:
    """Delete a member and their Firebase account."""
    # Check if member exists
    result = await db.execute(select(Member).where(Member.id == member_id))
    member = result.scalars().one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
        
    # Prevent deleting super admins
    sa_result = await db.execute(select(SuperAdmin).where(SuperAdmin.member_id == member_id))
    if sa_result.scalars().one_or_none():
        raise HTTPException(status_code=400, detail="Cannot delete super admin accounts")
        
    firebase_uid = member.firebase_uid
    member_email = member.email
    
    await db.delete(member)
    await db.commit()
    
    # Try to delete from Firebase
    try:
        delete_firebase_user(firebase_uid)
    except Exception as e:
        print(f"Warning: Failed to delete firebase user {firebase_uid}: {e}")
        
    await log_admin_action(db, admin.id, "member.delete", "member", member_id, detail=f"Deleted user {member_email}")


# --- Block 7: Organizations ---


@admin_router.get("/organizations", response_model=list[AdminOrgResponse])
async def list_organizations(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None),
    search: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[AdminOrgResponse]:
    """List all orgs with optional filters and pagination."""
    q = select(Organization).options(selectinload(Organization.entitlements).selectinload(OrganizationEntitlement.product)).order_by(Organization.created_at.desc())
    if status:
        q = q.where(Organization.status == status)
    if search:
        q = q.where(
            (Organization.name.ilike(f"%{search}%")) | (Organization.slug.ilike(f"%{search}%"))
        )
    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    orgs = result.scalars().all()
    out = []
    for org in orgs:
        count_result = await db.execute(
            select(func.count()).select_from(OrganizationMember).where(
                OrganizationMember.organization_id == org.id
            )
        )
        members_count = count_result.scalar() or 0
        out.append(
            AdminOrgResponse(
                id=org.id,
                name=org.name,
                slug=org.slug,
                status=org.status,
                tier=org.tier,
                prepaid_balance_cents=int(org.prepaid_balance_cents or 0),
                billing_mode=org.billing_mode,
                overdraft_limit_cents=int(org.overdraft_limit_cents or 0),
                members_count=members_count,
        entitlements=org.entitlements,
                created_at=org.created_at,
                updated_at=org.updated_at,
            )
        )
    return out


@admin_router.post("/organizations", response_model=AdminOrgResponse)
async def create_organization_super_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: AdminOrgCreate,
) -> AdminOrgResponse:
    """Create a new organization and assign owner by email."""
    # Lookup member by email
    result = await db.execute(select(Member).where(Member.email == body.owner_email))
    target_member = result.scalars().one_or_none()
    if not target_member:
        raise HTTPException(
            status_code=400,
            detail=f"User with email {body.owner_email} not found. They must sign up first."
        )

    slug = body.slug if body.slug else None
    try:
        org = await create_organization(db, body.name, target_member.id, slug=slug)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await log_admin_action(
        db,
        admin_member_id=admin.id,
        action="organization.create",
        target_type="organization",
        target_id=org.id,
        detail=f"Created organization assigned to {body.owner_email}",
    )

    return AdminOrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        status=org.status,
        tier=org.tier,
        prepaid_balance_cents=int(org.prepaid_balance_cents or 0),
        billing_mode=org.billing_mode,
        overdraft_limit_cents=int(org.overdraft_limit_cents or 0),
        members_count=1,
        entitlements=org.entitlements,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@admin_router.get("/organizations/{org_id}", response_model=AdminOrgResponse)
async def get_organization(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
) -> AdminOrgResponse:
    """Org detail with members count."""
    result = await db.execute(select(Organization).options(selectinload(Organization.entitlements).selectinload(OrganizationEntitlement.product)).where(Organization.id == org_id))
    org = result.scalars().one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    count_result = await db.execute(
        select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.organization_id == org.id
        )
    )
    members_count = count_result.scalar() or 0
    return AdminOrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        status=org.status,
        tier=org.tier,
        prepaid_balance_cents=int(org.prepaid_balance_cents or 0),
        billing_mode=org.billing_mode,
        overdraft_limit_cents=int(org.overdraft_limit_cents or 0),
        members_count=members_count,
        entitlements=org.entitlements,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@admin_router.get("/organizations/{org_id}/usage/summary", response_model=UsageSummaryResponse)
async def get_usage_summary_admin(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
    from_dt: datetime | None = Query(None, alias="from", description="Period start (UTC); use with to"),
    to_dt: datetime | None = Query(None, alias="to", description="Period end (exclusive, UTC); use with from"),
) -> UsageSummaryResponse:
    """Aggregated usage from usage_ledger for [from, to). Defaults to last 30 days when both omitted."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    if result.scalars().one_or_none() is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    try:
        period_start, period_end = resolve_usage_period(from_dt, to_dt)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return await summarize_usage_for_org(db, org_id, period_start, period_end)


@admin_router.patch("/organizations/{org_id}", response_model=AdminOrgResponse)
async def update_organization(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
    body: AdminOrgUpdate,
) -> AdminOrgResponse:
    """Update org status, tier, billing_mode, overdraft_limit_cents."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalars().one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    updates = {"updated_at": now}
    if body.status is not None:
        updates["status"] = body.status
    if body.tier is not None:
        updates["tier"] = body.tier
    if body.billing_mode is not None:
        updates["billing_mode"] = body.billing_mode
    if body.overdraft_limit_cents is not None:
        updates["overdraft_limit_cents"] = body.overdraft_limit_cents
    await db.execute(update(Organization).where(Organization.id == org_id).values(**updates))
    await db.commit()
    await log_admin_action(db, admin.id, "org.update", "organization", org_id)
    result = await db.execute(select(Organization).options(selectinload(Organization.entitlements).selectinload(OrganizationEntitlement.product)).where(Organization.id == org_id))
    org = result.scalars().one()
    count_result = await db.execute(
        select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.organization_id == org.id
        )
    )
    members_count = count_result.scalar() or 0
    return AdminOrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        status=org.status,
        tier=org.tier,
        prepaid_balance_cents=int(org.prepaid_balance_cents or 0),
        billing_mode=org.billing_mode,
        overdraft_limit_cents=int(org.overdraft_limit_cents or 0),
        members_count=members_count,
        entitlements=org.entitlements,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@admin_router.patch("/organizations/{org_id}/suspend", response_model=AdminOrgResponse)
async def suspend_organization(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
) -> AdminOrgResponse:
    """Set org status to suspended."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalars().one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        update(Organization).where(Organization.id == org_id).values(status=ORG_STATUS_SUSPENDED, updated_at=now)
    )
    await db.commit()
    await log_admin_action(db, admin.id, "org.suspend", "organization", org_id)
    result = await db.execute(select(Organization).options(selectinload(Organization.entitlements).selectinload(OrganizationEntitlement.product)).where(Organization.id == org_id))
    org = result.scalars().one()
    count_result = await db.execute(
        select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.organization_id == org.id
        )
    )
    members_count = count_result.scalar() or 0
    return AdminOrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        status=org.status,
        tier=org.tier,
        prepaid_balance_cents=int(org.prepaid_balance_cents or 0),
        billing_mode=org.billing_mode,
        overdraft_limit_cents=int(org.overdraft_limit_cents or 0),
        members_count=members_count,
        entitlements=org.entitlements,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@admin_router.patch("/organizations/{org_id}/activate", response_model=AdminOrgResponse)
async def activate_organization(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
) -> AdminOrgResponse:
    """Set org status to active."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalars().one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        update(Organization).where(Organization.id == org_id).values(status=ORG_STATUS_ACTIVE, updated_at=now)
    )
    await db.commit()
    await log_admin_action(db, admin.id, "org.activate", "organization", org_id)
    result = await db.execute(select(Organization).options(selectinload(Organization.entitlements).selectinload(OrganizationEntitlement.product)).where(Organization.id == org_id))
    org = result.scalars().one()
    count_result = await db.execute(
        select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.organization_id == org.id
        )
    )
    members_count = count_result.scalar() or 0
    return AdminOrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        status=org.status,
        tier=org.tier,
        prepaid_balance_cents=int(org.prepaid_balance_cents or 0),
        billing_mode=org.billing_mode,
        overdraft_limit_cents=int(org.overdraft_limit_cents or 0),
        members_count=members_count,
        entitlements=org.entitlements,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@admin_router.delete("/organizations/{org_id}/scrub", response_model=AdminOrgResponse)
async def scrub_organization(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
) -> AdminOrgResponse:
    """Scrub delete org: anonymize, remove members, cancel subs, set archived."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalars().one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    import uuid
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    random_suffix = uuid.uuid4().hex[:8]
    
    # 1. Anonymize name and slug, set status
    updates = {
        "name": f"Deleted Org {random_suffix}",
        "slug": f"deleted-org-{random_suffix}",
        "status": ORG_STATUS_ARCHIVED,
        "updated_at": now
    }
    await db.execute(update(Organization).where(Organization.id == org_id).values(**updates))
    
    # 2. Remove all members
    await db.execute(delete(OrganizationMember).where(OrganizationMember.organization_id == org_id))
    
    # 3. Cancel all active subscriptions
    active_subs = await db.execute(
        select(OrganizationSubscription).where(
            OrganizationSubscription.organization_id == org_id,
            OrganizationSubscription.status == SUBSCRIPTION_STATUS_ACTIVE
        )
    )
    for sub in active_subs.scalars().all():
        await update_subscription_status(db, sub.id, SUBSCRIPTION_STATUS_CANCELED)
        
    await db.commit()
    await log_admin_action(db, admin.id, "org.scrub", "organization", org_id)
    
    # Reload for response
    result = await db.execute(select(Organization).options(selectinload(Organization.entitlements).selectinload(OrganizationEntitlement.product)).where(Organization.id == org_id))
    org = result.scalars().one()
    
    return AdminOrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        status=org.status,
        tier=org.tier,
        prepaid_balance_cents=int(org.prepaid_balance_cents or 0),
        billing_mode=org.billing_mode,
        overdraft_limit_cents=int(org.overdraft_limit_cents or 0),
        members_count=0,
        entitlements=org.entitlements,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@admin_router.delete("/organizations/{org_id}/hard", status_code=status.HTTP_204_NO_CONTENT)
async def hard_delete_organization(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
) -> None:
    """True hard delete. DESTROYS ALL RELATED DATA. For dev/test only."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalars().one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    await db.delete(org)
    await db.commit()
    await log_admin_action(db, admin.id, "org.hard_delete", "organization", org_id)


@admin_router.get("/organizations/{org_id}/members")
async def list_organization_members(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
) -> list[dict]:
    """List org members with roles."""
    result = await db.execute(
        select(OrganizationMember, Member)
        .join(Member, OrganizationMember.member_id == Member.id)
        .where(OrganizationMember.organization_id == org_id)
    )
    rows = result.all()
    return [
        {
            "member_id": om.member_id,
            "email": m.email,
            "display_name": m.display_name,
            "role": om.role,
        }
        for om, m in rows
    ]


# --- Block 8: Subscriptions ---


@admin_router.get("/organizations/{org_id}/subscriptions", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
) -> list[SubscriptionResponse]:
    """List all subscriptions for org."""
    result = await db.execute(
        select(OrganizationSubscription)
        .options(selectinload(OrganizationSubscription.plan))
        .where(OrganizationSubscription.organization_id == org_id)
        .order_by(OrganizationSubscription.billing_cycle_end.desc())
    )
    subs = result.scalars().all()
    return [SubscriptionResponse.model_validate(s) for s in subs]


@admin_router.get("/organizations/{org_id}/subscriptions/current", response_model=SubscriptionResponse | None)
async def get_current_subscription_admin(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
) -> SubscriptionResponse | None:
    """Current active subscription for org."""
    sub = await get_current_subscription(db, org_id)
    if sub is None:
        return None
    await db.refresh(sub, ["plan"])
    return SubscriptionResponse(
        id=sub.id,
        organization_id=sub.organization_id,
        plan_id=sub.plan_id,
        status=sub.status,
        billing_cycle_start=sub.billing_cycle_start,
        billing_cycle_end=sub.billing_cycle_end,
        created_at=sub.created_at,
        plan=PlanResponse.model_validate(sub.plan) if sub.plan else None,
    )


@admin_router.post("/organizations/{org_id}/subscriptions", response_model=SubscriptionResponse)
async def create_subscription_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
    body: SubscriptionCreate,
) -> SubscriptionResponse:
    """Create subscription for org."""
    try:
        sub = await create_subscription(
            db,
            org_id,
            body.plan_id,
            _naive_utc(body.billing_cycle_start),
            _naive_utc(body.billing_cycle_end),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    await log_admin_action(db, admin.id, "subscription.create", "subscription", sub.id, detail=str(org_id))
    await db.refresh(sub, ["plan"])
    return SubscriptionResponse(
        id=sub.id,
        organization_id=sub.organization_id,
        plan_id=sub.plan_id,
        status=sub.status,
        billing_cycle_start=sub.billing_cycle_start,
        billing_cycle_end=sub.billing_cycle_end,
        created_at=sub.created_at,
        plan=PlanResponse.model_validate(sub.plan) if sub.plan else None,
    )


@admin_router.patch("/subscriptions/{sub_id}/status", response_model=SubscriptionResponse | None)
async def update_subscription_status_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    sub_id: UUID,
    body: SubscriptionStatusUpdate,
) -> SubscriptionResponse | None:
    """Update subscription status (cancel, suspend, reactivate)."""
    sub = await update_subscription_status(db, sub_id, body.status)
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await db.commit()
    await log_admin_action(db, admin.id, "subscription.update_status", "subscription", sub_id, detail=body.status)
    await db.refresh(sub, ["plan"])
    return SubscriptionResponse(
        id=sub.id,
        organization_id=sub.organization_id,
        plan_id=sub.plan_id,
        status=sub.status,
        billing_cycle_start=sub.billing_cycle_start,
        billing_cycle_end=sub.billing_cycle_end,
        created_at=sub.created_at,
        plan=PlanResponse.model_validate(sub.plan) if sub.plan else None,
    )


@admin_router.post("/subscriptions/{sub_id}/change-plan", response_model=SubscriptionResponse)
async def change_plan_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    sub_id: UUID,
    body: SubscriptionChangePlanRequest,
) -> SubscriptionResponse:
    """Cancel current sub and create new one for new plan."""
    try:
        new_sub = await sub_change_plan(
            db,
            sub_id,
            body.new_plan_id,
            _naive_utc(body.new_billing_cycle_start),
            _naive_utc(body.new_billing_cycle_end),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    await log_admin_action(db, admin.id, "subscription.change_plan", "subscription", new_sub.id)
    await db.refresh(new_sub, ["plan"])
    return SubscriptionResponse(
        id=new_sub.id,
        organization_id=new_sub.organization_id,
        plan_id=new_sub.plan_id,
        status=new_sub.status,
        billing_cycle_start=new_sub.billing_cycle_start,
        billing_cycle_end=new_sub.billing_cycle_end,
        created_at=new_sub.created_at,
        plan=PlanResponse.model_validate(new_sub.plan) if new_sub.plan else None,
    )


# --- Block 9: Invoices ---


@admin_router.get("/organizations/{org_id}/invoices", response_model=list[AdminInvoiceResponse])
async def list_invoices_admin(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
    status: str | None = Query(None),
) -> list[AdminInvoiceResponse]:
    """List invoices for org, optional status filter."""
    q = select(Invoice).where(Invoice.organization_id == org_id).order_by(Invoice.created_at.desc())
    if status:
        q = q.where(Invoice.status == status)
    result = await db.execute(q)
    invoices = result.scalars().all()
    out = []
    for inv in invoices:
        items_result = await db.execute(select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == inv.id))
        items = items_result.scalars().all()
        out.append(
            AdminInvoiceResponse(
                id=inv.id,
                organization_id=inv.organization_id,
                billing_period_start=inv.billing_period_start,
                billing_period_end=inv.billing_period_end,
                total_compute_units=inv.total_compute_units,
                included_units=inv.included_units,
                overage_units=inv.overage_units,
                amount_due=inv.amount_due,
                credits_applied_cents=inv.credits_applied_cents,
                amount_paid_cents=inv.amount_paid_cents,
                status=inv.status,
                external_id=inv.external_id,
                created_at=inv.created_at,
                line_items=[AdminInvoiceLineItemResponse.model_validate(i) for i in items],
            )
        )
    return out


@admin_router.get("/invoices/{invoice_id}", response_model=AdminInvoiceResponse)
async def get_invoice_admin(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    invoice_id: UUID,
) -> AdminInvoiceResponse:
    """Invoice detail with line items."""
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    inv = result.scalars().one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    items_result = await db.execute(select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == inv.id))
    items = items_result.scalars().all()
    return AdminInvoiceResponse(
        id=inv.id,
        organization_id=inv.organization_id,
        billing_period_start=inv.billing_period_start,
        billing_period_end=inv.billing_period_end,
        total_compute_units=inv.total_compute_units,
        included_units=inv.included_units,
        overage_units=inv.overage_units,
        amount_due=inv.amount_due,
        credits_applied_cents=inv.credits_applied_cents,
        amount_paid_cents=inv.amount_paid_cents,
        status=inv.status,
        external_id=inv.external_id,
        created_at=inv.created_at,
        line_items=[AdminInvoiceLineItemResponse.model_validate(i) for i in items],
    )


@admin_router.post("/organizations/{org_id}/invoices/generate")
async def generate_invoice_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
    body: InvoiceGenerateRequest,
) -> dict:
    """Generate invoice for billing period."""
    try:
        inv_id = await generate_invoice_for_org(
            db,
            org_id,
            _naive_utc(body.billing_period_end),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    await log_admin_action(db, admin.id, "invoice.generate", "invoice", inv_id, detail=str(org_id))
    return {"invoice_id": inv_id}


@admin_router.patch("/invoices/{invoice_id}/status")
async def update_invoice_status_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    invoice_id: UUID,
    body: InvoiceStatusUpdate,
) -> dict:
    """Mark invoice sent/paid/overdue. On overdue, suspend org."""
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    inv = result.scalars().one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(update(Invoice).where(Invoice.id == invoice_id).values(status=body.status))
    if body.status == INVOICE_STATUS_OVERDUE:
        await set_org_suspended_for_invoice(db, invoice_id)
    await db.commit()
    await log_admin_action(db, admin.id, "invoice.update_status", "invoice", invoice_id, detail=body.status)
    return {"invoice_id": invoice_id, "status": body.status}


@admin_router.patch("/invoices/{invoice_id}/payment")
async def record_invoice_payment_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    invoice_id: UUID,
    body: InvoicePaymentUpdate,
) -> dict:
    """Record payment (amount_paid_cents, credits_applied_cents)."""
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    inv = result.scalars().one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    updates = {}
    if body.amount_paid_cents is not None:
        updates["amount_paid_cents"] = body.amount_paid_cents
    if body.credits_applied_cents is not None:
        updates["credits_applied_cents"] = body.credits_applied_cents
    if not updates:
        raise HTTPException(status_code=400, detail="Provide at least one of amount_paid_cents, credits_applied_cents")
    await db.execute(update(Invoice).where(Invoice.id == invoice_id).values(**updates))
    await db.commit()
    await log_admin_action(db, admin.id, "invoice.record_payment", "invoice", invoice_id)
    return {"invoice_id": invoice_id}


# --- Block 10: Credits ---


@admin_router.get("/organizations/{org_id}/credits", response_model=CreditBalanceResponse)
async def get_credits_admin(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
) -> CreditBalanceResponse:
    """Current balance and recent credit ledger."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalars().one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    ledger_result = await db.execute(
        select(CreditLedger)
        .where(CreditLedger.organization_id == org_id)
        .order_by(CreditLedger.created_at.desc())
        .limit(20)
    )
    recent = ledger_result.scalars().all()
    return CreditBalanceResponse(
        balance_cents=int(org.prepaid_balance_cents or 0),
        billing_mode=org.billing_mode,
        overdraft_limit_cents=int(org.overdraft_limit_cents or 0),
        recent_ledger=[CreditLedgerEntry.model_validate(e) for e in recent],
    )


@admin_router.post("/organizations/{org_id}/credits/grant")
async def grant_credits_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
    body: CreditGrantRequest,
) -> dict:
    """Grant/top-up credits."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    if result.scalars().one_or_none() is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    await grant_credits(db, org_id, body.amount_cents, type=body.type, reference_id=body.reference_id)
    await db.commit()
    await log_admin_action(
        db, admin.id, "credits.grant", "organization", org_id,
        detail=f"amount_cents={body.amount_cents} type={body.type}",
    )
    return {"organization_id": org_id, "amount_cents": body.amount_cents}


@admin_router.get("/organizations/{org_id}/credits/ledger", response_model=list[CreditLedgerEntry])
async def get_credits_ledger_admin(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[CreditLedgerEntry]:
    """Full credit ledger with pagination."""
    result = await db.execute(
        select(CreditLedger)
        .where(CreditLedger.organization_id == org_id)
        .order_by(CreditLedger.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.scalars().all()
    return [CreditLedgerEntry.model_validate(r) for r in rows]


# --- Block 11: Plans ---


@admin_router.get("/plans", response_model=list[PlanResponse])
async def list_plans_admin(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PlanResponse]:
    """List all plans."""
    result = await db.execute(select(Plan).order_by(Plan.name))
    plans = result.scalars().all()
    return [PlanResponse.model_validate(p) for p in plans]


@admin_router.post("/plans", response_model=PlanResponse)
async def create_plan_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: PlanCreate,
) -> PlanResponse:
    """Create plan."""
    from uuid import uuid4
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    plan = Plan(
        id=uuid4(),
        name=body.name,
        monthly_price=body.monthly_price,
        included_compute_units=body.included_compute_units,
        overage_rate=body.overage_rate,
        currency=body.currency,
        created_at=now,
    )
    db.add(plan)
    await db.flush()
    await db.commit()
    await log_admin_action(db, admin.id, "plan.create", "plan", plan.id)
    await db.refresh(plan)
    return PlanResponse.model_validate(plan)


@admin_router.patch("/plans/{plan_id}", response_model=PlanResponse)
async def update_plan_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    plan_id: UUID,
    body: PlanUpdate,
) -> PlanResponse:
    """Update plan fields."""
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalars().one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    updates = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.monthly_price is not None:
        updates["monthly_price"] = body.monthly_price
    if body.included_compute_units is not None:
        updates["included_compute_units"] = body.included_compute_units
    if body.overage_rate is not None:
        updates["overage_rate"] = body.overage_rate
    if body.currency is not None:
        updates["currency"] = body.currency
    if updates:
        await db.execute(update(Plan).where(Plan.id == plan_id).values(**updates))
        await db.commit()
        await log_admin_action(db, admin.id, "plan.update", "plan", plan_id)
        await db.refresh(plan)
    return PlanResponse.model_validate(plan)


# --- Block 12: Quota actions ---


@admin_router.get("/actions", response_model=list[AdminActionResponse])
async def list_actions_admin(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    domain: str | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(None, description="Search by action_key/domain/unit_type"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[AdminActionResponse]:
    """List global quota actions with optional filters and pagination."""
    q = select(QuotaAction).order_by(QuotaAction.domain, QuotaAction.action_key)
    if domain:
        q = q.where(QuotaAction.domain == domain)
    if is_active is not None:
        q = q.where(QuotaAction.is_active == is_active)
    if search:
        term = f"%{search}%"
        q = q.where(
            QuotaAction.action_key.ilike(term)
            | QuotaAction.domain.ilike(term)
            | QuotaAction.unit_type.ilike(term)
        )
    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [AdminActionResponse.model_validate(r) for r in rows]


@admin_router.post("/actions", response_model=AdminActionResponse, status_code=status.HTTP_201_CREATED)
async def create_action_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: AdminActionCreate,
) -> AdminActionResponse:
    """Create one global quota action and insert an initial pricing row."""
    existing = await db.execute(select(QuotaAction).where(QuotaAction.action_key == body.action_key))
    if existing.scalars().one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Action key already exists")

    from uuid import uuid4

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    action = QuotaAction(
        id=uuid4(),
        action_key=body.action_key,
        domain=body.domain,
        unit_type=body.unit_type,
        description=body.description,
        product_id=body.product_id,
        is_active=True,
        created_at=now,
    )
    db.add(action)
    await db.flush()

    price = QuotaActionPrice(
        id=uuid4(),
        action_id=action.id,
        rate_cents_per_compute_unit=body.default_rate_cents_per_compute_unit,
        effective_from=now,
        created_at=now,
    )
    db.add(price)
    await db.flush()

    await db.commit()
    await log_admin_action(db, admin.id, "action.create", "action", action.id, detail=action.action_key)
    await db.refresh(action)
    return AdminActionResponse.model_validate(action)


@admin_router.patch("/actions/{action_key}", response_model=AdminActionResponse)
async def update_action_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    action_key: str,
    body: AdminActionUpdate,
) -> AdminActionResponse:
    """Update an existing global quota action."""
    result = await db.execute(select(QuotaAction).where(QuotaAction.action_key == action_key))
    action = result.scalars().one_or_none()
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")

    updates = {}
    if body.domain is not None:
        updates["domain"] = body.domain
    if body.unit_type is not None:
        updates["unit_type"] = body.unit_type
    if body.description is not None:
        updates["description"] = body.description
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    if body.product_id is not None:
        updates["product_id"] = body.product_id

    if updates:
        await db.execute(update(QuotaAction).where(QuotaAction.id == action.id).values(**updates))
        
    if body.rate_cents_per_compute_unit is not None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        price = QuotaActionPrice(
            id=uuid4(),
            action_id=action.id,
            rate_cents_per_compute_unit=body.rate_cents_per_compute_unit,
            effective_from=now,
            created_at=now,
        )
        db.add(price)
        await db.flush()

    if updates or body.rate_cents_per_compute_unit is not None:
        await db.commit()
        await log_admin_action(db, admin.id, "action.update", "action", action.id, detail=action.action_key)
        await db.refresh(action)

    return AdminActionResponse.model_validate(action)


@admin_router.delete("/actions/{action_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    action_key: str,
) -> None:
    """Soft-delete a global quota action."""
    result = await db.execute(select(QuotaAction).where(QuotaAction.action_key == action_key))
    action = result.scalars().one_or_none()
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
        
    action.is_active = False
    db.add(action)
    await db.commit()

    await log_admin_action(db, admin.id, "action.delete", "action", action.id, detail=action.action_key)


# --- Block 13: Admin management ---


@admin_router.get("/admins", response_model=list[SuperAdminResponse])
async def list_admins_admin(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SuperAdminResponse]:
    """List all super admins."""
    result = await db.execute(
        select(SuperAdmin, Member)
        .join(Member, SuperAdmin.member_id == Member.id)
        .order_by(SuperAdmin.created_at)
    )
    rows = result.all()
    return [
        SuperAdminResponse(
            member_id=pa.member_id,
            email=m.email,
            display_name=m.display_name,
            created_at=pa.created_at,
        )
        for pa, m in rows
    ]


@admin_router.post("/admins", response_model=SuperAdminResponse)
async def add_admin_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: SuperAdminCreate,
) -> SuperAdminResponse:
    """Add super admin by email."""
    member_result = await db.execute(select(Member).where(Member.email == body.email))
    member = member_result.scalars().one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found for this email")
    existing = await db.execute(select(SuperAdmin).where(SuperAdmin.member_id == member.id))
    if existing.scalars().one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Already a super admin")
    from uuid import uuid4
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    pa = SuperAdmin(id=uuid4(), member_id=member.id, created_at=now)
    db.add(pa)
    await db.flush()
    await db.commit()
    await log_admin_action(db, admin.id, "admin.add", "admin", member.id, detail=body.email)
    return SuperAdminResponse(
        member_id=member.id,
        email=member.email,
        display_name=member.display_name,
        created_at=pa.created_at,
    )


@admin_router.delete("/admins/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_admin_admin(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    member_id: UUID,
) -> None:
    """Remove super admin. Cannot remove yourself."""
    if member_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    result = await db.execute(select(SuperAdmin).where(SuperAdmin.member_id == member_id))
    pa = result.scalars().one_or_none()
    if pa is None:
        raise HTTPException(status_code=404, detail="Not a super admin")
    await db.delete(pa)
    await db.commit()
    await log_admin_action(db, admin.id, "admin.remove", "admin", member_id)


# --- Block 14: Audit log ---


@admin_router.get("/audit-log", response_model=list[AdminAuditLogResponse])
async def get_audit_log_admin(
    _: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_member_id: UUID | None = Query(None),
    action: str | None = Query(None),
    target_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[AdminAuditLogResponse]:
    """List admin audit entries with filters."""
    q = select(SuperAdminAuditLog).order_by(SuperAdminAuditLog.created_at.desc())
    if admin_member_id:
        q = q.where(SuperAdminAuditLog.admin_member_id == admin_member_id)
    if action:
        q = q.where(SuperAdminAuditLog.action == action)
    if target_type:
        q = q.where(SuperAdminAuditLog.target_type == target_type)
    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [AdminAuditLogResponse.model_validate(r) for r in rows]

# --- Products & Entitlements ---

@admin_router.get("/products", response_model=list[ProductResponse])
async def list_products(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProductResponse]:
    """List all registered products."""
    result = await db.execute(select(Product).order_by(Product.name))
    return [ProductResponse.model_validate(r) for r in result.scalars().all()]

@admin_router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: ProductCreate,
) -> ProductResponse:
    """Create a new product."""
    import uuid
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    prod = Product(
        id=uuid.uuid4(),
        name=body.name,
        product_key=body.product_key,
        description=body.description,
        product_link=body.product_link,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(prod)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Product key already exists")
    await log_admin_action(db, admin.id, "product.create", "product", prod.id)
    return ProductResponse.model_validate(prod)

@admin_router.patch("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    body: ProductUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[Member, Depends(require_super_admin)],
):
    """Update a product (e.g. name, description, product_link, is_active). product_key is immutable."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalars().one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    updates_made = False
    if body.name is not None:
        product.name = body.name
        updates_made = True
    
    # We allow explicit setting to None or string for description and product_link
    # We must check if they are included in the fields that were actually set in the request.
    # To do this robustly without model_dump(exclude_unset=True) we just check if it's not None
    # Wait, the frontend might send null. 
    # Let's use body.model_dump(exclude_unset=True)
    update_data = body.model_dump(exclude_unset=True)
    
    if "description" in update_data:
        product.description = update_data["description"]
        updates_made = True
    if "product_link" in update_data:
        product.product_link = update_data["product_link"]
        updates_made = True
    if "is_active" in update_data:
        product.is_active = update_data["is_active"]
        updates_made = True

    if updates_made:
        product.updated_at = now
        await db.commit()
        await log_admin_action(db, admin.id, "product.update", "product", product.id)
    
    return product


@admin_router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    product_id: UUID,
):
    """Delete a product."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    prod = result.scalars().one_or_none()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(prod)
    await db.commit()
    await log_admin_action(db, admin.id, "product.delete", "product", product_id)

@admin_router.post("/organizations/{org_id}/entitlements", response_model=AdminOrgResponse)
async def grant_entitlement(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
    body: EntitlementGrantRequest,
) -> AdminOrgResponse:
    """Grant an entitlement to an organization."""
    # Verify product exists
    result = await db.execute(select(Product).where(Product.product_key == body.product_key))
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=400, detail=f"Product key '{body.product_key}' does not exist")
        
    result = await db.execute(select(Organization).options(selectinload(Organization.entitlements).selectinload(OrganizationEntitlement.product)).where(Organization.id == org_id))
    org = result.scalars().one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    existing_ent = next((e for e in org.entitlements if e.product_id == product.id), None)
    if existing_ent:
        existing_ent.expires_at = body.expires_at
        existing_ent.max_compute_units = body.max_compute_units
    else:
        new_ent = OrganizationEntitlement(
            organization_id=org_id,
            product_id=product.id,
            expires_at=body.expires_at,
            max_compute_units=body.max_compute_units
        )
        db.add(new_ent)
        org.entitlements.append(new_ent)
        
    org.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await log_admin_action(db, admin.id, "org.entitlement.grant", "organization", org_id, f"product_key={body.product_key}")
        
    return await get_organization(admin, db, org_id)

@admin_router.delete("/organizations/{org_id}/entitlements/{product_key}", response_model=AdminOrgResponse)
async def revoke_entitlement(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    org_id: UUID,
    product_key: str,
) -> AdminOrgResponse:
    """Revoke an entitlement from an organization."""
    result = await db.execute(select(Organization).options(selectinload(Organization.entitlements).selectinload(OrganizationEntitlement.product)).where(Organization.id == org_id))
    org = result.scalars().one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    ent = next((e for e in org.entitlements if e.product_key == product_key), None)
    if ent:
        await db.delete(ent)
        org.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        await log_admin_action(db, admin.id, "org.entitlement.revoke", "organization", org_id, f"product_key={product_key}")
        
    return await get_organization(admin, db, org_id)

# --- Block 16: Invites ---

from datetime import timedelta
from app.schemas.invite import OrganizationInviteCreate, OrganizationInviteResponse
from app.models.organization_invite import OrganizationInvite
from app.core.config import settings

@admin_router.post("/invites", response_model=OrganizationInviteResponse)
async def create_organization_invite(
    admin: Annotated[Member, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: OrganizationInviteCreate,
) -> OrganizationInviteResponse:
    """Create an organization invite ticket."""
    body.email = body.email.lower()
    existing_invite = await db.execute(
        select(OrganizationInvite)
        .where(
            OrganizationInvite.email == body.email,
            OrganizationInvite.organization_id == body.organization_id,
            OrganizationInvite.status == "pending"
        )
    )
    if existing_invite.scalars().first():
        raise HTTPException(status_code=400, detail="An active invite already exists for this email with this organization context")
        
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_at = now + timedelta(hours=body.expiration_hours)
    
    invite = OrganizationInvite(
        email=body.email,
        organization_id=body.organization_id,
        plan_id=body.plan_id,
        role=body.role,
        status="pending",
        invited_by=admin.id,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(invite)
    await db.commit()
    
    await log_admin_action(db, admin.id, "invite.create", "invite", invite.id, detail=body.email)
    
    invite_url = f"{settings.ORG_CONSOLE_URL}/invite?token={invite.id}"
    
    response = OrganizationInviteResponse.model_validate(invite)
    response.invite_url = invite_url
    return response
