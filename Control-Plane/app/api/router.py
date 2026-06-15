"""Aggregate all module routers: auth, organizations, members, quotas, plans, billing, internal."""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.billing.router import router as billing_router
from app.modules.internal.router import router as internal_router
from app.modules.members.router import router as members_router
from app.modules.organizations.router import router as organizations_router
from app.modules.plans.router import router as plans_router
from app.modules.quotas.router import router as quotas_router
from app.modules.invites.router import invites_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(invites_router)
api_router.include_router(organizations_router)
api_router.include_router(billing_router)
api_router.include_router(members_router)
api_router.include_router(quotas_router)
api_router.include_router(plans_router)
api_router.include_router(internal_router)
