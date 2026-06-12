"""Organization and membership business logic."""

import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    ORG_STATUS_ACTIVE,
    ROLE_OWNER,
    TIER_STARTER,
)
from app.models.member import Member
from app.models.organization import Organization
from app.models.organization_entitlement import OrganizationEntitlement
from app.models.organization_member import OrganizationMember


def slugify(name: str) -> str:
    """Simple slug: lowercase, replace non-alphanumeric with hyphens, strip."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "org"


async def create_organization(
    db: AsyncSession,
    name: str,
    owner_member_id: UUID,
    slug: str | None = None,
) -> Organization:
    """Create organization and add owner as owner. Slug from name if not provided."""
    existing_membership = await db.execute(
        select(OrganizationMember).where(OrganizationMember.member_id == owner_member_id)
    )
    if existing_membership.scalars().first() is not None:
        raise ValueError("User is already a member of an organization.")

    existing_name = await db.execute(
        select(Organization).where(func.lower(Organization.name) == name.lower())
    )
    if existing_name.scalars().first() is not None:
        raise ValueError(f"Organization name '{name}' is already taken.")

    if slug is None or slug == "":
        slug = slugify(name)
    # Ensure uniqueness
    existing = await db.execute(select(Organization).where(Organization.slug == slug))
    if existing.scalars().first() is not None:
        base = slug
        for i in range(1, 1000):
            candidate = f"{base}-{i}"
            r = await db.execute(select(Organization).where(Organization.slug == candidate))
            if r.scalars().first() is None:
                slug = candidate
                break
        else:
            slug = f"{base}-{uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for TIMESTAMP WITHOUT TIME ZONE
    org = Organization(
        id=uuid4(),
        name=name,
        slug=slug,
        status=ORG_STATUS_ACTIVE,
        tier=TIER_STARTER,
        created_at=now,
        updated_at=now,
    )
    db.add(org)
    await db.flush()
    om = OrganizationMember(
        id=uuid4(),
        organization_id=org.id,
        member_id=owner_member_id,
        role=ROLE_OWNER,
        created_at=now,
    )
    db.add(om)
    await db.flush()
    return org


async def get_organization(db: AsyncSession, org_id: UUID) -> Organization | None:
    """Get organization by id."""
    result = await db.execute(
        select(Organization)
        .options(selectinload(Organization.entitlements).selectinload(OrganizationEntitlement.product))
        .where(Organization.id == org_id)
    )
    return result.scalars().one_or_none()


async def list_organizations_for_member(
    db: AsyncSession,
    member_id: UUID,
) -> list[tuple[Organization, str]]:
    """List (organization, role) for member."""
    result = await db.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .options(selectinload(Organization.entitlements).selectinload(OrganizationEntitlement.product))
        .where(OrganizationMember.member_id == member_id)
    )
    return list(result.all())


async def get_membership(
    db: AsyncSession,
    organization_id: UUID,
    member_id: UUID,
) -> OrganizationMember | None:
    """Get organization_members row if exists."""
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.member_id == member_id,
        )
    )
    return result.scalars().one_or_none()


async def count_owners(db: AsyncSession, organization_id: UUID) -> int:
    """Count members with role owner in org."""
    result = await db.execute(
        select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.role == ROLE_OWNER,
        )
    )
    return result.scalar() or 0


async def update_member_role(
    db: AsyncSession,
    organization_id: UUID,
    member_id: UUID,
    new_role: str,
) -> OrganizationMember | None:
    """Update role; prevent demoting last owner. Returns updated OrganizationMember or None."""
    membership = await get_membership(db, organization_id, member_id)
    if membership is None:
        return None
    if membership.role == ROLE_OWNER and new_role != ROLE_OWNER:
        if await count_owners(db, organization_id) <= 1:
            return None  # Cannot demote last owner
    membership.role = new_role
    await db.flush()
    return membership


async def remove_member(
    db: AsyncSession,
    organization_id: UUID,
    member_id: UUID,
) -> bool:
    """Remove member from org. Returns False if would remove last owner."""
    membership = await get_membership(db, organization_id, member_id)
    if membership is None:
        return True  # Already not a member
    if membership.role == ROLE_OWNER and await count_owners(db, organization_id) <= 1:
        return False
    await db.delete(membership)
    await db.flush()
    return True


async def get_organization_members(
    db: AsyncSession,
    organization_id: UUID,
) -> list[tuple[Member, str]]:
    """List all members and their roles for a specific organization."""
    result = await db.execute(
        select(Member, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.member_id == Member.id)
        .where(OrganizationMember.organization_id == organization_id)
        .order_by(Member.created_at.desc())
    )
    return list(result.all())


async def get_pending_invites(
    db: AsyncSession,
    organization_id: UUID,
) -> list["OrganizationInvite"]:
    """List all pending invites for a specific organization."""
    from app.models.organization_invite import OrganizationInvite
    result = await db.execute(
        select(OrganizationInvite)
        .where(
            OrganizationInvite.organization_id == organization_id,
            OrganizationInvite.status == "pending"
        )
        .order_by(OrganizationInvite.created_at.desc())
    )
    return list(result.scalars().all())

