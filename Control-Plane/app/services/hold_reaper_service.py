"""Expire orphaned quota holds safely with FOR UPDATE SKIP LOCKED."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import QUOTA_STATUS_HELD
from app.db.session import AsyncSessionLocal
from app.models.quota_check_request import QuotaCheckRequest
from app.services.quota_check_service import quota_rollback

logger = logging.getLogger("hold_reaper")


def _naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _list_expired_hold_ids(db: AsyncSession, *, limit: int = 100) -> list:
    now = _naive_utc_now()
    result = await db.execute(
        text(
            """
            SELECT id
            FROM quota_check_requests
            WHERE status = :status
              AND expires_at IS NOT NULL
              AND expires_at < :now
            ORDER BY expires_at
            FOR UPDATE SKIP LOCKED
            LIMIT :limit
            """
        ),
        {"status": QUOTA_STATUS_HELD, "now": now, "limit": limit},
    )
    return [row[0] for row in result.fetchall()]


async def expire_orphaned_holds(db: AsyncSession, *, limit: int = 100) -> int:
    """
    Expire held reservations past expires_at within the given session.
    Caller commits. Prefer reap_once() for production (one commit per hold).
    """
    ids = await _list_expired_hold_ids(db, limit=limit)
    expired = 0
    for row_id in ids:
        qr_result = await db.execute(
            select(QuotaCheckRequest).where(QuotaCheckRequest.id == row_id)
        )
        qr = qr_result.scalars().one_or_none()
        if qr is None or qr.status != QUOTA_STATUS_HELD:
            continue
        await quota_rollback(
            db,
            org_id=qr.organization_id,
            request_id=qr.request_id,
            expired=True,
        )
        expired += 1
        logger.info(
            "Expired hold request_id=%s org_id=%s",
            qr.request_id,
            qr.organization_id,
        )
    return expired


async def reap_once(*, limit: int = 100) -> int:
    """Expire up to `limit` holds, committing each successfully expired hold."""
    async with AsyncSessionLocal() as db:
        try:
            ids = await _list_expired_hold_ids(db, limit=limit)
            await db.commit()  # release advisory locks from listing txn
        except Exception:
            await db.rollback()
            raise

    expired = 0
    for row_id in ids:
        async with AsyncSessionLocal() as db:
            try:
                qr_result = await db.execute(
                    select(QuotaCheckRequest)
                    .where(QuotaCheckRequest.id == row_id)
                    .with_for_update(skip_locked=True)
                )
                qr = qr_result.scalars().one_or_none()
                if qr is None or qr.status != QUOTA_STATUS_HELD:
                    await db.commit()
                    continue
                if qr.expires_at is None or qr.expires_at >= _naive_utc_now():
                    await db.commit()
                    continue
                await quota_rollback(
                    db,
                    org_id=qr.organization_id,
                    request_id=qr.request_id,
                    expired=True,
                )
                await db.commit()
                expired += 1
                logger.info(
                    "Expired hold request_id=%s org_id=%s",
                    qr.request_id,
                    qr.organization_id,
                )
            except Exception:
                await db.rollback()
                logger.exception("Failed to expire hold id=%s", row_id)
    return expired
