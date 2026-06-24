## Control Plane

The Control Plane is the system that decides whether product requests are allowed, tracks usage, and turns usage into billing data.

Think of it as the policy and accounting layer behind your product APIs:

- Users authenticate and become members of organizations.
- Organizations get limits and pricing per action.
- Product requests call an internal quota endpoint before executing expensive work.
- Allowed requests are recorded for usage and invoicing.
- Optional prepaid credits can be consumed in real time.

### Core terms (plain language)

- **Action**: a metered capability in your product, identified by an `action_key` (example: `legal.case.analyze.v1`).
- **Units**: business-facing quantity for an action (for example "requests" or "tokens").
- **Compute units**: normalized billing quantity used for pricing and overage math.
- **Quota**: how much of an action an organization can use per day, month, or lifetime.
- **Rate limiting**: short-window throttling to protect the system from bursts.
- **Credits**: prepaid balance (in cents) for prepay organizations; consumed during quota check.
- **Postpay**: usage is recorded now and invoiced later.
- **Prepay**: request is allowed only if credits/overdraft can cover cost.
- **Idempotency (`request_id`)**: prevents double charging or double usage recording on retries.

### How the product is used in the current version

1. Product authenticates users with Firebase and exchanges Firebase ID token for a Control JWT (`POST /auth/exchange`).
2. Product creates or selects an organization and sets quotas/plans (admin or scripts during setup).
3. Before handling a metered product request, product calls `POST /internal/v1/quota/check` with:
   - `organization_id`, `action_key`, `units`, `compute_units`
   - optional `member_id`
   - `request_id` (strongly recommended; required for safe prepaid flows)
4. Control Plane returns allow/deny with reason and usage/limit context.
5. If allowed, product performs the action; Control Plane records usage and (for prepay) debits credits.
6. Billing data (subscriptions, invoices, ledger) is available through billing/admin APIs.

### High-level capabilities

- **Authentication & Identity**
  - Firebase ID token -> Control JWT exchange (`/auth/exchange`) using RS256 keys.
  - `members` table for Firebase UID, email, display name, active flag.
- **RBAC & Organizations**
  - `organizations`, `organization_members` with roles: owner, admin, member, viewer.
  - JWT-based org scoping and role checks via dependencies in `app/core/dependencies.py`.
- **Quota & Rate Limiting**
  - Global action registry (`quota_actions`) with `action_key`, domain, unit type.
  - Per-org, per-action limits (`organization_quota_limits`) with periods (day, month, lifetime).
  - Redis-based per-org rate limiting and per-period counters; PostgreSQL-backed lifetime usage (`organization_usage_lifetime`).
  - Internal quota check endpoint: `POST /internal/v1/quota/check` for the product plane.
- **Billing & Credits (Core, no Stripe yet)**
  - Usage recording in `usage_ledger` for every allowed internal quota check.
  - Plan catalog (`plans`) and subscriptions (`organization_subscriptions`).
  - Invoice generation from usage (`invoices`, `invoice_line_items`).
  - Per-action pricing via `quota_action_prices` (cents per compute unit).
  - Prepaid wallet on organizations: `prepaid_balance_cents`, `billing_mode` (`postpay` or `prepay`), `overdraft_limit_cents`.
  - Wallet ledger: `credit_ledger` with grants, top-ups, and consumption.
  - Idempotent, credit-aware quota check via `quota_check_requests` and `request_id`.
- **Admin / Ops overlay**
  - `app/modules/admin/` for platform-admin operations at `/admin/v1`.

For documentation, see **[docs/README.md](docs/README.md)** or start with [docs/01_system_overview.md](docs/01_system_overview.md).

---

## Project status

- **Done – Phase 1 (Bootstrap & Schema)**:
  - Config, DB session, Redis lifespan, FastAPI app, health endpoint.
  - PostgreSQL schema deployed via `scripts/create_tables.sh` (core + billing tables).
- **Done – Phase 2 (Core Control Plane)**:
  - SQLAlchemy models for all core tables.
  - Auth (Firebase → Control JWT), RBAC, org & member APIs.
  - Quota actions & limits, Redis cache, internal quota check, rate limiting, audit logging.
  - Router wiring and a `scripts/test_endpoints.sh` smoke script.
- **Done – Phase 3 (Billing foundations + credits)**:
  - Usage recording in `usage_ledger`.
  - Subscription lifecycle service and read-only billing APIs (`GET /plans`, current subscription, invoices list/detail).
  - Per-action pricing via `quota_action_prices` and `pricing_service`.
  - Prepaid wallet (`prepaid_balance_cents`, `billing_mode`, `overdraft_limit_cents`) with `credit_ledger` and `credit_service`.
  - Idempotent internal `quota_check` that:
    - Enforces org status and quotas.
    - Optionally enforces prepaid credits for `billing_mode='prepay'` using `request_id`.
    - Records decisions in `quota_check_requests`.
  - Invoice generation that aggregates usage and fills `credits_applied_cents` / `amount_paid_cents` (currently both `0` by default, ready for later payment integration).
