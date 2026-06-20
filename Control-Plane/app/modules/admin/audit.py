"""Admin audit: log_admin_action – write to super_admin_audit_logs."""

import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import SuperAdminAuditLog


async def log_admin_action(
    db: AsyncSession,
    admin_member_id: UUID,
    action: str,
    target_type: str,
    target_id: UUID | None = None,
    detail: str | None = None,
) -> None:
    """Append one row to super_admin_audit_logs. Call after every admin write."""
    entry = SuperAdminAuditLog(
        id=uuid.uuid4(),
        admin_member_id=admin_member_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(entry)
    await db.flush()
