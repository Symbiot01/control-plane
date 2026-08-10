#!/usr/bin/env bash
# DEPRECATED for production provisioning.
# Schema source of truth is Alembic: alembic upgrade head
# (see alembic/versions/). This script may drift from the ORM and is kept
# only for emergency local bootstraps.
#
# Create Control Plane tables. Run from project root: ./scripts/create_tables.sh
set -e

echo "WARNING: scripts/create_tables.sh is deprecated. Prefer: alembic upgrade head" >&2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "Missing .env" >&2
  exit 1
fi

export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
while IFS= read -r line; do
  if [[ "$line" =~ ^POSTGRES_ ]]; then
    export "$line"
  fi
done < .env

PGHOST="${POSTGRES_HOST}" \
PGSSLMODE="${POSTGRES_SSLMODE:-disable}" \
PGPORT="${POSTGRES_PORT:-5432}" \
PGUSER="${POSTGRES_USER:-postgres}" \
PGPASSWORD="${POSTGRES_PASSWORD}" \
PGDATABASE="${POSTGRES_DB:-control_plane}" \
psql -v ON_ERROR_STOP=1 <<'SQL'
-- 1. members
CREATE TABLE IF NOT EXISTS members (
  id UUID PRIMARY KEY,
  firebase_uid TEXT UNIQUE NOT NULL,
  email TEXT NOT NULL,
  display_name TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_members_email ON members(email);

-- 2. organizations
CREATE TABLE IF NOT EXISTS organizations (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  tier TEXT NOT NULL DEFAULT 'starter',
  prepaid_balance_cents BIGINT NOT NULL DEFAULT 0,
  held_balance_cents BIGINT NOT NULL DEFAULT 0,
  billing_mode TEXT NOT NULL DEFAULT 'postpay',
  overdraft_limit_cents BIGINT NOT NULL DEFAULT 0,
  entitlements JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_organizations_status ON organizations(status);

-- 3. organization_members
CREATE TABLE IF NOT EXISTS organization_members (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  member_id UUID NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL,
  UNIQUE (organization_id, member_id)
);
CREATE INDEX IF NOT EXISTS idx_org_members_org ON organization_members(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_members_member ON organization_members(member_id);

-- 4. quota_actions
CREATE TABLE IF NOT EXISTS quota_actions (
  id UUID PRIMARY KEY,
  action_key TEXT UNIQUE NOT NULL,
  domain TEXT NOT NULL,
  unit_type TEXT NOT NULL,
  description TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quota_actions_domain ON quota_actions(domain);

-- 5. organization_quota_limits
CREATE TABLE IF NOT EXISTS organization_quota_limits (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  action_id UUID NOT NULL REFERENCES quota_actions(id),
  limit_value BIGINT NOT NULL,
  period TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL,
  UNIQUE (organization_id, action_id, period)
);
CREATE INDEX IF NOT EXISTS idx_org_quota_limits_org ON organization_quota_limits(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_quota_limits_action ON organization_quota_limits(action_id);

-- 6. organization_usage_lifetime
CREATE TABLE IF NOT EXISTS organization_usage_lifetime (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  action_id UUID NOT NULL REFERENCES quota_actions(id),
  used_units BIGINT NOT NULL DEFAULT 0,
  updated_at TIMESTAMP NOT NULL,
  UNIQUE (organization_id, action_id)
);
CREATE INDEX IF NOT EXISTS idx_org_usage_lifetime_org ON organization_usage_lifetime(organization_id);

-- 7. usage_ledger
CREATE TABLE IF NOT EXISTS usage_ledger (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  member_id UUID REFERENCES members(id) ON DELETE SET NULL,
  action_id UUID REFERENCES quota_actions(id) ON DELETE SET NULL,
  units BIGINT NOT NULL,
  unit_type TEXT NOT NULL,
  compute_units BIGINT NOT NULL,
  request_id TEXT,
  created_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_ledger_org ON usage_ledger(organization_id);
CREATE INDEX IF NOT EXISTS idx_usage_ledger_created ON usage_ledger(created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_ledger_org_request_id ON usage_ledger (organization_id, request_id) WHERE request_id IS NOT NULL;

-- 8. plans
CREATE TABLE IF NOT EXISTS plans (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  monthly_price BIGINT NOT NULL,
  included_compute_units BIGINT NOT NULL,
  overage_rate BIGINT NOT NULL,
  currency TEXT NOT NULL DEFAULT 'USD',
  created_at TIMESTAMP NOT NULL
);

-- 9. organization_subscriptions
CREATE TABLE IF NOT EXISTS organization_subscriptions (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
  status TEXT NOT NULL,
  billing_cycle_start TIMESTAMP NOT NULL,
  billing_cycle_end TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_org_subs_org ON organization_subscriptions(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_subs_plan ON organization_subscriptions(plan_id);

-- 9b. quota_action_prices (cents per compute_unit per action; for prepaid and billing)
CREATE TABLE IF NOT EXISTS quota_action_prices (
  id UUID PRIMARY KEY,
  action_id UUID NOT NULL REFERENCES quota_actions(id) ON DELETE CASCADE,
  rate_cents_per_compute_unit BIGINT NOT NULL,
  effective_from TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quota_action_prices_action ON quota_action_prices(action_id);
CREATE INDEX IF NOT EXISTS idx_quota_action_prices_effective ON quota_action_prices(effective_from);

-- 9c. quota_check_requests (idempotency: same request_id => same allow/deny, no double debit)
CREATE TABLE IF NOT EXISTS quota_check_requests (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  request_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'committed',
  allowed BOOLEAN NOT NULL,
  reason TEXT,
  held_units BIGINT,
  held_cents BIGINT,
  created_at TIMESTAMP NOT NULL,
  UNIQUE (organization_id, request_id)
);
CREATE INDEX IF NOT EXISTS idx_quota_check_requests_org ON quota_check_requests(organization_id);

-- 9d. credit_ledger (audit trail: grant, top_up, consume, refund)
CREATE TABLE IF NOT EXISTS credit_ledger (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  amount_cents BIGINT NOT NULL,
  type TEXT NOT NULL,
  reference_id TEXT,
  created_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_org ON credit_ledger(organization_id);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_created ON credit_ledger(created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_ledger_consume_idempotency ON credit_ledger (organization_id, reference_id) WHERE type = 'consume' AND reference_id IS NOT NULL;

-- 10. invoices
CREATE TABLE IF NOT EXISTS invoices (
  id UUID PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  billing_period_start TIMESTAMP NOT NULL,
  billing_period_end TIMESTAMP NOT NULL,
  total_compute_units BIGINT NOT NULL,
  included_units BIGINT NOT NULL,
  overage_units BIGINT NOT NULL,
  amount_due BIGINT NOT NULL,
  credits_applied_cents BIGINT NOT NULL DEFAULT 0,
  amount_paid_cents BIGINT NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  external_id TEXT,
  created_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_invoices_org ON invoices(organization_id);

-- 11. invoice_line_items
CREATE TABLE IF NOT EXISTS invoice_line_items (
  id UUID PRIMARY KEY,
  invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  action_id UUID NOT NULL REFERENCES quota_actions(id) ON DELETE RESTRICT,
  units BIGINT NOT NULL,
  compute_units BIGINT NOT NULL,
  amount BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_invoice_line_items_invoice ON invoice_line_items(invoice_id);

-- 12. audit_logs
CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY,
  organization_id UUID,
  member_id UUID,
  action_key TEXT,
  result TEXT,
  created_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_org ON audit_logs(organization_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_member ON audit_logs(member_id);

-- 13. platform_admins
CREATE TABLE IF NOT EXISTS platform_admins (
  id UUID PRIMARY KEY,
  member_id UUID NOT NULL UNIQUE REFERENCES members(id) ON DELETE CASCADE,
  created_at TIMESTAMP NOT NULL
);

-- 14. platform_admin_audit_logs
CREATE TABLE IF NOT EXISTS platform_admin_audit_logs (
  id UUID PRIMARY KEY,
  admin_member_id UUID NOT NULL REFERENCES members(id),
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id UUID,
  detail TEXT,
  created_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_admin_audit_admin ON platform_admin_audit_logs(admin_member_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_created ON platform_admin_audit_logs(created_at);

-- 15. products
CREATE TABLE IF NOT EXISTS products (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  product_key TEXT UNIQUE NOT NULL,
  description TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_products_key ON products(product_key);

SQL

echo "Tables created successfully."
