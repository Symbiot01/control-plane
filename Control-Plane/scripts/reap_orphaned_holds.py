#!/usr/bin/env python
"""
Reap orphaned holds.
Finds QuotaCheckRequest entries with status 'held' older than 1 hour,
and automatically rolls them back.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, and_
from app.db.session import SessionLocal
from app.models.quota_check_request import QuotaCheckRequest
from app.services.quota_check_service import quota_rollback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reaper")

async def reap_orphaned_holds():
    logger.info("Starting orphaned holds reaper...")
    async with SessionLocal() as db:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        
        # Find stuck holds
        result = await db.execute(
            select(QuotaCheckRequest)
            .where(
                and_(
                    QuotaCheckRequest.status == "held",
                    QuotaCheckRequest.created_at < cutoff
                )
            )
        )
        stuck_requests = result.scalars().all()
        
        if not stuck_requests:
            logger.info("No orphaned holds found.")
            return

        for qr in stuck_requests:
            logger.info(f"Rolling back orphaned request_id: {qr.request_id} for org_id: {qr.organization_id}")
            try:
                await quota_rollback(db, qr.organization_id, qr.request_id)
                await db.commit()
                logger.info(f"Successfully rolled back {qr.request_id}")
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to rollback {qr.request_id}: {e}")

if __name__ == "__main__":
    asyncio.run(reap_orphaned_holds())
