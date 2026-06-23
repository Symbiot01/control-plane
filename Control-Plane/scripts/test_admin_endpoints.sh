#!/usr/bin/env bash
# E2E test for admin API. Usage: CONTROL_JWT='<token>' ./scripts/test_admin_endpoints.sh [BASE_URL]
# Prerequisite: server running; platform admin via scripts/seed_platform_admin.py
# Get CONTROL_JWT from scripts/get_tokens.sh (use the access_token for a user that is a platform admin).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${1:-http://127.0.0.1:8000}"
BASE_URL="${BASE_URL%/}"
CONTROL_JWT="${CONTROL_JWT:-}"

if [[ -z "$CONTROL_JWT" ]]; then
  echo "Set CONTROL_JWT in env (Bearer token for a platform admin)."
  echo "Example: CONTROL_JWT='eyJ...' $0 $BASE_URL"
  exit 1
fi

AUTH_HEADER="Authorization: Bearer $CONTROL_JWT"

# Helper: print status and body
_req() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  local url="${BASE_URL}/admin/v1${path}"
  if [[ "$method" == "GET" ]]; then
    curl -s -w "\nHTTP_STATUS:%{http_code}" -H "$AUTH_HEADER" "$url"
  else
    curl -s -w "\nHTTP_STATUS:%{http_code}" -X "$method" -H "$AUTH_HEADER" -H "Content-Type: application/json" -d "$data" "$url"
  fi
}

echo "=== 1. GET /admin/v1/stats ==="
OUT=$(_req GET "/stats")
BODY=$(echo "$OUT" | sed '/^HTTP_STATUS:/d')
STATUS=$(echo "$OUT" | grep '^HTTP_STATUS:' | cut -d: -f2)
echo "$BODY" | head -c 500
echo ""
echo "Status: $STATUS"
[[ "$STATUS" != "200" ]] && echo "Expected 200 from /admin/v1/stats. Is this user a platform admin?" && exit 1
echo ""

echo "=== 2. GET /admin/v1/organizations ==="
OUT=$(_req GET "/organizations")
BODY=$(echo "$OUT" | sed '/^HTTP_STATUS:/d')
STATUS=$(echo "$OUT" | grep '^HTTP_STATUS:' | cut -d: -f2)
echo "$BODY" | head -c 800
echo ""
ORG_ID=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if isinstance(d,list) and len(d) else '')" 2>/dev/null || true)
if [[ -z "$ORG_ID" ]]; then
  echo "No orgs in list. Create an org via normal API first. Using placeholder for read-only tests."
  ORG_ID="00000000-0000-0000-0000-000000000001"
else
  echo "Using org_id: $ORG_ID"
fi
echo ""

echo "=== 3. GET /admin/v1/organizations/$ORG_ID ==="
OUT=$(_req GET "/organizations/$ORG_ID")
echo "$OUT" | sed '/^HTTP_STATUS:/d'
echo ""

echo "=== 4. PATCH /admin/v1/organizations/$ORG_ID/suspend ==="
OUT=$(_req PATCH "/organizations/$ORG_ID/suspend")
echo "$OUT" | sed '/^HTTP_STATUS:/d'
echo ""

echo "=== 5. PATCH /admin/v1/organizations/$ORG_ID/activate ==="
OUT=$(_req PATCH "/organizations/$ORG_ID/activate")
echo "$OUT" | sed '/^HTTP_STATUS:/d'
echo ""

echo "=== 6. GET /admin/v1/plans ==="
OUT=$(_req GET "/plans")
BODY=$(echo "$OUT" | sed '/^HTTP_STATUS:/d')
PLAN_ID=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if isinstance(d,list) and len(d) else '')" 2>/dev/null || true)
echo "$BODY" | head -c 400
echo ""
echo ""

echo "=== 7. POST /admin/v1/plans (create) ==="
OUT=$(_req POST "/plans" '{"name":"Admin Test Plan","monthly_price":1999,"included_compute_units":5000,"overage_rate":2,"currency":"USD"}')
BODY=$(echo "$OUT" | sed '/^HTTP_STATUS:/d')
NEW_PLAN_ID=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || true)
echo "$BODY"
[[ -z "$NEW_PLAN_ID" ]] && NEW_PLAN_ID="$PLAN_ID"
echo ""

echo "=== 8. PATCH /admin/v1/plans/$NEW_PLAN_ID ==="
OUT=$(_req PATCH "/plans/$NEW_PLAN_ID" '{"monthly_price":2499}')
echo "$OUT" | sed '/^HTTP_STATUS:/d'
echo ""

echo "=== 9. GET /admin/v1/actions (list) ==="
OUT=$(_req GET "/actions?limit=5")
echo "$OUT" | sed '/^HTTP_STATUS:/d' | head -c 600
echo ""
echo ""

