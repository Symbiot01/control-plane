"""Credit service – manage prepaid wallet balance and credit ledger."""

import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_ledger import CreditLedger
from app.models.organization import Organization


def _naive_utc(dt: datetime) -> datetime:
    """Ensure datetime is naive UTC for TIMESTAMP WITHOUT TIME ZONE."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


async def grant_credits(
    db: AsyncSession,
    organization_id: UUID,
    amount_cents: int,
    type: str = "grant",
    reference_id: str | None = None,
) -> None:
    """
    Grant or top up credits for an organization.

    amount_cents must be positive. Updates organizations.prepaid_balance_cents and inserts a
    positive row into credit_ledger.
    """
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive for grant_credits")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Increment wallet balance
    await db.execute(
        update(Organization)
        .where(Organization.id == organization_id)
        .values(
            prepaid_balance_cents=Organization.prepaid_balance_cents + amount_cents,
            updated_at=now,
        )
    )

    # Ledger row
    entry = CreditLedger(
        id=uuid.uuid4(),
        organization_id=organization_id,
        amount_cents=amount_cents,
        type=type,
        reference_id=reference_id,
        created_at=now,
    )
    db.add(entry)
    await db.flush()


async def consume_credits(
    db: AsyncSession,
    organization_id: UUID,
    amount_cents: int,
    request_id: str,
) -> bool:
    """
    Consume credits for a request (prepaid mode).

    - amount_cents must be positive.
    - Enforces overdraft_limit_cents (balance can't go below -overdraft_limit_cents).
    - Returns True if debit succeeded, False if insufficient credits.

    NOTE: Callers must ensure idempotency at a higher level (for example via QuotaCheckRequest)
    so the same (org, request_id) isn't debited twice.
    """
    if amount_cents <= 0:
        raise ValueError("amount_cents must be positive for consume_credits")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Load current overdraft limit
    org_result = await db.execute(select(Organization).where(Organization.id == organization_id))
    org = org_result.scalars().one_or_none()
    if org is None:
        raise ValueError("Organization not found")

    lower_bound = -int(org.overdraft_limit_cents or 0)

    # Atomic debit: ensure new balance >= lower_bound
    from sqlalchemy import and_

    update_stmt = (
        update(Organization)
        .where(
            and_(
                Organization.id == organization_id,
                Organization.prepaid_balance_cents - amount_cents >= lower_bound,
            )
        )
        .values(
            prepaid_balance_cents=Organization.prepaid_balance_cents - amount_cents,
            updated_at=now,
        )
    )
    result = await db.execute(update_stmt)
    if result.rowcount == 0:
        # Insufficient credits (would go below overdraft limit)
        return False

    # Ledger row: negative amount for consume
    entry = CreditLedger(
        id=uuid.uuid4(),
        organization_id=organization_id,
        amount_cents=-amount_cents,
        type="consume",
        reference_id=request_id,
        created_at=now,
    )
    db.add(entry)
    await db.flush()
    return True


async def hold_credits(
    db: AsyncSession,
    organization_id: UUID,
    amount_cents: int,
    request_id: str,
) -> bool:
    """
    Reserve credits by moving them from available to held_balance_cents.
    Enforces overdraft limit on (prepaid_balance_cents - held_balance_cents - amount_cents).
    Returns True if successful, False if insufficient credits.
    """
    if amount_cents < 0:
        raise ValueError("amount_cents must be positive for hold_credits")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    org_result = await db.execute(select(Organization).where(Organization.id == organization_id))
    org = org_result.scalars().one_or_none()
    if org is None:
        raise ValueError("Organization not found")

    lower_bound = -int(org.overdraft_limit_cents or 0)
    
    from sqlalchemy import and_
    update_stmt = (
        update(Organization)
        .where(
            and_(
                Organization.id == organization_id,
                Organization.prepaid_balance_cents - Organization.held_balance_cents - amount_cents >= lower_bound,
            )
        )
        .values(
            held_balance_cents=Organization.held_balance_cents + amount_cents,
            updated_at=now,
        )
    )
    result = await db.execute(update_stmt)
    if result.rowcount == 0:
        return False
    return True


async def commit_credits(
    db: AsyncSession,
    organization_id: UUID,
    held_cents: int,
    actual_cents: int,
    request_id: str,
) -> None:
    """
    Commit a previously held amount.
    Releases held_cents back, and permanently deducts actual_cents from prepaid_balance_cents.
    Records actual_cents in credit_ledger.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    update_stmt = (
        update(Organization)
        .where(Organization.id == organization_id)
        .values(
            held_balance_cents=Organization.held_balance_cents - held_cents,
            prepaid_balance_cents=Organization.prepaid_balance_cents - actual_cents,
            updated_at=now,
        )
    )
    await db.execute(update_stmt)

    if actual_cents > 0:
        entry = CreditLedger(
            id=uuid.uuid4(),
            organization_id=organization_id,
            amount_cents=-actual_cents,
            type="consume",
            reference_id=request_id,
            created_at=now,
        )
        db.add(entry)
    await db.flush()


async def rollback_credits(
    db: AsyncSession,
    organization_id: UUID,
    held_cents: int,
    request_id: str,
) -> None:
    """
    Rollback a hold if the action failed.
    Releases held_cents back to available balance.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    update_stmt = (
        update(Organization)
        .where(Organization.id == organization_id)
        .values(
            held_balance_cents=Organization.held_balance_cents - held_cents,
            updated_at=now,
        )
    )
    await db.execute(update_stmt)
    await db.flush()
