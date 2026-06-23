#!/usr/bin/env bash
# Test all Control Plane endpoints. Usage: ./scripts/test_endpoints.sh [BASE_URL]
# Requires: .env (for INTERNAL_API_KEY), server running at BASE_URL (default http://127.0.0.1:8000)
# Pass Firebase id_token via ID_TOKEN env var.
# For internal quota/check to return allowed, seed actions first: python scripts/seed_quota_actions.py
# Note: Admin/manual billing internal-key endpoints were removed; only /internal/v1/* uses INTERNAL_API_KEY now.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${1:-http://127.0.0.1:8000}"
ID_TOKEN="${ID_TOKEN:-}"

# Parse JSON key (works without jq)
_json() { python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$1',''))" 2>/dev/null; }

if [[ -z "$ID_TOKEN" ]]; then
  echo "Set ID_TOKEN (Firebase id token) in env."
  echo "Example: ID_TOKEN='eyJ...' $0 $BASE_URL"
  echo ""
fi

# Load INTERNAL_API_KEY from .env
if [[ -f .env ]]; then
  export $(grep -v '^#' .env | grep 'INTERNAL_API_KEY=' | xargs)
fi

echo "=== 1. GET /health ==="
curl -s "$BASE_URL/health"
echo -e "\n"

echo "=== 2. GET /.well-known/jwks.json ==="
curl -s "$BASE_URL/.well-known/jwks.json" | head -c 300
echo -e "\n\n"

if [[ -z "$ID_TOKEN" ]]; then
  echo "Skipping auth and protected endpoints (no ID_TOKEN)."
  echo "=== 3. POST /internal/v1/quota/check (internal API key) ==="
  if [[ -n "$INTERNAL_API_KEY" ]]; then
    curl -s -X POST "$BASE_URL/internal/v1/quota/check" \
      -H "Content-Type: application/json" \
      -H "X-Internal-Api-Key: $INTERNAL_API_KEY" \
      -d '{"organization_id":"00000000-0000-0000-0000-000000000001","action_key":"legal.case.analyze.v1","units":1}'
  else
    echo "INTERNAL_API_KEY not set in .env"
  fi
  echo ""
  exit 0
fi

echo "=== 3. POST /auth/exchange ==="
EXCHANGE=$(curl -s -X POST "$BASE_URL/auth/exchange" \
  -H "Content-Type: application/json" \
  -d "{\"id_token\":\"$ID_TOKEN\"}")
echo "$EXCHANGE"
CONTROL_JWT=$(echo "$EXCHANGE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || true)
if [[ -z "$CONTROL_JWT" ]]; then
  echo "Failed to get Control JWT. Check token and server."
  exit 1
fi
echo "Control JWT obtained."
echo ""

echo "=== 4. GET /members/me ==="
curl -s "$BASE_URL/members/me" -H "Authorization: Bearer $CONTROL_JWT"
echo -e "\n"

echo "=== 5. POST /organizations (create) ==="
ORG_RESP=$(curl -s -X POST "$BASE_URL/organizations" \
  -H "Authorization: Bearer $CONTROL_JWT" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Org from Script"}')
echo "$ORG_RESP"
ORG_ID=$(echo "$ORG_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || true)
if [[ -z "$ORG_ID" ]]; then
  echo "Could not create org. Using placeholder for remaining tests."
  ORG_ID="00000000-0000-0000-0000-000000000001"
else
  echo "Created org_id: $ORG_ID"
  echo "Re-exchanging token so JWT includes org_id (required for org-scoped routes)..."
  EXCHANGE2=$(curl -s -X POST "$BASE_URL/auth/exchange" -H "Content-Type: application/json" -d "{\"id_token\":\"$ID_TOKEN\"}")
  CONTROL_JWT=$(echo "$EXCHANGE2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || true)
  [[ -n "$CONTROL_JWT" ]] && echo "New Control JWT obtained with org context."
fi
echo ""

echo "=== 6. GET /organizations/me ==="
ORGS_ME=$(curl -s "$BASE_URL/organizations/me" -H "Authorization: Bearer $CONTROL_JWT")
echo "$ORGS_ME"
# Use first org in list for scoped routes (JWT org_id is set from first membership after re-exchange)
ORG_SCOPED=$(echo "$ORGS_ME" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if isinstance(d,list) and d else '')" 2>/dev/null || true)
[[ -z "$ORG_SCOPED" ]] && ORG_SCOPED="$ORG_ID"
echo -e "\n"

echo "=== 7. GET /organizations/$ORG_SCOPED ==="
curl -s "$BASE_URL/organizations/$ORG_SCOPED" -H "Authorization: Bearer $CONTROL_JWT"
echo -e "\n"

echo "=== 8. GET /quotas/$ORG_SCOPED ==="
curl -s "$BASE_URL/quotas/$ORG_SCOPED" -H "Authorization: Bearer $CONTROL_JWT"
echo -e "\n"

echo "=== 9. GET /plans ==="
curl -s "$BASE_URL/plans" -H "Authorization: Bearer $CONTROL_JWT"
echo -e "\n"

echo "=== 10. GET /organizations/$ORG_SCOPED/subscriptions/current ==="
curl -s "$BASE_URL/organizations/$ORG_SCOPED/subscriptions/current" -H "Authorization: Bearer $CONTROL_JWT"
echo -e "\n"

echo "=== 11. GET /organizations/$ORG_SCOPED/invoices ==="
curl -s "$BASE_URL/organizations/$ORG_SCOPED/invoices" -H "Authorization: Bearer $CONTROL_JWT"
echo -e "\n"

echo "=== 12. POST /internal/v1/quota/check ==="
if [[ -n "$INTERNAL_API_KEY" ]]; then
  QUOTA_RESP=$(curl -s -X POST "$BASE_URL/internal/v1/quota/check" \
    -H "Content-Type: application/json" \
    -H "X-Internal-Api-Key: $INTERNAL_API_KEY" \
    -d "{\"organization_id\":\"$ORG_SCOPED\",\"action_key\":\"legal.case.analyze.v1\",\"units\":1,\"request_id\":\"e2e-test-$(date +%s)\"}")
  echo "$QUOTA_RESP"
  ALLOWED=$(echo "$QUOTA_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('allowed', False))" 2>/dev/null || echo "false")
  REASON=$(echo "$QUOTA_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('reason',''))" 2>/dev/null || echo "")
  if [[ "$ALLOWED" == "True" || "$ALLOWED" == "true" ]]; then
    echo "(quota check allowed)"
  else
    echo "(quota check denied: ${REASON:-unknown}. To get allowed: seed quota_actions, set org quota limits, and create an active subscription for this org.)"
  fi
else
  echo "INTERNAL_API_KEY not set."
fi
echo -e "\n"

echo "Done."
