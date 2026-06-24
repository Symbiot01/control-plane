# Admin

This document describes the **admin** API and how to build or integrate a frontend for the Control Plane admin area: authentication (Firebase → Control JWT), super-admins authorization, and all admin endpoints.

Note: the provided React console (`org-nexus-console`) is user-console only (no `/admin/*` UI routes). Use this doc when building an admin UI for super admins.

---

## 1. Overview

- **Admin API base path:** `{BASE_URL}/admin/v1`
- **Auth:** Same as the rest of the Control Plane — Firebase sign-in, then exchange the Firebase ID token for a Control JWT. All admin requests use the Control JWT in `Authorization: Bearer <token>`.
- **Authorization:** Only users listed in the **super_admins** table can call admin endpoints. Others get `403 Forbidden` with `{"detail": "Not a super admin"}`.
- **Bootstrap:** The first admin is added via the script `scripts/seed_super_admin.py` (e.g. `sahil0111patel@gmail.com`). After that, existing admins can add more via `POST /admin/v1/admins`.

---

## 2. Authentication flow

### 2.1 Firebase login

Use Firebase Authentication in your frontend (e.g. Firebase JS SDK) to sign in with email/password (or another provider). After sign-in, obtain the Firebase ID token:

```javascript
import { getAuth, signInWithEmailAndPassword } from "firebase/auth";

const auth = getAuth(app);
const userCred = await signInWithEmailAndPassword(auth, email, password);
const idToken = await userCred.user.getIdToken();
```

### 2.2 Exchange for Control JWT

**Request**

- **Method:** `POST`
- **URL:** `{BASE_URL}/auth/exchange`
- **Headers:** `Content-Type: application/json`
- **Body:** `{ "id_token": "<firebase_id_token>" }`

**Response (200)**

```json
{
  "access_token": "<control_jwt>",
  "token_type": "bearer",
  "expires_in": 5400
}
```

Use `access_token` as the Control JWT for all admin API calls.

**Errors:** `401` — Invalid or expired Firebase token.

### 2.3 Using the Control JWT for admin

For every admin request:

- **Header:** `Authorization: Bearer <control_jwt>`
- **URL:** `{BASE_URL}/admin/v1/<path>`

If the user is not a super admin, admin endpoints return **403 Forbidden** with `{"detail": "Not a super admin"}`.

### 2.4 Checking if the user is a super admin

1. **Probe an admin endpoint** — Call e.g. `GET {BASE_URL}/admin/v1/stats`.  
   - **200** → user is a super admin; show admin UI.  
   - **403** → not a super admin; show “Access denied” or redirect.

2. **List admins (if already admin)** — `GET {BASE_URL}/admin/v1/admins` returns the list of super admins.

**Recommended:** After Firebase login and exchange, call `GET /admin/v1/stats`. If 200, treat the user as admin and load the admin app; if 403, treat as non-admin.

---

## 3. Adding the first admin

The backend does not allow self-service admin sign-up. The first admin is added by running the seed script (the member must already exist, e.g. after one successful `/auth/exchange` with that email):

```bash
# From project root
python scripts/seed_super_admin.py sahil0111patel@gmail.com
```

Or with no argument (uses default email from the script):

```bash
python scripts/seed_super_admin.py
```

Ensure the user has signed in at least once (Firebase + exchange) so a `members` row exists for that email.

---

## 4. Admin API endpoints reference

Base URL for all below: **`{BASE_URL}/admin/v1`**.  
All require: **`Authorization: Bearer <control_jwt>`**.

