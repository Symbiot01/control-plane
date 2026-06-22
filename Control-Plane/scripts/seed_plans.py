#!/usr/bin/env python3
"""Seed plans with a default starter plan. Idempotent (skip if plan name exists). Run from project root: python scripts/seed_plans.py"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import asyncpg_connect_args_for_sslmode, settings
from app.models.plan import Plan

# Default plan: price in cents, included compute units, overage rate per unit (cents)
DEFAULT_PLAN = {
    "name": "starter",
    "monthly_price": 2999,  # $29.99
    "included_compute_units": 10_000,
    "overage_rate": 5,  # 5 cents per unit over included
    "currency": "USD",
}


async def main():
    engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args=asyncpg_connect_args_for_sslmode(settings.POSTGRES_SSLMODE),
        echo=False,
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        r = await session.execute(select(Plan).where(Plan.name == DEFAULT_PLAN["name"]))
        if r.scalars().first() is not None:
            print(f"Skip (exists): {DEFAULT_PLAN['name']}")
            await engine.dispose()
            print("Done.")
            return
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        plan = Plan(
            id=uuid4(),
            name=DEFAULT_PLAN["name"],
            monthly_price=DEFAULT_PLAN["monthly_price"],
            included_compute_units=DEFAULT_PLAN["included_compute_units"],
            overage_rate=DEFAULT_PLAN["overage_rate"],
            currency=DEFAULT_PLAN["currency"],
            created_at=now,
        )
        session.add(plan)
        print(f"Inserted plan: {DEFAULT_PLAN['name']}")
        await session.commit()
    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
