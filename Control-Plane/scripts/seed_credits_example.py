#!/usr/bin/env python3
"""Seed example prepaid credits for a test organization.

Run from project root:
    python scripts/seed_credits_example.py <organization_id> <amount_cents>
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import asyncpg_connect_args_for_sslmode, settings  # noqa: E402
from app.services.credit_service import grant_credits  # noqa: E402


async def main(org_id: UUID, amount_cents: int) -> None:
    engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args=asyncpg_connect_args_for_sslmode(settings.POSTGRES_SSLMODE),
        echo=False,
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        print(
            f"{datetime.now(timezone.utc).isoformat()} "
            f"Granting {amount_cents} cents to org {org_id}"
        )
        await grant_credits(session, org_id, amount_cents, type="seed_top_up", reference_id=None)
        await session.commit()
    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/seed_credits_example.py <organization_id> <amount_cents>")
        sys.exit(1)
    org_id = UUID(sys.argv[1])
    amount_cents = int(sys.argv[2])
    asyncio.run(main(org_id, amount_cents))