- **Next – Admin/Ops overlay & payments**:
  - `app/modules/admin/` with super admin auth and write APIs:
    - Create/update plans and subscriptions.
    - Trigger invoice generation and mark invoices paid/overdue.
  - Stripe or other PSP integration for collecting payments and reconciling invoices.

---

## Architecture overview

### Tech stack

- **FastAPI** for the HTTP API.
- **PostgreSQL** (async via SQLAlchemy + asyncpg) as the source of truth.
- **Redis** for quotas, rate limiting, and cached org metadata.
- **Firebase Admin** to validate Firebase ID tokens.
- **JWT (RS256)** for Control JWTs issued by the control plane.

### Major components

- `app/core/*`
  - `config.py`: environment & settings (via pydantic-settings).
  - `firebase.py`: Firebase Admin initialization.
  - `jwt.py`: Control JWT issue/verify + JWKS endpoint.
  - `dependencies.py`: auth, org membership, RBAC, rate limiting, internal API key.
- `app/db/*`
  - `session.py`: async PostgreSQL engine + `get_db` dependency.
  - `base.py`: SQLAlchemy `Base`.
- `app/models/*`
  - Core: `Member`, `Organization`, `OrganizationMember`, `QuotaAction`,
    `OrganizationQuotaLimit`, `OrganizationUsageLifetime`, `AuditLog`.
  - Billing: `UsageLedger`, `Plan`, `OrganizationSubscription`, `Invoice`,
    `InvoiceLineItem`, `QuotaActionPrice`, `QuotaCheckRequest`, `CreditLedger`.
- `app/services/*`
  - `org_service`, `subscription_service`, `invoice_service`.
  - `quota_check_service` (central allow/deny + usage recording + credits).
  - `pricing_service` (per-action rates), `credit_service` (wallet operations).
  - `quota_cache_service` (org limits/status in Redis), `usage_ledger_service`, `audit_service`.
- `app/modules/*`
  - `auth`: Firebase → Control JWT exchange and auth endpoints.
  - `organizations`: org and membership APIs.
  - `members`: member profile.
  - `quotas`: org quota limits CRUD.
  - `plans`: plan catalog read APIs.
  - `billing`: org-scoped subscription & invoice **read** APIs.
  - `internal`: internal-only `POST /internal/v1/quota/check`.
- `app/api/router.py`
  - Aggregates all routers under a single API router, mounted by `app/main.py`.

---

## Data model (short version)

- **Members & Orgs**
  - `members`: Firebase users with email + display_name.
  - `organizations`: tenants with `status` (active/suspended/archived) and `tier`.
  - `organization_members`: roles per org.
- **Quota**
  - `quota_actions`: registry of measurable actions (e.g. `legal.case.analyze.v1`).
  - `organization_quota_limits`: per-org, per-action, per-period limits.
  - `organization_usage_lifetime`: durable lifetime counters.
- **Billing**
  - `usage_ledger`: one row per allowed internal quota check (org, action, units, compute_units, member, request_id, created_at).
  - `plans`: plans with `monthly_price`, `included_compute_units`, `overage_rate`, `currency`.
  - `organization_subscriptions`: which plan an org is on, with billing window.
  - `invoices`: per-org per-period invoices, including:
    - `total_compute_units`, `included_units`, `overage_units`, `amount_due`.
    - `credits_applied_cents`, `amount_paid_cents`.
  - `invoice_line_items`: per-action amounts per invoice.
  - `quota_action_prices`: `rate_cents_per_compute_unit` per action, with `effective_from`.
  - `credit_ledger`: wallet transactions in cents (positive = grant/top-up, negative = consume).
  - `quota_check_requests`: idempotent decision log keyed by `(organization_id, request_id)`.

---

## How billing & credits behave

- **Postpay mode (`billing_mode='postpay'`)**
  - Internal quota checks enforce quotas and record usage to `usage_ledger`.
  - No real-time credits check; invoices are generated from usage + plan terms:
    - `amount_due = plan.monthly_price + overage_units * plan.overage_rate`.
  - `credits_applied_cents` and `amount_paid_cents` are currently `0` by default; future payment flows will update them.

- **Prepay mode (`billing_mode='prepay'`)**
  - Before recording usage, `quota_check`:
    - Resolves the current subscription/plan and verifies org is subscribed.
    - Resolves per-action rate from `quota_action_prices`.
    - Computes `cost_cents = rate_cents_per_compute_unit * compute_units`.
    - Attempts an atomic wallet debit via `credit_service.consume_credits`.
  - If debit fails (no balance + overdraft limit), the request is denied with `reason='insufficient_credits'` and no usage is recorded.
  - Every call with a `request_id` is idempotent:
    - First decision is stored in `quota_check_requests`.
    - Later retries with the same `(org_id, request_id)` return the same decision and do not re-debit or re-record usage.

- **Idempotency**
  - Required for safe money/credits:
    - Request body for `/internal/v1/quota/check` includes `request_id`.
    - `quota_check_requests` enforces uniqueness and re-use of decisions.
    - `usage_ledger` has a partial unique index on `(organization_id, request_id)` where `request_id IS NOT NULL`.

