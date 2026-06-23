#!/usr/bin/env bash
# Add one quota action (and a default price row). Run from project root.
# Usage: ./scripts/add_action.sh <action_key> <domain> <unit_type> [description]
# Example: ./scripts/add_action.sh genetic.flow.v1 genetic tokens "Genetic flow"
set -e

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

ACTION_KEY="${1:-}"
DOMAIN="${2:-}"
UNIT_TYPE="${3:-}"
DESCRIPTION="${4:-}"

if [[ -z "$ACTION_KEY" || -z "$DOMAIN" || -z "$UNIT_TYPE" ]]; then
  echo "Usage: $0 <action_key> <domain> <unit_type> [description]" >&2
  echo "Example: $0 genetic.flow.v1 genetic tokens \"Genetic flow\"" >&2
  exit 1
fi

PGHOST="${POSTGRES_HOST}" \
PGSSLMODE="${POSTGRES_SSLMODE:-disable}" \
PGPORT="${POSTGRES_PORT:-5432}" \
PGUSER="${POSTGRES_USER:-postgres}" \
PGPASSWORD="${POSTGRES_PASSWORD}" \
PGDATABASE="${POSTGRES_DB:-control_plane}" \
psql -v ON_ERROR_STOP=1 -v ak="$ACTION_KEY" -v dom="$DOMAIN" -v ut="$UNIT_TYPE" -v desc="$DESCRIPTION" <<'SQL'
INSERT INTO quota_actions (id, action_key, domain, unit_type, description, is_active, created_at)
VALUES (gen_random_uuid(), :'ak', :'dom', :'ut', NULLIF(TRIM(:'desc'), ''), true, NOW())
ON CONFLICT (action_key) DO NOTHING;

INSERT INTO quota_action_prices (id, action_id, rate_cents_per_compute_unit, effective_from, created_at)
SELECT gen_random_uuid(), q.id, 1, NOW(), NOW()
FROM quota_actions q
WHERE q.action_key = :'ak'
AND NOT EXISTS (SELECT 1 FROM quota_action_prices qap WHERE qap.action_id = q.id);
SQL

echo "Added (or already exists): $ACTION_KEY"
