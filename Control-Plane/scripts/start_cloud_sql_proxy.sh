#!/usr/bin/env bash
# Start Cloud SQL Auth Proxy for local dev (connects app to control-plane-db-v1).
#
# Prerequisites (GCP console, project medrecs-485208):
#   Grant roles/cloudsql.client to the service account used below, OR run:
#     gcloud auth application-default login
#     gcloud config set project medrecs-485208
#
# Usage:
#   ./scripts/start_cloud_sql_proxy.sh
#   # then in another terminal: uvicorn app.main:app --reload --port 8000
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ENV_FILE:-${BACKEND_DIR}/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing .env at: $ENV_FILE" >&2
  exit 1
fi

PYTHON="${BACKEND_DIR}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

get_env() {
  ENV_FILE="$ENV_FILE" "$PYTHON" -c "
import os, sys
from dotenv import dotenv_values
val = dotenv_values(os.environ['ENV_FILE']).get(sys.argv[1], '') or ''
print(val, end='')
" "$1"
}

DATABASE_URL="$(get_env DATABASE_URL)"
if [[ -z "$DATABASE_URL" ]]; then
  echo "Set DATABASE_URL in $ENV_FILE" >&2
  exit 1
fi

# DATABASE_URL contains the PostgreSQL credentials/database, but Cloud SQL
# Proxy additionally requires project:region:instance. Allow an override for
# other environments and default to the instance this script is dedicated to.
DEFAULT_INSTANCE="medrecs-485208:us-central1:control-plane-db-v1"
INSTANCE="$(get_env CLOUD_SQL_INSTANCE)"
INSTANCE="${INSTANCE:-$DEFAULT_INSTANCE}"
PORT="$(get_env CLOUD_SQL_PROXY_PORT)"
PORT="${PORT:-5433}"

# Parse and validate without echoing the username or password.
DB_DETAILS="$(DATABASE_URL="$DATABASE_URL" "$PYTHON" -c "
import os
from urllib.parse import urlsplit

url = os.environ['DATABASE_URL']
parsed = urlsplit(url.replace('postgresql+asyncpg://', 'postgresql://', 1))
if parsed.scheme not in {'postgresql', 'postgres'}:
    raise SystemExit('DATABASE_URL must use PostgreSQL')
if not parsed.hostname or not parsed.path.lstrip('/'):
    raise SystemExit('DATABASE_URL must include host and database name')
print(f'{parsed.hostname}|{parsed.port or 5432}|{parsed.path.lstrip(\"/\")}', end='')
")"
IFS='|' read -r DB_HOST DB_PORT DB_NAME <<< "$DB_DETAILS"

PROXY_BIN="${CLOUD_SQL_PROXY_BIN:-}"
if [[ -z "$PROXY_BIN" ]]; then
  for candidate in \
    "${BACKEND_DIR}/bin/cloud-sql-proxy" \
    "${HOME}/.local/bin/cloud-sql-proxy" \
    "/tmp/cloud-sql-proxy" \
    "$(command -v cloud-sql-proxy 2>/dev/null || true)"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      PROXY_BIN="$candidate"
      break
    fi
  done
fi

if [[ -z "$PROXY_BIN" || ! -x "$PROXY_BIN" ]]; then
  echo "cloud-sql-proxy not found. Downloading to ${BACKEND_DIR}/bin/cloud-sql-proxy ..."
  mkdir -p "${BACKEND_DIR}/bin"
  curl -fsSL -o "${BACKEND_DIR}/bin/cloud-sql-proxy" \
    "https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.3/cloud-sql-proxy.linux.amd64"
  chmod +x "${BACKEND_DIR}/bin/cloud-sql-proxy"
  PROXY_BIN="${BACKEND_DIR}/bin/cloud-sql-proxy"
fi

# Prefer the explicit local credential file. Fall back to materializing the
# service-account JSON from .env, then to Application Default Credentials.
CREDS_FILE="${BACKEND_DIR}/.cloud-sql-proxy-credentials.json"
SA_JSON="$(get_env GCP_SERVICE_ACCOUNT_JSON)"
PROXY_CREDS_ARGS=()

if [[ -f "$CREDS_FILE" ]]; then
  chmod 600 "$CREDS_FILE"
  PROXY_CREDS_ARGS=(--credentials-file "$CREDS_FILE")
  echo "Using credential file: $CREDS_FILE"
elif [[ -n "$SA_JSON" ]]; then
  SA_EMAIL="$(ENV_FILE="$ENV_FILE" "$PYTHON" -c "
import json, os
from dotenv import dotenv_values
raw = dotenv_values(os.environ['ENV_FILE']).get('GCP_SERVICE_ACCOUNT_JSON', '')
data = json.loads(raw)
with open('${CREDS_FILE}', 'w', encoding='utf-8') as f:
    f.write(json.dumps(data))
os.chmod('${CREDS_FILE}', 0o600)
print(data.get('client_email', 'unknown'), end='')
")"
  export GOOGLE_APPLICATION_CREDENTIALS="$CREDS_FILE"
  PROXY_CREDS_ARGS=(--credentials-file "$CREDS_FILE")
  echo "Using GCP_SERVICE_ACCOUNT_JSON → ${SA_EMAIL}"
elif [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
  echo "Using GOOGLE_APPLICATION_CREDENTIALS=${GOOGLE_APPLICATION_CREDENTIALS}"
else
  echo "No GCP_SERVICE_ACCOUNT_JSON set; proxy will use gcloud application-default credentials." >&2
fi

echo "Starting Cloud SQL proxy"
echo "  instance: $INSTANCE"
echo "  database: $DB_NAME"
echo "  remote:   $DB_HOST:$DB_PORT"
echo "  listen:   127.0.0.1:${PORT}"
echo "  binary:   $PROXY_BIN"
echo
echo "Connect through 127.0.0.1:${PORT} using the user/password/database from DATABASE_URL."
echo "Press Ctrl+C to stop."
echo

exec "$PROXY_BIN" "${PROXY_CREDS_ARGS[@]}" "$INSTANCE" --port "$PORT"
