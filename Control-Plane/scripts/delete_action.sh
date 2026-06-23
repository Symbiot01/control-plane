#!/usr/bin/env bash
# Hard-delete one quota action (removes row; fails if used in invoice_line_items). Run from project root.
# Usage: ./scripts/delete_action.sh <action_key>
# Example: ./scripts/delete_action.sh genetic.flow.v1
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
if [[ -z "$ACTION_KEY" ]]; then
  echo "Usage: $0 <action_key>" >&2
  echo "Example: $0 genetic.flow.v1" >&2
  exit 1
fi

PGHOST="${POSTGRES_HOST}" \
PGSSLMODE="${POSTGRES_SSLMODE:-disable}" \
PGPORT="${POSTGRES_PORT:-5432}" \
PGUSER="${POSTGRES_USER:-postgres}" \
PGPASSWORD="${POSTGRES_PASSWORD}" \
PGDATABASE="${POSTGRES_DB:-control_plane}" \
psql -v ON_ERROR_STOP=1 -v ak="$ACTION_KEY" <<'SQL'
DELETE FROM quota_actions WHERE action_key = :'ak';
SQL

echo "Deleted: $ACTION_KEY"
