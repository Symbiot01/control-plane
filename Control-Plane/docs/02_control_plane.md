# Control plane

This document describes the **control plane** service: its purpose, tech stack, authentication, RBAC, quota and rate limiting, billing, and main API groups.

---

## 1. Purpose

The control plane is the central service for:

- **Authentication & identity** — Exchange Firebase ID tokens for short-lived Control JWTs; maintain `members` (Firebase UID, email, display name).
- **RBAC & organizations** — Tenants (`organizations`), membership and roles (`organization_members`: owner, admin, member, viewer), JWT-based org scoping.
- **Quota & rate limiting** — Global action registry (`quota_actions`), per-org per-action limits (day, month, lifetime), Redis counters and rate limiting.
- **Billing & credits** — Plans, subscriptions, usage recording (`usage_ledger`), per-action pricing, prepaid wallet and `credit_ledger`, idempotent quota check with `quota_check_requests`.
- **Internal quota check** — `POST /internal/v1/quota/check` for the product plane to allow/deny metered operations and record usage.

The admin module (`/admin/v1`) provides write APIs for plans, subscriptions, invoices, credits, and quota actions.

---

## 2. Tech stack

- **FastAPI** — HTTP API.
- **PostgreSQL** — Async (SQLAlchemy + asyncpg), source of truth for identity, orgs, quotas, billing.
- **Redis** — Quota counters (day/month), rate limiting, cached org metadata.
- **Firebase Admin** — Validate Firebase ID tokens.
- **JWT (RS256)** — Control JWTs issued by the control plane; JWKS at `GET /.well-known/jwks.json`.

---

## 3. Authentication

- **Firebase ID token** — Provided by the product plane (or a script) after the user signs in with Firebase.
- **Control JWT** — Issued by `POST /auth/exchange` when the Firebase token is valid. Contains the member identity (e.g. `sub` = member_id). Used for all user-scoped APIs (organizations, members, quotas, plans, billing).
- **JWKS** — `GET /.well-known/jwks.json` exposes public keys so other services can verify Control JWTs.
- **Internal API** — `POST /internal/v1/quota/check` is protected by `INTERNAL_API_KEY` (header), not by the Control JWT.

---

## 4. RBAC and organizations

- **Organizations** — Each tenant has `organizations` (name, slug, status, tier) and `organization_members` (member_id, role).
- **Roles** — owner, admin, member, viewer. Role checks are enforced by dependencies (e.g. `require_org_admin_for_path`) so that only allowed roles can call certain endpoints (e.g. PATCH quotas, invite members).
- **JWT org scoping** — The Control JWT does not list orgs; the app resolves membership from `organization_members`. Path parameters like `org_id` are validated against the member’s membership so a user can only access orgs they belong to.

---

## 5. Quota and rate limiting

- **Actions** — Global registry in `quota_actions` (e.g. `action_key`: `legal.case.analyze.v1`). See [05_actions_guide.md](05_actions_guide.md).
- **Limits** — `organization_quota_limits`: per org, per action, per period (day, month, lifetime, etc.). Live usage/holds live in PostgreSQL `quota_usage_buckets` (`used_units`, `reserved_units`). Redis is for org-status cache and API rate limiting only.
- **Rate limiting** — Per-org Redis-based rate limit (dependency `rate_limit_per_org`); returns 429 when exceeded.
- **Quota check** — The internal endpoint `POST /internal/v1/quota/check` evaluates org status, active subscription, limits, and (for prepay) wallet balance; on allow it increments PostgreSQL buckets and writes to `usage_ledger`. Postpay records `cost_cents=0`.

---

## 6. Billing (plans, subscriptions, credits, invoices)

- **Plans** — Catalog in `plans` (monthly_price, included_compute_units, overage_rate, currency). Read via `GET /plans`.
- **Subscriptions** — `organization_subscriptions` links an org to a plan with a billing window. An org must have an active subscription for the internal quota check to allow requests.
- **Usage** — Every allowed quota check (and successful commit) writes a row to `usage_ledger` (organization_id, action_id, units, compute_units, member_id, request_id, created_at).
- **Pricing** — `quota_action_prices`: per action, `rate_cents_per_compute_unit` and `effective_from`. Used to compute cost for prepay and for invoice line amounts.
- **Prepaid wallet** — Organizations have `prepaid_balance_cents`, `billing_mode` (postpay or prepay), and optional `overdraft_limit_cents`. `credit_ledger` records grants, top-ups, and consumption. For prepay, check/reserve debit or hold the wallet; `request_id` is required for idempotency.
- **Invoices** — Generated from `usage_ledger` over a billing period: `invoices` (total_compute_units, included_units, overage_units, amount_due, credits_applied_cents, amount_paid_cents, status) and `invoice_line_items` per action. Org members can read invoices via billing APIs; admins can generate and update them via the admin API.
- **Idempotency** — `quota_check_requests` is UNIQUE on `(organization_id, request_id)` with a request fingerprint. Exact retries return the stored decision; payload mismatch → **409**. Hold TTL + in-process reaper expire stale `held` rows.

---

## 7. Internal quota check

- **Endpoint** — `POST /internal/v1/quota/check` (also `reserve` / `commit` / `rollback`).
- **Auth** — `INTERNAL_API_KEY` in header.
- **Request body** — `organization_id`, `action_key`, `units` (default 1), optional `member_id`, **required** `request_id`, optional `compute_units` (defaults to units).
- **Behavior** — Validates org status, subscription, action; checks PostgreSQL bucket limits; for prepay, resolves rate and debits wallet. On allow: increments `used_units`, writes one `usage_ledger` row, status `committed`. Returns `allowed`, `status`, optional `reason`, `current_usage`, `limit`.

---

## 8. Main API groups

| Group | Prefix / path | Description |
|-------|----------------|-------------|
| Auth | `POST /auth/exchange`, `GET /.well-known/jwks.json` | Firebase → Control JWT; JWKS. |
| Organizations | `POST /organizations`, `GET /organizations/me`, `GET /organizations/{id}`, member management under `/organizations/{id}/members` | Create org, list my orgs, org detail, invite/update/remove members. |
| Members | `GET /members/me` | Current member profile and org roles. |
| Quotas | `GET /quotas/{org_id}`, `PATCH /quotas/{org_id}` | List/update org quota limits (admin/owner). |
| Plans | `GET /plans` | List plan catalog. |
| Billing | `GET /organizations/{org_id}/subscriptions/current`, `GET /organizations/{org_id}/invoices`, `GET /organizations/{org_id}/invoices/{id}` | Current subscription, list/detail invoices (read-only for org members). Note: invoice list returns **summary** (no `line_items`); invoice detail includes `line_items`. |
| Internal | `POST /internal/v1/quota/check|reserve|commit|rollback` | Quota metering (INTERNAL_API_KEY). |
| Admin | `GET|PATCH|... /admin/v1/*` | Orgs, subscriptions, invoices, credits, plans, actions, admins, audit, stats (platform admins only; see [04_admin.md](04_admin.md)). |

---

## 9. Data model (summary)

- **Identity & orgs** — `members`, `organizations`, `organization_members`.
- **Quota** — `quota_actions`, `organization_quota_limits`, `organization_usage_lifetime`.
- **Billing** — `usage_ledger`, `plans`, `organization_subscriptions`, `invoices`, `invoice_line_items`, `quota_action_prices`, `credit_ledger`, `quota_check_requests`.
- **Admin** — `platform_admins`, `platform_admin_audit_logs`.

Tables are created by `scripts/create_tables.sh`; see [06_reference.md](06_reference.md) for scripts and env vars.
