"""
Reap orphaned holds.
Finds QuotaCheckRequest entries with status 'held' past expires_at,
and rolls them back / marks expired via the shared hold_reaper_service.
"""

import asyncio
import logging

from app.services.hold_reaper_service import reap_once

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reaper")


async def main() -> None:
    logger.info("Starting orphaned holds reaper...")
    n = await reap_once()
    if n == 0:
        logger.info("No orphaned holds found.")
    else:
        logger.info("Expired %s orphaned hold(s).", n)


if __name__ == "__main__":
    asyncio.run(main())
