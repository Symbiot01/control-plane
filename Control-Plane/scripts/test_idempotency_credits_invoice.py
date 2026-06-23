#!/usr/bin/env python3
"""
Test idempotency, credits (prepay), usage_ledger, and invoice generation.

- Idempotency: same (org_id, request_id) twice -> same response, only one usage_ledger and one quota_check_requests row.
- Credits: set org to prepay, grant small balance, one allowed consume then one insufficient_credits; verify credit_ledger.
- usage_ledger: assert rows for org after allowed checks.
- Invoice: generate_invoice_for_org(billing_period_end only; start derived), then assert invoice and line items.

Usage:
  python scripts/test_idempotency_credits_invoice.py [--org-id UUID] [--base-url URL]
  Set INTERNAL_API_KEY in .env. Server must be running. Optional: ORG_ID env or --org-id (default: first org with subscription).
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import asyncpg_connect_args_for_sslmode, settings
from app.models.credit_ledger import CreditLedger
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.organization import Organization
from app.models.quota_check_request import QuotaCheckRequest
from app.models.usage_ledger import UsageLedger
from app.services.credit_service import grant_credits
from app.services.invoice_service import generate_invoice_for_org


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def post_quota_check(base_url: str, api_key: str, org_id: str, action_key: str, units: int = 1, request_id: str | None = None) -> dict:
    import urllib.request
    body = {"organization_id": org_id, "action_key": action_key, "units": units}
    if request_id:
        body["request_id"] = request_id
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/internal/v1/quota/check",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Internal-Api-Key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


async def get_test_org_id(session: AsyncSession) -> UUID:
    from app.models.organization_subscription import OrganizationSubscription
    from app.core.constants import SUBSCRIPTION_STATUS_ACTIVE
    r = await session.execute(
        select(OrganizationSubscription.organization_id).where(
            OrganizationSubscription.status == SUBSCRIPTION_STATUS_ACTIVE
        ).limit(1)
    )
    row = r.first()
    if row is None:
        raise RuntimeError("No org with active subscription. Run seed_test_user.py first.")
    return row[0]


async def run_tests(base_url: str, api_key: str, org_id: UUID) -> None:
    engine = create_async_engine(
        settings.DATABASE_URL,
        connect_args=asyncpg_connect_args_for_sslmode(settings.POSTGRES_SSLMODE),
        echo=False,
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    org_id_str = str(org_id)
    # Use action that likely has quota headroom (legal may be exhausted from stress test)
    action_key = "medical.opinion.generate.v1"
    failures = []

    async with async_session() as session:
        # --- 1. Idempotency ---
        print("=== 1. Idempotency (same request_id twice) ===")
        req_id = f"idem-{datetime.now(timezone.utc).timestamp()}"
        r1 = post_quota_check(base_url, api_key, org_id_str, action_key, units=1, request_id=req_id)
        r2 = post_quota_check(base_url, api_key, org_id_str, action_key, units=1, request_id=req_id)
        if r1.get("allowed") != True or r2.get("allowed") != True:
            failures.append(f"Idempotency: expected both allowed; r1={r1.get('allowed')} r2={r2.get('allowed')}")
        else:
            print(f"  Both requests allowed (r1 current_usage={r1.get('current_usage')}, r2 current_usage={r2.get('current_usage')})")
        count_usage = await session.execute(
            select(func.count()).select_from(UsageLedger).where(
                UsageLedger.organization_id == org_id,
                UsageLedger.request_id == req_id,
            )
        )
        n_usage = (count_usage.scalars().first()) or 0
        if n_usage != 1:
            failures.append(f"Idempotency: expected 1 usage_ledger row for request_id={req_id}, got {n_usage}")
        else:
            print(f"  usage_ledger: 1 row for request_id={req_id} (no double count)")
        count_qcr = await session.execute(
            select(func.count()).select_from(QuotaCheckRequest).where(
                QuotaCheckRequest.organization_id == org_id,
                QuotaCheckRequest.request_id == req_id,
            )
        )
        n_qcr = (count_qcr.scalars().first()) or 0
        if n_qcr != 1:
            failures.append(f"Idempotency: expected 1 quota_check_requests row for request_id={req_id}, got {n_qcr}")
        else:
            print(f"  quota_check_requests: 1 row for request_id={req_id}")
        print()

        # --- 2. Credits (prepay): set balance, one consume then insufficient ---
        print("=== 2. Credits (prepay + consume + insufficient_credits) ===")
        org_row = (await session.execute(select(Organization).where(Organization.id == org_id))).scalars().one()
        original_mode = org_row.billing_mode
        original_balance = int(org_row.prepaid_balance_cents or 0)
        original_overdraft = int(org_row.overdraft_limit_cents or 0)
        org_row.billing_mode = "prepay"
        org_row.prepaid_balance_cents = 1  # 1 cent: one allowed (1 unit=1 cent), next denied
        org_row.overdraft_limit_cents = 0
        await session.flush()
        await session.commit()

        req_id_allow = f"credit-allow-{datetime.now(timezone.utc).timestamp()}"
        req_id_deny = f"credit-deny-{datetime.now(timezone.utc).timestamp()}"
        r_allow = post_quota_check(base_url, api_key, org_id_str, action_key, units=1, request_id=req_id_allow)
        r_deny = post_quota_check(base_url, api_key, org_id_str, action_key, units=1, request_id=req_id_deny)
        if not r_allow.get("allowed"):
            failures.append(f"Credits: first request (balance=1) expected allowed, got {r_allow}")
        else:
            print(f"  First request (1 cent): allowed")
        if r_deny.get("allowed") or r_deny.get("reason") != "insufficient_credits":
            failures.append(f"Credits: second request expected denied insufficient_credits, got {r_deny}")
        else:
            print(f"  Second request: denied reason={r_deny.get('reason')}")
        count_consume = await session.execute(
            select(func.count()).select_from(CreditLedger).where(
                CreditLedger.organization_id == org_id,
                CreditLedger.type == "consume",
                CreditLedger.reference_id.in_([req_id_allow, req_id_deny]),
            )
        )
        n_consume = (count_consume.scalars().first()) or 0
        if n_consume != 1:
            failures.append(f"Credits: expected 1 consume row (only first request), got {n_consume}")
        else:
            print(f"  credit_ledger: 1 consume row (no double debit)")
        # Restore org
        org_row = (await session.execute(select(Organization).where(Organization.id == org_id))).scalars().one()
        org_row.billing_mode = original_mode
        org_row.prepaid_balance_cents = original_balance
        org_row.overdraft_limit_cents = original_overdraft
        await session.flush()
        await session.commit()
        print()

        # --- 3. usage_ledger ---
        print("=== 3. usage_ledger ===")
        r = await session.execute(
            select(func.count(), func.coalesce(func.sum(UsageLedger.compute_units), 0)).select_from(UsageLedger).where(
                UsageLedger.organization_id == org_id
            )
        )
        row = r.one()
        print(f"  Rows for org: {row[0]}, total compute_units: {row[1]}")
        sample = (await session.execute(select(UsageLedger).where(UsageLedger.organization_id == org_id).limit(3))).scalars().all()
        for s in sample:
            print(f"    id={s.id}, action_id={s.action_id}, units={s.units}, compute_units={s.compute_units}, request_id={s.request_id}")
        print()

        # --- 4. Invoice generation ---
        print("=== 4. Invoice generation ===")
        now = _naive_utc(datetime.now(timezone.utc))
        year, month = now.year, now.month
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month == 12:
            billing_period_end = period_start.replace(year=year + 1, month=1, day=1)
        else:
            billing_period_end = period_start.replace(month=month + 1, day=1)
        inv_id = await generate_invoice_for_org(session, org_id, billing_period_end)
        await session.commit()
        inv = (await session.execute(select(Invoice).where(Invoice.id == inv_id))).scalars().one()
        print(f"  Invoice id={inv.id}, total_compute_units={inv.total_compute_units}, included={inv.included_units}, overage={inv.overage_units}, amount_due={inv.amount_due}, credits_applied={inv.credits_applied_cents}, amount_paid={inv.amount_paid_cents}")
        items = (await session.execute(select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == inv_id))).scalars().all()
        print(f"  Line items: {len(items)}")
        for it in items:
            print(f"    action_id={it.action_id}, units={it.units}, compute_units={it.compute_units}, amount={it.amount}")
        if inv.total_compute_units > 0 and len(items) == 0:
            failures.append("Invoice: expected at least one line item when total_compute_units > 0")
        print()

    await engine.dispose()
    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("All checks passed.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org-id", type=str, default=os.environ.get("ORG_ID"), help="Organization UUID (default: first with subscription)")
    ap.add_argument("--base-url", type=str, default=os.environ.get("BASE_URL", "http://127.0.0.1:8000"), help="Control Plane base URL")
    args = ap.parse_args()
    api_key = os.environ.get("INTERNAL_API_KEY")
    if not api_key:
        print("Set INTERNAL_API_KEY in .env")
        sys.exit(1)
    if args.org_id:
        org_id = UUID(args.org_id)
    else:
        async def _get():
            engine = create_async_engine(
                settings.DATABASE_URL,
                connect_args=asyncpg_connect_args_for_sslmode(settings.POSTGRES_SSLMODE),
                echo=False,
            )
            async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with async_session() as s:
                oid = await get_test_org_id(s)
            await engine.dispose()
            return oid
        org_id = asyncio.run(_get())
    print(f"Using org_id={org_id}, base_url={args.base_url}")
    asyncio.run(run_tests(args.base_url, api_key, org_id))


if __name__ == "__main__":
    main()
