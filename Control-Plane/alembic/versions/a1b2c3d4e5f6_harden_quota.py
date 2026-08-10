"""Harden quota accounting: unique request ids, buckets, reservation allocations."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6_harden_quota"
down_revision: Union[str, Sequence[str], None] = "c9af54ae28b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Expand quota_check_requests ---
    op.add_column(
        "quota_check_requests",
        sa.Column("member_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "quota_check_requests",
        sa.Column("operation", sa.String(), nullable=False, server_default="check"),
    )
    op.add_column(
        "quota_check_requests",
        sa.Column("request_fingerprint", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "quota_check_requests",
        sa.Column("held_compute_units", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "quota_check_requests",
        sa.Column("rate_cents_per_compute_unit", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "quota_check_requests",
        sa.Column("actual_units", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "quota_check_requests",
        sa.Column("actual_compute_units", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "quota_check_requests",
        sa.Column("actual_cost_cents", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "quota_check_requests",
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "quota_check_requests",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_foreign_key(
        "fk_quota_check_requests_member_id",
        "quota_check_requests",
        "members",
        ["member_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Backfill updated_at and normalize denied rows that used default status=committed
    op.execute(
        """
        UPDATE quota_check_requests
        SET updated_at = created_at
        WHERE updated_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE quota_check_requests
        SET status = 'denied'
        WHERE allowed = false AND status = 'committed'
        """
    )
    op.execute(
        """
        UPDATE quota_check_requests
        SET expires_at = created_at + INTERVAL '1 hour'
        WHERE status = 'held' AND expires_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE quota_check_requests
        SET operation = CASE WHEN status = 'held' THEN 'reserve' ELSE 'check' END
        WHERE operation = 'check' AND status IN ('held', 'rolled_back')
        """
    )
    op.alter_column("quota_check_requests", "updated_at", nullable=False)

    # Deduplicate before UNIQUE: keep newest row per (org, request_id)
    op.execute(
        """
        DELETE FROM quota_check_requests q
        USING quota_check_requests newer
        WHERE q.organization_id = newer.organization_id
          AND q.request_id = newer.request_id
          AND q.created_at < newer.created_at
        """
    )
    op.execute(
        """
        DELETE FROM quota_check_requests q
        USING quota_check_requests newer
        WHERE q.organization_id = newer.organization_id
          AND q.request_id = newer.request_id
          AND q.created_at = newer.created_at
          AND q.id < newer.id
        """
    )

    op.create_unique_constraint(
        "uq_quota_check_requests_org_request",
        "quota_check_requests",
        ["organization_id", "request_id"],
    )
    op.create_index(
        "ix_quota_check_requests_held_expires",
        "quota_check_requests",
        ["expires_at"],
        unique=False,
        postgresql_where=sa.text("status = 'held'"),
    )

    # --- Usage buckets ---
    op.create_table(
        "quota_usage_buckets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("used_units", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reserved_units", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["action_id"], ["quota_actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "action_id",
            "period",
            "window_start",
            name="uq_quota_usage_buckets_org_action_period_window",
        ),
    )
    op.create_index(
        "ix_quota_usage_buckets_organization_id",
        "quota_usage_buckets",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_quota_usage_buckets_action_id",
        "quota_usage_buckets",
        ["action_id"],
        unique=False,
    )

    op.create_table(
        "quota_reservation_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("bucket_id", sa.Uuid(), nullable=False),
        sa.Column("units", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bucket_id"], ["quota_usage_buckets.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"], ["quota_check_requests.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reservation_id",
            "bucket_id",
            name="uq_quota_reservation_allocations_res_bucket",
        ),
    )
    op.create_index(
        "ix_quota_reservation_allocations_reservation_id",
        "quota_reservation_allocations",
        ["reservation_id"],
        unique=False,
    )
    op.create_index(
        "ix_quota_reservation_allocations_bucket_id",
        "quota_reservation_allocations",
        ["bucket_id"],
        unique=False,
    )

    # Backfill lifetime used_units from organization_usage_lifetime
    op.execute(
        """
        INSERT INTO quota_usage_buckets (
            id, organization_id, action_id, period, window_start, used_units, reserved_units, updated_at
        )
        SELECT
            gen_random_uuid(),
            organization_id,
            action_id,
            'lifetime',
            TIMESTAMP '1970-01-01 00:00:00',
            used_units,
            0,
            updated_at
        FROM organization_usage_lifetime
        ON CONFLICT (organization_id, action_id, period, window_start) DO UPDATE
        SET used_units = EXCLUDED.used_units,
            updated_at = EXCLUDED.updated_at
        """
    )

    # Backfill day/month used_units from usage_ledger
    op.execute(
        """
        INSERT INTO quota_usage_buckets (
            id, organization_id, action_id, period, window_start, used_units, reserved_units, updated_at
        )
        SELECT
            gen_random_uuid(),
            organization_id,
            action_id,
            'per_day',
            date_trunc('day', created_at),
            COALESCE(SUM(units), 0),
            0,
            MAX(created_at)
        FROM usage_ledger
        WHERE action_id IS NOT NULL
        GROUP BY organization_id, action_id, date_trunc('day', created_at)
        ON CONFLICT (organization_id, action_id, period, window_start) DO UPDATE
        SET used_units = EXCLUDED.used_units,
            updated_at = EXCLUDED.updated_at
        """
    )
    op.execute(
        """
        INSERT INTO quota_usage_buckets (
            id, organization_id, action_id, period, window_start, used_units, reserved_units, updated_at
        )
        SELECT
            gen_random_uuid(),
            organization_id,
            action_id,
            'per_month',
            date_trunc('month', created_at),
            COALESCE(SUM(units), 0),
            0,
            MAX(created_at)
        FROM usage_ledger
        WHERE action_id IS NOT NULL
        GROUP BY organization_id, action_id, date_trunc('month', created_at)
        ON CONFLICT (organization_id, action_id, period, window_start) DO UPDATE
        SET used_units = EXCLUDED.used_units,
            updated_at = EXCLUDED.updated_at
        """
    )

    # Defensive unique indexes for ledger idempotency
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_usage_ledger_org_request
        ON usage_ledger (organization_id, request_id)
        WHERE request_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_ledger_org_consume_ref
        ON credit_ledger (organization_id, reference_id)
        WHERE type = 'consume' AND reference_id IS NOT NULL
        """
    )

    # Drop server defaults that were only for backfill convenience
    op.alter_column("quota_check_requests", "operation", server_default=None)
    op.alter_column("quota_check_requests", "request_fingerprint", server_default=None)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_credit_ledger_org_consume_ref")
    op.execute("DROP INDEX IF EXISTS uq_usage_ledger_org_request")
    op.drop_index(
        "ix_quota_reservation_allocations_bucket_id",
        table_name="quota_reservation_allocations",
    )
    op.drop_index(
        "ix_quota_reservation_allocations_reservation_id",
        table_name="quota_reservation_allocations",
    )
    op.drop_table("quota_reservation_allocations")
    op.drop_index("ix_quota_usage_buckets_action_id", table_name="quota_usage_buckets")
    op.drop_index(
        "ix_quota_usage_buckets_organization_id", table_name="quota_usage_buckets"
    )
    op.drop_table("quota_usage_buckets")
    op.drop_index("ix_quota_check_requests_held_expires", table_name="quota_check_requests")
    op.drop_constraint(
        "uq_quota_check_requests_org_request", "quota_check_requests", type_="unique"
    )
    op.drop_constraint(
        "fk_quota_check_requests_member_id", "quota_check_requests", type_="foreignkey"
    )
    op.drop_column("quota_check_requests", "updated_at")
    op.drop_column("quota_check_requests", "expires_at")
    op.drop_column("quota_check_requests", "actual_cost_cents")
    op.drop_column("quota_check_requests", "actual_compute_units")
    op.drop_column("quota_check_requests", "actual_units")
    op.drop_column("quota_check_requests", "rate_cents_per_compute_unit")
    op.drop_column("quota_check_requests", "held_compute_units")
    op.drop_column("quota_check_requests", "request_fingerprint")
    op.drop_column("quota_check_requests", "operation")
    op.drop_column("quota_check_requests", "member_id")
