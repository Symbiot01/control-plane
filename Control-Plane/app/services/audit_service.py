"""Audit logging: write to audit_logs table."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def log_audit(
    db: AsyncSession,
    *,
    organization_id: UUID | None = None,
    member_id: UUID | None = None,
    action_key: str,
    result: str,
) -> None:
    """Insert one audit_log row. Call from quota check, org create, invite, role change, member remove."""
    row = AuditLog(
        id=uuid4(),
        organization_id=organization_id,
        member_id=member_id,
        action_key=action_key,
        result=result,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),  # naive UTC for TIMESTAMP WITHOUT TIME ZONE
    )
    db.add(row)
    await db.flush()


async def get_organization_audit_logs(
    db: AsyncSession,
    organization_id: UUID,
    limit: int = 100,
) -> list[AuditLog]:
    """Get recent audit logs for an organization."""
    from sqlalchemy import select
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())