---

## Running the project locally

### 1. Environment

1. Copy the example env file and fill values:

   ```bash
   cp .env.example .env
   ```

2. Create a virtualenv and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

3. Start PostgreSQL and Redis (for example via Docker):

   ```bash
   docker compose up -d
   ```

4. Create (or recreate) tables:

   ```bash
   ./scripts/create_tables.sh           # create tables
   # or, to drop everything and recreate:
   ./scripts/reset_tables.sh
   ```

5. Seed base data:

   ```bash
   python scripts/seed_quota_actions.py   # quota_actions + default prices
   python scripts/seed_plans.py           # basic plan(s)
   # After you create an organization, you can optionally seed credits:
   # python scripts/seed_credits_example.py <org_id> <amount_cents>
   ```

6. Run the app:

   ```bash
   uvicorn app.main:app --reload
   ```

7. Check:
   - Health: `http://127.0.0.1:8000/health`
   - Docs: `http://127.0.0.1:8000/docs`

### 2. Required env vars

See `.env.example` for the full list. Key variables:

- **Database & Redis**
  - `DATABASE_URL`
  - `REDIS_URL`
  - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`, `POSTGRES_HOST` (for `create_tables.sh`).
- **Firebase & JWT**
  - `GCP_SERVICE_ACCOUNT_JSON` (service account JSON string).
  - `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY` (PEM).
  - `JWT_ISSUER`, `JWT_EXPIRATION_MINUTES`.
- **Internal**
  - `INTERNAL_API_KEY` for `/internal/v1/*`.
  - `ENVIRONMENT` (e.g. `local`, `staging`, `prod`).

### 3. Troubleshooting: "password authentication failed" for postgres

The official Postgres Docker image sets the database user password **only when the data volume is first created**. If you later change `POSTGRES_PASSWORD` in `.env`, the running container still has the **old** password in the database; your app and scripts use the **new** value from `.env`, so they no longer match.

- **Fix (resets all DB data):** Recreate the volume so Postgres re-initializes with your current `.env`:
  ```bash
  docker compose down -v
  docker compose up -d
  # Wait for postgres to be healthy, then:
  ./scripts/create_tables.sh
  ```
- **Alternative:** If you know the password the volume was originally created with, set that in `.env` as `POSTGRES_PASSWORD` (and do not set `DATABASE_URL` so the app keeps using the POSTGRES_* vars).

---

## Key endpoints (external and internal)

- **Auth**
  - `POST /auth/exchange` – Firebase ID token → Control JWT.
  - `GET /.well-known/jwks.json` – JWKS for Control JWT verification.
- **Organizations & Members**
  - `POST /organizations` – create org.
  - `GET /organizations/me` – list orgs current member belongs to.
  - `GET /organizations/{org_id}` – org details.
  - Member management via `POST/PATCH/DELETE` under `/organizations/{org_id}/members`.
  - `GET /members/me` – current member profile and org roles.
- **Quotas**
  - `GET /organizations/{org_id}/quotas` – list org quota limits.
  - `PATCH /organizations/{org_id}/quotas` – update org quota limits (admin/owner).
- **Plans & Billing (read-only for org members)**
  - `GET /plans` – list available plans.
  - `GET /organizations/{org_id}/subscriptions/current` – current subscription for org.
  - `GET /organizations/{org_id}/invoices` – list invoices for org.
  - `GET /organizations/{org_id}/invoices/{invoice_id}` – invoice details.
- **Internal (product plane)**
  - `POST /internal/v1/quota/check` – internal quota + billing decision.
    - Auth: `INTERNAL_API_KEY` header.
    - Body: `organization_id`, `action_key`, `units`, optional `member_id`, `request_id`, `compute_units`.
    - Response: `allowed`, optional `reason`, `current_usage`, `limit`.

---

## Admin / ops overlay

- **Admin module**: `app/modules/admin/` – always mounted at `/admin/v1`.
- Super admins (see `super_admins` table) can manage orgs, plans, subscriptions, invoices, credits, and other admins via the admin API.
- **Admin docs**: See **[docs/04_admin.md](docs/04_admin.md)** for Firebase login, auth exchange, and full admin endpoint reference.

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/01_system_overview.md](docs/01_system_overview.md) | Actors, flows, auth, and how everything fits together. |
| [docs/02_control_plane.md](docs/02_control_plane.md) | Control plane capabilities, tech stack, and APIs. |
| [docs/03_product_plane_integration.md](docs/03_product_plane_integration.md) | How the product plane integrates (auth, quota check, scripts). |
| [docs/04_admin.md](docs/04_admin.md) | Admin API and building the admin UI. |
| [docs/05_actions_guide.md](docs/05_actions_guide.md) | Quota actions: add, disable, and use. |
| [docs/06_reference.md](docs/06_reference.md) | Scripts, env vars, troubleshooting. |

Full index: **[docs/README.md](docs/README.md)**.

