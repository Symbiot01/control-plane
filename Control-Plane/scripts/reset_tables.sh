#!/usr/bin/env bash
# Drop all tables in public schema, then run create_tables.sh.
# Run from project root: ./scripts/reset_tables.sh
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

echo "Dropping all tables..."
PGHOST="${POSTGRES_HOST}" \
PGSSLMODE="${POSTGRES_SSLMODE:-disable}" \
PGPORT="${POSTGRES_PORT:-5432}" \
PGUSER="${POSTGRES_USER:-postgres}" \
PGPASSWORD="${POSTGRES_PASSWORD}" \
PGDATABASE="${POSTGRES_DB:-control_plane}" \
psql -v ON_ERROR_STOP=1 <<'SQL'
DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
  END LOOP;
END $$;
SQL

echo "Creating tables..."
"$SCRIPT_DIR/create_tables.sh"

echo "Done."
