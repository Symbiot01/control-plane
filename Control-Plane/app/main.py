"""Control Plane – FastAPI app entry. Lifespan: Redis + DB; Firebase; health check."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.api.router import api_router
from app.core.config import settings
from app.modules.admin.router import admin_router
from app.core.firebase import ensure_firebase_initialized
from app.core.jwt import build_jwks
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: Firebase, Redis; attach to app.state. Shutdown: close Redis, dispose DB engine."""
    ensure_firebase_initialized()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    app.state.redis = redis
    try:
        yield
    finally:
        await redis.aclose()
        await engine.dispose()


app = FastAPI(
    title="Control Plane",
    description="Phase 1: Auth, RBAC, organizations, quotas, rate limiting. No billing.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_redis(request: Request) -> Redis:
    """FastAPI dependency: return Redis client from app.state."""
    return request.app.state.redis


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check. Returns 200 when app is up."""
    return {"status": "ok"}


@app.get("/.well-known/jwks.json")
async def jwks() -> dict:
    """JWKS for Control JWT verification (Product Plane / clients)."""
    return build_jwks()


app.include_router(api_router)
app.include_router(admin_router, prefix="/admin/v1")

from fastapi.responses import JSONResponse
import traceback
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    with open("error.log", "a") as f:
        f.write(f"Error on {request.url.path}:\n")
        traceback.print_exc(file=f)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error"}
    )