ACTION_KEY="admin.test.$(date +%s)"
echo "=== 10. POST /admin/v1/actions (create) ==="
OUT=$(_req POST "/actions" "{\"action_key\":\"$ACTION_KEY\",\"domain\":\"admin-test\",\"unit_type\":\"tokens\",\"description\":\"created by test_admin_endpoints.sh\"}")
echo "$OUT" | sed '/^HTTP_STATUS:/d'
echo ""

echo "=== 11. PATCH /admin/v1/actions/$ACTION_KEY (disable) ==="
OUT=$(_req PATCH "/actions/$ACTION_KEY" '{"is_active":false}')
echo "$OUT" | sed '/^HTTP_STATUS:/d'
echo ""

echo "=== 12. DELETE /admin/v1/actions/$ACTION_KEY ==="
OUT=$(_req DELETE "/actions/$ACTION_KEY" '{}')
echo "$OUT" | sed '/^HTTP_STATUS:/d'
echo ""

echo "=== 13. POST /admin/v1/organizations/$ORG_ID/subscriptions ==="
# Use first day of current month to last day
START=$(date -u +%Y-%m-01T00:00:00)
END=$(date -u -d "$(date -u +%Y-%m-01) +1 month -1 day" +%Y-%m-%dT23:59:59 2>/dev/null || date -u +%Y-%m-%dT23:59:59)
OUT=$(_req POST "/organizations/$ORG_ID/subscriptions" "{\"plan_id\":\"$NEW_PLAN_ID\",\"billing_cycle_start\":\"$START\",\"billing_cycle_end\":\"$END\"}")
BODY=$(echo "$OUT" | sed '/^HTTP_STATUS:/d')
SUB_ID=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || true)
echo "$BODY" | head -c 400
echo ""
echo ""

echo "=== 14. GET /admin/v1/organizations/$ORG_ID/subscriptions/current ==="
OUT=$(_req GET "/organizations/$ORG_ID/subscriptions/current")
echo "$OUT" | sed '/^HTTP_STATUS:/d'
echo ""

if [[ -n "$SUB_ID" ]]; then
  echo "=== 15. PATCH /admin/v1/subscriptions/$SUB_ID/status (cancel) ==="
  OUT=$(_req PATCH "/subscriptions/$SUB_ID/status" '{"status":"canceled"}')
  echo "$OUT" | sed '/^HTTP_STATUS:/d'
  echo ""
fi

echo "=== 16. POST /admin/v1/organizations/$ORG_ID/credits/grant ==="
OUT=$(_req POST "/organizations/$ORG_ID/credits/grant" '{"amount_cents":500,"type":"grant","reference_id":"test-admin-script"}')
echo "$OUT" | sed '/^HTTP_STATUS:/d'
echo ""

echo "=== 17. GET /admin/v1/organizations/$ORG_ID/credits ==="
OUT=$(_req GET "/organizations/$ORG_ID/credits")
echo "$OUT" | sed '/^HTTP_STATUS:/d'
echo ""

echo "=== 18. GET /admin/v1/organizations/$ORG_ID/credits/ledger ==="
OUT=$(_req GET "/organizations/$ORG_ID/credits/ledger")
echo "$OUT" | sed '/^HTTP_STATUS:/d' | head -c 500
echo ""
echo ""

echo "=== 19. POST /admin/v1/organizations/$ORG_ID/invoices/generate ==="
END=$(date -u +%Y-%m-%dT23:59:59)
OUT=$(_req POST "/organizations/$ORG_ID/invoices/generate" "{\"billing_period_end\":\"$END\"}")
BODY=$(echo "$OUT" | sed '/^HTTP_STATUS:/d')
INV_ID=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('invoice_id',''))" 2>/dev/null || true)
echo "$BODY"
echo ""

if [[ -n "$INV_ID" ]]; then
  echo "=== 20. GET /admin/v1/invoices/$INV_ID ==="
  OUT=$(_req GET "/invoices/$INV_ID")
  echo "$OUT" | sed '/^HTTP_STATUS:/d' | head -c 600
  echo ""
  echo ""

  echo "=== 21. PATCH /admin/v1/invoices/$INV_ID/status ==="
  OUT=$(_req PATCH "/invoices/$INV_ID/status" '{"status":"paid"}')
  echo "$OUT" | sed '/^HTTP_STATUS:/d'
  echo ""

  echo "=== 22. PATCH /admin/v1/invoices/$INV_ID/payment ==="
  OUT=$(_req PATCH "/invoices/$INV_ID/payment" '{"amount_paid_cents":2499,"credits_applied_cents":0}')
  echo "$OUT" | sed '/^HTTP_STATUS:/d'
  echo ""
fi

echo "=== 23. GET /admin/v1/admins ==="
OUT=$(_req GET "/admins")
echo "$OUT" | sed '/^HTTP_STATUS:/d'
echo ""

echo "=== 24. GET /admin/v1/audit-log ==="
OUT=$(_req GET "/audit-log?limit=5")
echo "$OUT" | sed '/^HTTP_STATUS:/d' | head -c 800
echo ""
echo ""

echo "Done."
