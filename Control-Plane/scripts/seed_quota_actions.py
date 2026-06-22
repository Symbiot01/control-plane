#!/usr/bin/env python3
"""Seed quota_actions with a minimal set. Run from project root: python scripts/seed_quota_actions.py"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import asyncpg_connect_args_for_sslmode, settings
from app.models.quota_action import QuotaAction
from app.models.quota_action_price import QuotaActionPrice

ACTIONS = [
    ("legal.case.analyze.v1", "legal", "count", "Legal case analysis"),
    ("medical.opinion.generate.v1", "medical", "tokens", "Medical opinion generation"),
    ("vision.defect.detect.v1", "vision", "count", "Vision defect detection"),
    ("core.member.create.v1", "core", "count", "Member creation"),
]


async def main():
    engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args=asyncpg_connect_args_for_sslmode(settings.POSTGRES_SSLMODE),
        echo=False,
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        for action_key, domain, unit_type, description in ACTIONS:
            r = await session.execute(select(QuotaAction).where(QuotaAction.action_key == action_key))
            if r.scalars().first() is not None:
                print(f"Skip (exists): {action_key}")
                continue
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            q = QuotaAction(
                id=uuid4(),
                action_key=action_key,
                domain=domain,
                unit_type=unit_type,
                description=description,
                is_active=True,
                created_at=now_naive,
            )
            session.add(q)
            print(f"Inserted: {action_key}")
            # Seed a simple default price: 1 cent per compute unit, effective now
            price = QuotaActionPrice(
                id=uuid4(),
                action_id=q.id,
                rate_cents_per_compute_unit=1,
                effective_from=now_naive,
                created_at=now_naive,
            )
            session.add(price)
            print(f"  -> Inserted price for {action_key}: 1 cent per compute unit")
        # Ensure every existing action has at least one price (for actions created before prices existed)
        all_actions = (await session.execute(select(QuotaAction))).scalars().all()
        for q in all_actions:
            has_price = (await session.execute(select(QuotaActionPrice).where(QuotaActionPrice.action_id == q.id).limit(1))).scalars().first()
            if has_price is None:
                now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
                price = QuotaActionPrice(
                    id=uuid4(),
                    action_id=q.id,
                    rate_cents_per_compute_unit=1,
                    effective_from=now_naive,
                    created_at=now_naive,
                )
                session.add(price)
                print(f"  -> Inserted default price for existing action {q.action_key}: 1 cent per compute unit")
        await session.commit()
    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
