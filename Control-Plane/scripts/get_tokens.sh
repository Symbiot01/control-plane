#!/usr/bin/env bash
# Create/sign in a Firebase user by email/password, then exchange the Firebase ID token
# for a Control JWT via /auth/exchange.
#
# Usage:
#   ./scripts/get_tokens.sh <EMAIL> <PASSWORD> [BASE_URL]
# Example:
#   ./scripts/get_tokens.sh user@example.com mypassword http://127.0.0.1:8000
#
# Notes:
# - Uses your Firebase project config:
#     apiKey:      AIzaSyDVlV_SrHSDFEO13By3-0V8Fu7nC-Gi72g
#     authDomain:  medrecs-485208.firebaseapp.com
#     projectId:   medrecs-485208
# - If the user does not exist, it will be created via accounts:signUp.

set -e

EMAIL="$1"
PASSWORD="$2"
BASE_URL="${3:-http://127.0.0.1:8000}"

if [[ -z "$EMAIL" || -z "$PASSWORD" ]]; then
  echo "Usage: $0 <EMAIL> <PASSWORD> [BASE_URL]" >&2
  exit 1
fi

FIREBASE_API_KEY="${FIREBASE_API_KEY:-AIzaSyDVlV_SrHSDFEO13By3-0V8Fu7nC-Gi72g}"

json_field() {
  python3 -c "import sys, json; d = json.load(sys.stdin); print(d.get('$1', ''))" 2>/dev/null
}

echo "=== Firebase sign-in (or create) for $EMAIL ==="

SIGNIN_RESPONSE=$(curl -s -X POST \
  "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${FIREBASE_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"returnSecureToken\":true}")

ERROR_MSG=$(echo "$SIGNIN_RESPONSE" | python3 -c "import sys, json; d=json.load(sys.stdin); e=d.get('error',{}); print(e.get('message',''))" 2>/dev/null || true)

if [[ -n "$ERROR_MSG" ]]; then
  echo "Sign-in failed ($ERROR_MSG), attempting sign-up..."
  SIGNUP_RESPONSE=$(curl -s -X POST \
    "https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=${FIREBASE_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"returnSecureToken\":true}")
  ID_TOKEN=$(echo "$SIGNUP_RESPONSE" | json_field "idToken")
else
  ID_TOKEN=$(echo "$SIGNIN_RESPONSE" | json_field "idToken")
fi

if [[ -z "$ID_TOKEN" ]]; then
  echo "Failed to obtain Firebase ID token. Response:" >&2
  echo "$SIGNIN_RESPONSE" >&2
  exit 1
fi

echo "Firebase ID token (idToken):"
echo "$ID_TOKEN"
echo

echo "=== Exchange Firebase ID token for Control JWT at $BASE_URL/auth/exchange ==="
EXCHANGE_RESPONSE=$(curl -s -X POST "${BASE_URL}/auth/exchange" \
  -H "Content-Type: application/json" \
  -d "{\"id_token\":\"${ID_TOKEN}\"}")
echo "$EXCHANGE_RESPONSE"
echo

CONTROL_JWT=$(echo "$EXCHANGE_RESPONSE" | json_field "access_token")

if [[ -z "$CONTROL_JWT" ]]; then
  echo "Failed to obtain Control JWT from /auth/exchange." >&2
  exit 1
fi

echo "Control JWT (access_token):"
echo "$CONTROL_JWT"
echo

echo "You can now use:"
echo "  ID_TOKEN  -> for scripts/test_endpoints.sh via: ID_TOKEN=\"\$ID_TOKEN\" ./scripts/test_endpoints.sh"
echo "  CONTROL_JWT -> as Authorization: Bearer <token> for Control Plane endpoints."

