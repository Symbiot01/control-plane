"""Member routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_member, rate_limit_per_org
from app.db.session import get_db
from app.models.member import Member
from app.models.organization_entitlement import OrganizationEntitlement
from app.models.product import Product
from app.schemas.member import MemberProfile
from app.schemas.organization import EntitlementResponse, OrganizationResponse, OrganizationWithRole
from app.services.org_service import list_organizations_for_member

router = APIRouter(prefix="/members", tags=["members"])


@router.get("/me", response_model=MemberProfile)
async def get_members_me(
    db: Annotated[AsyncSession, Depends(get_db)],
    member: Annotated[Member, Depends(get_current_member)],
    _rl: Annotated[None, Depends(rate_limit_per_org)],
):
    """Current member profile with org role and product entitlements."""
    pairs = await list_organizations_for_member(db, member.id)
    org_with_role = None
    entitlements: list[EntitlementResponse] = []
    if pairs:
        org, role = pairs[0]
        org_with_role = OrganizationWithRole(
            **OrganizationResponse.model_validate(org).model_dump(),
            role=role,
        )
        result = await db.execute(
            select(OrganizationEntitlement, Product)
            .join(Product, OrganizationEntitlement.product_id == Product.id)
            .where(OrganizationEntitlement.organization_id == org.id)
        )
        for ent, prod in result.all():
            entitlements.append(
                EntitlementResponse(
                    product_key=prod.product_key,
                    product_name=prod.name,
                    product_link=prod.product_link,
                    is_active=prod.is_active,
                    expires_at=ent.expires_at,
                    max_compute_units=ent.max_compute_units,
                    created_at=ent.created_at,
                )
            )

    return MemberProfile(
        id=member.id,
        email=member.email,
        display_name=member.display_name,
        is_active=member.is_active,
        created_at=member.created_at,
        organization=org_with_role,
        entitlements=entitlements,
    )
