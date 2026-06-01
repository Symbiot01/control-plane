"""rename_platform_admin_to_super_admin

Revision ID: f323b6922761
Revises: 4e57d8e75771
Create Date: 2026-08-01 09:01:00.893270

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f323b6922761'
down_revision: Union[str, Sequence[str], None] = '4e57d8e75771'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('platform_admins', 'super_admins')
    op.rename_table('platform_admin_audit_logs', 'super_admin_audit_logs')


def downgrade() -> None:
    """Downgrade schema."""
    op.rename_table('super_admin_audit_logs', 'platform_admin_audit_logs')
    op.rename_table('super_admins', 'platform_admins')
