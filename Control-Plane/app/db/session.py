"""Async database session and dependency."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import asyncpg_connect_args_for_sslmode, settings
from app.db.base import Base

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=asyncpg_connect_args_for_sslmode(settings.POSTGRES_SSLMODE),
    echo=settings.ENVIRONMENT == "development",
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
