#!/usr/bin/env python3
"""
Read-only preflight audit before applying harden-quota migration.

Reports:
- duplicate (organization_id, request_id) in quota_check_requests
- duplicate usage_ledger / credit_ledger consume references
- inconsistent terminal statuses
- held_balance_cents vs sum of live held reservations

Exit 0 if clean; exit 1 if manual reconciliation is required.
Does not delete or mutate billable rows.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import asyncpg_connect_args_for_sslmode, settings


async def run_audit() -> int:
    engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args=asyncpg_connect_args_for_sslmode(settings.POSTGRES_SSLMODE),
        echo=False,
    )
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    issues = 0

    async with Session() as db:
        print("=== Duplicate (organization_id, request_id) ===")
        rows = (
            await db.execute(
                text(
                    """
                    SELECT organization_id, request_id, COUNT(*) AS n, array_agg(status)
                    FROM quota_check_requests
                    GROUP BY organization_id, request_id
                    HAVING COUNT(*) > 1
                    ORDER BY n DESC
                    LIMIT 50
                    """
                )
            )
        ).all()
        if not rows:
            print("  OK: none")
        else:
            issues += len(rows)
            for r in rows:
                print(f"  DUPLICATE org={r[0]} request_id={r[1]} count={r[2]} statuses={r[3]}")

        print("\n=== Duplicate usage_ledger (organization_id, request_id) ===")
        rows = (
            await db.execute(
                text(
                    """
                    SELECT organization_id, request_id, COUNT(*) AS n
                    FROM usage_ledger
                    WHERE request_id IS NOT NULL
                    GROUP BY organization_id, request_id
                    HAVING COUNT(*) > 1
                    LIMIT 50
                    """
                )
            )
        ).all()
        if not rows:
            print("  OK: none")
        else:
            issues += len(rows)
            for r in rows:
                print(f"  DUPLICATE org={r[0]} request_id={r[1]} count={r[2]}")

        print("\n=== Duplicate credit_ledger consume references ===")
        rows = (
            await db.execute(
                text(
                    """
                    SELECT organization_id, reference_id, COUNT(*) AS n
                    FROM credit_ledger
                    WHERE type = 'consume' AND reference_id IS NOT NULL
                    GROUP BY organization_id, reference_id
                    HAVING COUNT(*) > 1
                    LIMIT 50
                    """
                )
            )
        ).all()
        if not rows:
            print("  OK: none")
        else:
            issues += len(rows)
            for r in rows:
                print(f"  DUPLICATE org={r[0]} reference_id={r[1]} count={r[2]}")

        print("\n=== Allowed=false with status=committed (legacy) ===")
        n = (
            await db.execute(
                text(
                    """
                    SELECT COUNT(*) FROM quota_check_requests
                    WHERE allowed = false AND status = 'committed'
                    """
                )
            )
        ).scalar()
        print(f"  count={n} (migration will normalize to denied)")

        print("\n=== Held balance vs live holds ===")
        rows = (
            await db.execute(
                text(
                    """
                    SELECT o.id,
                           o.held_balance_cents,
                           COALESCE(SUM(q.held_cents), 0) AS live_holds
                    FROM organizations o
                    LEFT JOIN quota_check_requests q
                      ON q.organization_id = o.id AND q.status = 'held'
                    GROUP BY o.id, o.held_balance_cents
                    HAVING o.held_balance_cents <> COALESCE(SUM(q.held_cents), 0)
                    LIMIT 50
                    """
                )
            )
        ).all()
        if not rows:
            print("  OK: held_balance_cents matches sum of held reservations")
        else:
            issues += len(rows)
            for r in rows:
                print(
                    f"  MISMATCH org={r[0]} held_balance_cents={r[1]} live_holds={r[2]}"
                )

    await engine.dispose()
    if issues:
        print(f"\nPREFLIGHT FAILED: {issues} issue group(s). Reconcile manually before UNIQUE migration.")
        return 1
    print("\nPREFLIGHT OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_audit()))
