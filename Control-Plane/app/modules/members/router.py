"""Member routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_member, rate_limit_per_org
from app.db.session import get_db
from app.models.member import Member
from app.schemas.member import MemberProfile
from app.schemas.organization import OrganizationResponse, OrganizationWithRole
from app.services.org_service import list_organizations_for_member

router = APIRouter(prefix="/members", tags=["members"])


@router.get("/me", response_model=MemberProfile)
async def get_members_me(
    db: Annotated[AsyncSession, Depends(get_db)],
    member: Annotated[Member, Depends(get_current_member)],
    _rl: Annotated[None, Depends(rate_limit_per_org)],
):
    """Current member profile with list of orgs and roles."""
    pairs = await list_organizations_for_member(db, member.id)
    org_with_role = None
    if pairs:
        org, role = pairs[0]
        org_with_role = OrganizationWithRole(**OrganizationResponse.model_validate(org).model_dump(), role=role)
        
    return MemberProfile(
        id=member.id,
        email=member.email,
        display_name=member.display_name,
        is_active=member.is_active,
        created_at=member.created_at,
        organization=org_with_role,
    )
