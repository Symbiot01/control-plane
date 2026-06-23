#!/usr/bin/env bash
#
# Stress-test quota/check for one org until a limit is exceeded and the next call is denied.
# Uses the same org (first org for the authenticated user); each request uses a unique request_id
# so each call consumes quota. Stops when allowed=false and prints the reason.
#
# Usage:
#   ./scripts/stress_test_quota.sh [BASE_URL]
#   ID_TOKEN=<firebase_id_token> ./scripts/stress_test_quota.sh
# Or run get_tokens first and pipe the id token:
#   ID_TOKEN=$(./scripts/get_tokens.sh "sahil0111patel@gmail.com" "test123@" http://127.0.0.1:8000 2>/dev/null | sed -n '/^eyJ/p' | head -1)
#   export ID_TOKEN && ./scripts/stress_test_quota.sh http://127.0.0.1:8000
#
# Expects: seeded org with limits (e.g. per_day=100 for legal.case.analyze.v1).
# Success: script exits 0 when a request is denied (limit exhausted).
# Failure: script exits 1 if no deny after MAX_REQUESTS.
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${1:-http://127.0.0.1:8000}"
ID_TOKEN="${ID_TOKEN:-}"
# Cap requests so we don't run forever if limits are very high
MAX_REQUESTS="${MAX_REQUESTS:-250}"

if [[ -f .env ]]; then
  export $(grep -v '^#' .env | grep 'INTERNAL_API_KEY=' | xargs)
fi

if [[ -z "$ID_TOKEN" ]]; then
  echo "Set ID_TOKEN (Firebase id token). Example: ID_TOKEN=\$(./scripts/get_tokens.sh ... 2>/dev/null | sed -n '/^eyJ/p' | head -1)"
  exit 1
fi
if [[ -z "$INTERNAL_API_KEY" ]]; then
  echo "INTERNAL_API_KEY not set in .env"
  exit 1
fi

echo "=== Exchange token and get first org ==="
EXCHANGE=$(curl -s -X POST "$BASE_URL/auth/exchange" -H "Content-Type: application/json" -d "{\"id_token\":\"$ID_TOKEN\"}")
CONTROL_JWT=$(echo "$EXCHANGE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null)
if [[ -z "$CONTROL_JWT" ]]; then
  echo "Failed to get Control JWT"
  exit 1
fi
ORGS_ME=$(curl -s "$BASE_URL/organizations/me" -H "Authorization: Bearer $CONTROL_JWT")
ORG_ID=$(echo "$ORGS_ME" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if isinstance(d,list) and d else '')" 2>/dev/null)
if [[ -z "$ORG_ID" ]]; then
  echo "No organization found for user. Run seed_test_user.py first."
  exit 1
fi
echo "Using org_id: $ORG_ID"
echo "Sending quota/check requests (action_key=legal.case.analyze.v1, units=1) until denied (max $MAX_REQUESTS)..."
echo ""

RUN_ID="stress-$(date +%s)"
ALLOWED_COUNT=0
LAST_RESPONSE=""

for i in $(seq 1 "$MAX_REQUESTS"); do
  RESP=$(curl -s -X POST "$BASE_URL/internal/v1/quota/check" \
    -H "Content-Type: application/json" \
    -H "X-Internal-Api-Key: $INTERNAL_API_KEY" \
    -d "{\"organization_id\":\"$ORG_ID\",\"action_key\":\"legal.case.analyze.v1\",\"units\":1,\"request_id\":\"${RUN_ID}-${i}\"}")
  LAST_RESPONSE="$RESP"
  ALLOWED=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('allowed', False))" 2>/dev/null)
  REASON=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('reason','') or '')" 2>/dev/null)

  if [[ "$ALLOWED" == "True" || "$ALLOWED" == "true" ]]; then
    ALLOWED_COUNT=$((ALLOWED_COUNT + 1))
    printf "\r  Allowed: %d" "$ALLOWED_COUNT"
  else
    echo ""
    echo "Denied after $ALLOWED_COUNT allowed requests (request #$i)."
    echo "Reason: ${REASON:-unknown}"
    echo "Response: $LAST_RESPONSE"
    echo "Stress test passed: quota/sub limit exhausted and request correctly denied."
    exit 0
  fi
done

echo ""
echo "Sent $MAX_REQUESTS requests; all were allowed. Expected a deny before this (e.g. per_day limit)."
echo "Last response: $LAST_RESPONSE"
exit 1
