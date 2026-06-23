#!/usr/bin/env bash
# List all quota_actions in the database. Run from project root: ./scripts/list_actions.sh
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

PGHOST="${POSTGRES_HOST}" \
PGSSLMODE="${POSTGRES_SSLMODE:-disable}" \
PGPORT="${POSTGRES_PORT:-5432}" \
PGUSER="${POSTGRES_USER:-postgres}" \
PGPASSWORD="${POSTGRES_PASSWORD}" \
PGDATABASE="${POSTGRES_DB:-control_plane}" \
psql -v ON_ERROR_STOP=1 <<'SQL'
SELECT id, action_key, domain, unit_type, description, is_active, created_at
FROM quota_actions
ORDER BY domain, action_key;
SQL