### 4.1 Dashboard

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/stats` | Dashboard counters | `total_orgs`, `active_orgs`, `suspended_orgs`, `archived_orgs`, `active_subscriptions`, `draft_invoices`, `overdue_invoices`, `total_members` |

### 4.2 Organizations

| Method | Path | Description | Query / Body | Response |
|--------|------|-------------|--------------|----------|
| GET | `/organizations` | List all orgs | Query: `status`, `search`, `offset`, `limit` | List of `AdminOrgResponse` |
| GET | `/organizations/{org_id}` | Org detail | — | `AdminOrgResponse` (includes `prepaid_balance_cents`, `billing_mode`, `overdraft_limit_cents`, `members_count`) |
| PATCH | `/organizations/{org_id}` | Update org | Body: `status`, `tier`, `billing_mode`, `overdraft_limit_cents` (all optional) | `AdminOrgResponse` |
| PATCH | `/organizations/{org_id}/suspend` | Set status = suspended | — | `AdminOrgResponse` |
| PATCH | `/organizations/{org_id}/activate` | Set status = active | — | `AdminOrgResponse` |
| GET | `/organizations/{org_id}/members` | List org members | — | Array of `{ member_id, email, display_name, role }` |

### 4.3 Subscriptions

| Method | Path | Description | Body | Response |
|--------|------|-------------|------|----------|
| GET | `/organizations/{org_id}/subscriptions` | List all subscriptions for org | — | List of `SubscriptionResponse` |
| GET | `/organizations/{org_id}/subscriptions/current` | Current active subscription | — | `SubscriptionResponse` or null |
| POST | `/organizations/{org_id}/subscriptions` | Create subscription | `plan_id`, `billing_cycle_start`, `billing_cycle_end` (ISO datetime) | `SubscriptionResponse` |
| PATCH | `/subscriptions/{sub_id}/status` | Update status | `{ "status": "active" \| "canceled" \| "past_due" \| "trialing" }` | `SubscriptionResponse` |
| POST | `/subscriptions/{sub_id}/change-plan` | Change plan (cancel current, create new) | `new_plan_id`, `new_billing_cycle_start`, `new_billing_cycle_end` | `SubscriptionResponse` (new sub) |

### 4.4 Invoices

| Method | Path | Description | Query / Body | Response |
|--------|------|-------------|--------------|----------|
| GET | `/organizations/{org_id}/invoices` | List invoices | Query: `status` (optional) | List of `AdminInvoiceResponse` |
| GET | `/invoices/{invoice_id}` | Invoice detail + line items | — | `AdminInvoiceResponse` |
| POST | `/organizations/{org_id}/invoices/generate` | Generate next invoice ending at a date | Body: `billing_period_end` (ISO datetime) | `{ "invoice_id": "<uuid>" }` |
| PATCH | `/invoices/{invoice_id}/status` | Mark sent/paid/overdue | Body: `{ "status": "draft" \| "sent" \| "paid" \| "overdue" }` | Overdue can trigger org suspend |
| PATCH | `/invoices/{invoice_id}/payment` | Record payment | Body: `amount_paid_cents`, `credits_applied_cents` (optional, at least one) | `{ "invoice_id" }` |

`POST /organizations/{org_id}/invoices/generate` period behavior:

- Request only sends `billing_period_end`.
- Backend derives start as:
  1. latest existing `invoice.billing_period_end` for org, else
  2. active `subscription.billing_cycle_start`.
- Window is `[derived_start, billing_period_end)`.
- Request is idempotent for the same derived window.
- Overlapping windows are rejected with `400`.

### 4.5 Credits (prepaid wallet)

| Method | Path | Description | Body | Response |
|--------|------|-------------|------|----------|
| GET | `/organizations/{org_id}/credits` | Balance + recent ledger | — | `balance_cents`, `billing_mode`, `overdraft_limit_cents`, `recent_ledger` |
| POST | `/organizations/{org_id}/credits/grant` | Grant/top-up credits | `amount_cents` (required, >0), `type` (default `"grant"`), `reference_id` (optional) | `{ "organization_id", "amount_cents" }` |
| GET | `/organizations/{org_id}/credits/ledger` | Full ledger | Query: `offset`, `limit` | List of ledger entries |

### 4.6 Plans

| Method | Path | Description | Body | Response |
|--------|------|-------------|------|----------|
| GET | `/plans` | List all plans | — | List of `PlanResponse` |
| POST | `/plans` | Create plan | See below | `PlanResponse` |
| PATCH | `/plans/{plan_id}` | Update plan | Optional: `name`, `monthly_price`, `included_compute_units`, `overage_rate`, `currency` | `PlanResponse` |

**Create plan request body** — Both snake_case and camelCase are accepted; numbers may be sent as strings. Example:

```json
{
  "name": "Pro",
  "monthlyPrice": 2999,
  "includedComputeUnits": 10000,
  "overageRate": 5,
  "currency": "USD"
}
```

Or snake_case: `monthly_price`, `included_compute_units`, `overage_rate`. Optional: `currency` (default `"USD"`). Required: `name` (or `planName`), `monthly_price`/`monthlyPrice`, `included_compute_units`/`includedComputeUnits`, `overage_rate`/`overageRate`.

### 4.7 Actions (global quota action registry)

| Method | Path | Description | Query / Body | Response |
|--------|------|-------------|--------------|----------|
| GET | `/actions` | List actions | Query: `domain`, `is_active`, `search`, `offset`, `limit` | List of action rows |
| POST | `/actions` | Create action (+ initial price row) | `action_key`, `domain`, `unit_type`, optional `description`, optional `default_rate_cents_per_compute_unit` (default 1) | Created action |
| PATCH | `/actions/{action_key}` | Update action metadata or activation state | Optional: `domain`, `unit_type`, `description`, `is_active` | Updated action |
| DELETE | `/actions/{action_key}` | Hard-delete action | — | 204 (or 409 if referenced by existing records, e.g. invoice line items) |

Notes:

- `POST /actions` creates the `quota_actions` row and inserts an initial `quota_action_prices` row.
- If an action is already referenced (for example by `invoice_line_items`), delete returns **409 Conflict**.

### 4.8 Admin management

| Method | Path | Description | Body | Response |
|--------|------|-------------|------|----------|
| GET | `/admins` | List super admins | — | List of `member_id`, `email`, `display_name`, `created_at` |
| POST | `/admins` | Add super admin | `{ "email": "<member_email>" }` (member must exist) | `SuperAdminResponse` |
| DELETE | `/admins/{member_id}` | Remove super admin | — | 204 (cannot remove yourself) |

### 4.9 Audit log

| Method | Path | Description | Query | Response |
|--------|------|-------------|-------|----------|
| GET | `/audit-log` | List admin actions | `admin_member_id`, `action`, `target_type`, `offset`, `limit` | List of audit entries |

---

## 5. Frontend flow summary

1. **Firebase:** Sign in (e.g. email/password) → get Firebase ID token.
2. **Exchange:** `POST {BASE_URL}/auth/exchange` with `{ "id_token": "<firebase_id_token>" }` → get Control JWT (`access_token`).
3. **Admin check:** `GET {BASE_URL}/admin/v1/stats` with `Authorization: Bearer <control_jwt>`.  
   - **200** → user is platform admin; load admin UI and use the same JWT for all admin endpoints.  
   - **403** → not admin; show access denied or redirect.
4. **Admin UI:** Use the same Control JWT for all requests to `{BASE_URL}/admin/v1/*`.
5. **Token refresh:** When the Control JWT expires, get a new Firebase ID token (`user.getIdToken(true)`), then call `/auth/exchange` again.

---

## 6. CORS and base URL

- Ensure the Control Plane allows your frontend origin in CORS (e.g. `allow_origins` in the app).
- Set `BASE_URL` to the Control Plane API root (e.g. `https://api.example.com` or `http://127.0.0.1:8000` for local dev).

---

## 7. Scripts reference

- **Get Control JWT (CLI):** `./scripts/get_tokens.sh <EMAIL> <PASSWORD> [BASE_URL]` — Firebase sign-in + exchange; prints `access_token`.
- **Bootstrap first admin:** `python scripts/seed_platform_admin.py [EMAIL]` — run after the user has signed in at least once so the member exists.
- **Smoke test admin API:** `CONTROL_JWT='<token>' ./scripts/test_admin_endpoints.sh [BASE_URL]`.

See [06_reference.md](06_reference.md) for the full list of scripts.
