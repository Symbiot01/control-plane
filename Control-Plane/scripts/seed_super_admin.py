#!/usr/bin/env python3
"""
Bootstrap a super admin by email. Inserts into super_admins if not already present.

Usage:
  python scripts/seed_super_admin.py [EMAIL]
  python scripts/seed_super_admin.py sahil0111patel@gmail.com

Run from project root. Member must already exist (e.g. after one /auth/exchange with that email).
Default admin email: sahil0111patel@gmail.com (used when no argument is given).
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import asyncpg_connect_args_for_sslmode, settings
from app.models.member import Member
from app.modules.admin.models import SuperAdmin

DEFAULT_EMAIL = "sahil0111patel@gmail.com"


async def main(email: str) -> None:
    engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args=asyncpg_connect_args_for_sslmode(settings.POSTGRES_SSLMODE),
        echo=False,
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        result = await session.execute(select(Member).where(Member.email == email))
        member = result.scalars().one_or_none()
        if member is None:
            print(f"Member not found for email: {email}", file=sys.stderr)
            sys.exit(1)
        existing = await session.execute(
            select(SuperAdmin).where(SuperAdmin.member_id == member.id)
        )
        if existing.scalars().one_or_none() is not None:
            print(f"Already a super admin: {email}")
            await engine.dispose()
            return
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        pa = SuperAdmin(id=uuid4(), member_id=member.id, created_at=now)
        session.add(pa)
        await session.commit()
        print(f"Added super admin: {email} (member_id={member.id})")
    await engine.dispose()


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EMAIL
    try:
        asyncio.run(main(email))
    except Exception as e:
        err = str(e).lower()
        if "password" in err or "authentication" in err or "connection" in err or "invalidpassworderror" in err:
            print(
                "Database connection failed. Check .env: POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB (or DATABASE_URL).",
                file=sys.stderr,
            )
            print(
                "If using Docker Compose: ensure .env matches the credentials the postgres container was created with. "
                "To reset: docker compose down -v && docker compose up -d",
                file=sys.stderr,
            )
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
