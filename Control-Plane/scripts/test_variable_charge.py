#!/usr/bin/env python
"""
Test variable charges.
This script demonstrates the Two-Phase Commit flow by hitting the 
reserve and commit endpoints locally.
Requires the Control Plane to be running locally on port 8000.
"""

import httpx
import asyncio
import uuid
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test")

# Load .env
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY")

async def run_test():
    if not INTERNAL_API_KEY:
        logger.error("INTERNAL_API_KEY not found in .env. Please copy .env.example to .env first.")
        return

    # First, let's just grab the first organization ID from the database using python
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.core.config import settings
    from app.core.config import asyncpg_connect_args_for_sslmode
    from app.models.organization import Organization

    engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args=asyncpg_connect_args_for_sslmode(settings.POSTGRES_SSLMODE),
        echo=False,
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    org_id = None
    async with async_session() as session:
        r = await session.execute(select(Organization.id).limit(1))
        row = r.first()
        if row:
            org_id = str(row[0])
    
    await engine.dispose()

    if not org_id:
        logger.error("No organizations found in the database. Please run python scripts/seed_test_user.py first!")
        return

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        headers = {"X-Internal-API-Key": INTERNAL_API_KEY}
        request_id = str(uuid.uuid4())
        action_key = "medical.opinion.generate.v1"
        
        logger.info(f"Phase 1: Reserving 40 units for org {org_id}")
        resp = await client.post(
            "/internal/v1/quota/reserve",
            headers=headers,
            json={
                "organization_id": org_id,
                "action_key": action_key,
                "max_units": 40,
                "request_id": request_id
            }
        )
        logger.info(f"Reserve response: {resp.status_code} {resp.text}")
        
        if resp.status_code != 200 or not resp.json().get("allowed"):
            logger.error("Reserve failed. Did you seed the database?")
            return

        logger.info("Phase 2: Committing 25 actual units used")
        resp2 = await client.post(
            "/internal/v1/quota/commit",
            headers=headers,
            json={
                "organization_id": org_id,
                "request_id": request_id,
                "actual_units": 25
            }
        )
        logger.info(f"Commit response: {resp2.status_code} {resp2.text}")

if __name__ == "__main__":
    asyncio.run(run_test())

