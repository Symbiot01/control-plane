"""Control Plane – FastAPI app entry. Lifespan: Redis + DB + hold reaper; Firebase; health check."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.api.router import api_router
from app.core.config import settings
from app.core.firebase import ensure_firebase_initialized
from app.core.jwt import build_jwks
from app.db.session import engine
from app.modules.admin.router import admin_router
from app.services.hold_reaper_service import reap_once

logger = logging.getLogger("control_plane")


async def _hold_reaper_loop(stop: asyncio.Event) -> None:
    interval = max(5, int(settings.QUOTA_REAPER_INTERVAL_SECONDS))
    while not stop.is_set():
        try:
            n = await reap_once()
            if n:
                logger.info("Hold reaper expired %s reservation(s)", n)
        except Exception:
            logger.exception("Hold reaper iteration failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: Firebase, Redis, optional hold reaper. Shutdown: stop reaper, close Redis, dispose DB."""
    ensure_firebase_initialized()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    app.state.redis = redis
    stop = asyncio.Event()
    reaper_task: asyncio.Task | None = None
    if settings.QUOTA_REAPER_ENABLED:
        reaper_task = asyncio.create_task(_hold_reaper_loop(stop))
    try:
        yield
    finally:
        stop.set()
        if reaper_task is not None:
            await reaper_task
        await redis.aclose()
        await engine.dispose()


app = FastAPI(
    title="Control Plane",
    description="Auth, RBAC, organizations, quotas, rate limiting, billing.",
    version="0.2.0",
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback

    with open("error.log", "a") as f:
        f.write(f"Error on {request.url.path}:\n")
        traceback.print_exc(file=f)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error"},
    )
