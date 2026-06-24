# HTTP API surface

All paths are **relative to the app root**. There is **no** `/api/v1` prefix; `/health` and `/.well-known/jwks.json` are at root.

| Auth | Notes |
|------|--------|
| **Public** | No JWT |
| **Member** | `Authorization: Bearer <Control JWT>` (`sub` = member id, `org_id` + `roles` when scoped to an org) |
| **Internal** | `X-Internal-Api-Key: <key>` or `Authorization: Bearer <same key>` (see `INTERNAL_API_KEY`) |
| **Admin** | Member JWT **and** user must be in `super_admins` |

Path parameters shown as `{name}`. Schemas live under `app/schemas/` and `app/modules/admin/schemas.py`; field lists below are summaries.

---

## App root

### `GET /health`

- **Input:** None.
- **Output:** JSON `{"status": "ok"}`.

### `GET /.well-known/jwks.json`

- **Input:** None.
- **Output:** JWKS document (JSON) for verifying Control JWTs (RS256).

---

## Auth

### `POST /auth/exchange`

Exchange a Firebase ID token for a Control JWT.

- **Input:** JSON body (`AuthExchangeRequest`): `id_token` (string, Firebase ID token).
- **Output:** JSON (`AuthExchangeResponse`): `access_token`, `token_type` (e.g. `Bearer`), `expires_in` (seconds).

---

## Members

### `GET /members/me`

- **Input:** `Authorization: Bearer` (Control JWT). Optional org rate limit applies when `org_id` is in the token.
- **Output:** JSON (`MemberProfile`): `id`, `email`, `display_name`, `is_active`, `created_at`, `organizations` (list of org fields + `role` per org).

---

## Organizations

JWT `org_id` must match path `org_id` where a membership dependency is used.

### `POST /organizations`

- **Input:** JSON (`OrganizationCreate`): `name`, optional `slug`.
- **Output:** JSON (`OrganizationResponse`): `id`, `name`, `slug`, `status`, `tier`, `created_at`, `updated_at`.

### `GET /organizations/me`

- **Input:** Bearer token.
- **Output:** JSON array of `OrganizationWithRole` (org fields + `role`).

### `GET /organizations/{org_id}`

- **Input:** Path `org_id`. Requires membership for that org.
- **Output:** JSON (`OrganizationResponse`).

### `POST /organizations/{org_id}/invite`

- **Input:** Path `org_id`. JSON (`InviteMemberRequest`): `email`, `role` (`owner` \| `admin` \| `member` \| `viewer`). Org admin/owner.
- **Output:** JSON `{"status": "invited", "email", "role"}`.

### `PATCH /organizations/{org_id}/member/{member_id}`

- **Input:** Path `org_id`, `member_id`. JSON (`UpdateMemberRoleRequest`): `role`. Org admin/owner.
- **Output:** JSON `{"status": "updated", "member_id", "role"}`.

### `DELETE /organizations/{org_id}/member/{member_id}`

- **Input:** Path `org_id`, `member_id`. Org admin/owner.
- **Output:** JSON `{"status": "removed", "member_id"}` (403 if last owner).

---

## Billing (member)

Prefix: `/organizations/{org_id}`.

### `GET /organizations/{org_id}/subscriptions/current`

- **Input:** Path `org_id` (must match JWT org). Member of org.
- **Output:** JSON (`SubscriptionResponse`) with nested `plan` (`PlanResponse`), or `null` if no active subscription.

### `GET /organizations/{org_id}/invoices`

- **Input:** Path `org_id`. Query: `status` (optional, invoice status), `limit` (default 50, max 100). Member of org.
- **Output:** JSON array of `InvoiceSummaryResponse` (period, totals, `amount_due`, `status`, etc.; no line items).

### `GET /organizations/{org_id}/invoices/{invoice_id}`

- **Input:** Path `org_id`, `invoice_id`. Member of org; invoice must belong to org.
- **Output:** JSON (`InvoiceResponse`): invoice fields plus `line_items` (`InvoiceLineItemResponse` list).

### `GET /organizations/{org_id}/usage/summary`

- **Input:** Path `org_id` (JWT org must match). Query: `from`, `to` (optional datetimes, half-open window `[from, to)` in UTC). If **both** omitted, defaults to **last 30 days** ending now. If only one is passed → 400.
- **Output:** JSON (`UsageSummaryResponse`): `organization_id`, `period_start`, `period_end`, `total_compute_units`, `total_units`, `by_action` (list of `action_id`, `action_key`, `units`, `compute_units` per action; includes rows with null `action_id` if present).

---

## Quotas

### `GET /quotas/{org_id}`

- **Input:** Path `org_id` (must match JWT org). **Org admin/owner** (not viewer-only).
- **Output:** JSON array (`QuotaLimitResponse`): per row `action_id`, `action_key`, `period`, `limit_value`, etc.

### `PATCH /quotas/{org_id}`

- **Input:** Path `org_id`. JSON (`QuotaLimitsUpdate`): `action_id`, `period` (must be a configured period, e.g. `per_day`, `per_month`, `lifetime`, …), `limit_value` ≥ 0. Org admin/owner.
- **Output:** JSON `{"status": "updated", "action_id", "period", "limit_value"}` (invalid period → 400).

---

## Plans (catalog)

### `GET /plans`

- **Input:** Bearer token.
- **Output:** JSON array (`PlanResponse`): `id`, `name`, `monthly_price`, `included_compute_units`, `overage_rate`, `currency`, `created_at`.

---

## Internal (product plane)

### `POST /internal/v1/quota/check`

Pre-request quota / credits check; records usage on **allow**.

- **Input:** Header internal API key (see top). JSON (`QuotaCheckRequest`): `organization_id`, `action_key`, `units` (≥ 1, default 1), optional `member_id`, `request_id`, `compute_units` (defaults to `units` if omitted).
- **Output:** JSON (`QuotaCheckResponse`): `allowed`, optional `reason`, optional `current_usage` / `limit` when denied for quota limits.

---

## Admin (`/admin/v1`)

All routes: **super admin** + Bearer JWT. Bodies use schemas from `app/modules/admin/schemas.py` unless noted.

### Stats

#### `GET /admin/v1/stats`

- **Input:** None.
- **Output:** JSON (`AdminStatsResponse`): counts (`total_orgs`, `active_orgs`, `suspended_orgs`, `archived_orgs`, `active_subscriptions`, `draft_invoices`, `overdue_invoices`, `total_members`).

### Organizations

#### `GET /admin/v1/organizations`

- **Input:** Query: `status`, `search`, `offset`, `limit` (default 50, max 200).
- **Output:** JSON array (`AdminOrgResponse`): org fields plus `prepaid_balance_cents`, `billing_mode`, `overdraft_limit_cents`, `members_count`.

#### `GET /admin/v1/organizations/{org_id}`

- **Input:** Path `org_id`.
- **Output:** JSON (`AdminOrgResponse`). 404 if missing.

#### `GET /admin/v1/organizations/{org_id}/usage/summary`

- **Input:** Path `org_id`. Query: `from`, `to` (optional; same rules as member `usage/summary`). Org must exist → 404 otherwise.
- **Output:** JSON (`UsageSummaryResponse`), same shape as `GET /organizations/{org_id}/usage/summary`.

#### `PATCH /admin/v1/organizations/{org_id}`

- **Input:** JSON (`AdminOrgUpdate`): optional `status`, `tier`, `billing_mode`, `overdraft_limit_cents`.
- **Output:** JSON (`AdminOrgResponse`).

#### `PATCH /admin/v1/organizations/{org_id}/suspend` | `.../activate`

- **Input:** Path `org_id` only (no body).
- **Output:** JSON (`AdminOrgResponse`) with updated `status`.

#### `GET /admin/v1/organizations/{org_id}/members`

- **Input:** Path `org_id`.
- **Output:** JSON array of objects: `member_id`, `email`, `display_name`, `role`.

### Subscriptions (admin)

#### `GET /admin/v1/organizations/{org_id}/subscriptions`

- **Input:** Path `org_id`.
- **Output:** JSON array (`SubscriptionResponse` with `plan`).

#### `GET /admin/v1/organizations/{org_id}/subscriptions/current`

- **Input:** Path `org_id`.
- **Output:** `SubscriptionResponse` or `null`.

#### `POST /admin/v1/organizations/{org_id}/subscriptions`

- **Input:** JSON (`SubscriptionCreate`): `plan_id`, `billing_cycle_start`, `billing_cycle_end`.
- **Output:** JSON (`SubscriptionResponse`). 400 on business rule errors.

#### `PATCH /admin/v1/subscriptions/{sub_id}/status`

- **Input:** JSON (`SubscriptionStatusUpdate`): `status`.
- **Output:** JSON (`SubscriptionResponse`) or 404.

#### `POST /admin/v1/subscriptions/{sub_id}/change-plan`

- **Input:** JSON (`SubscriptionChangePlanRequest`): `new_plan_id`, `new_billing_cycle_start`, `new_billing_cycle_end`.
- **Output:** JSON (`SubscriptionResponse`).

### Invoices (admin)

#### `GET /admin/v1/organizations/{org_id}/invoices`

- **Input:** Path `org_id`. Query: optional `status`.
- **Output:** JSON array (`AdminInvoiceResponse` with line items and payment fields).

#### `GET /admin/v1/invoices/{invoice_id}`

- **Input:** Path `invoice_id`.
- **Output:** JSON (`AdminInvoiceResponse`). 404 if missing.

#### `POST /admin/v1/organizations/{org_id}/invoices/generate`

- **Input:** JSON (`InvoiceGenerateRequest`): `billing_period_end` (period start is derived server-side).
- **Output:** JSON `{"invoice_id": <UUID>}`. 400 if generation fails (e.g. no subscription).

#### `PATCH /admin/v1/invoices/{invoice_id}/status`

- **Input:** JSON (`InvoiceStatusUpdate`): `status`. Overdue may suspend org.
- **Output:** JSON `{"invoice_id", "status"}`.

#### `PATCH /admin/v1/invoices/{invoice_id}/payment`

- **Input:** JSON (`InvoicePaymentUpdate`): at least one of `amount_paid_cents`, `credits_applied_cents`.
- **Output:** JSON `{"invoice_id"}`.

### Credits (admin)

#### `GET /admin/v1/organizations/{org_id}/credits`

- **Input:** Path `org_id`.
- **Output:** JSON (`CreditBalanceResponse`): `balance_cents`, `billing_mode`, `overdraft_limit_cents`, `recent_ledger` (short list of `CreditLedgerEntry`).

#### `POST /admin/v1/organizations/{org_id}/credits/grant`

- **Input:** JSON (`CreditGrantRequest`): `amount_cents` (must be > 0), optional `type`, `reference_id`.
- **Output:** JSON `{"organization_id", "amount_cents"}`.

#### `GET /admin/v1/organizations/{org_id}/credits/ledger`

- **Input:** Query: `offset`, `limit` (max 200).
- **Output:** JSON array (`CreditLedgerEntry`).

### Plans (admin)

#### `GET /admin/v1/plans`

- **Input:** None.
- **Output:** JSON array (`PlanResponse`).

#### `POST /admin/v1/plans`

- **Input:** JSON (`PlanCreate`): supports aliases `planName`, `monthlyPrice`, `includedComputeUnits`, `overageRate` as well as snake_case fields (see schema).
- **Output:** JSON (`PlanResponse`).

#### `PATCH /admin/v1/plans/{plan_id}`

- **Input:** JSON (`PlanUpdate`): any of `name`, `monthly_price`, `included_compute_units`, `overage_rate`, `currency`.
- **Output:** JSON (`PlanResponse`).

### Quota actions (admin registry)

#### `GET /admin/v1/actions`

- **Input:** Query: `domain`, `is_active`, `search`, `offset`, `limit` (max 500).
- **Output:** JSON array (`AdminActionResponse`).

#### `POST /admin/v1/actions`

- **Input:** JSON (`AdminActionCreate`): `action_key`, `domain`, `unit_type`, optional `description`, `default_rate_cents_per_compute_unit`.
- **Output:** JSON (`AdminActionResponse`). 201. 400 if `action_key` exists.

#### `PATCH /admin/v1/actions/{action_key}`

- **Input:** JSON (`AdminActionUpdate`): optional `domain`, `unit_type`, `description`, `is_active`.
- **Output:** JSON (`AdminActionResponse`).

#### `DELETE /admin/v1/actions/{action_key}`

- **Input:** Path `action_key`.
- **Output:** 204 empty body, or 404 / 409 if referenced.

### Super admins

#### `GET /admin/v1/admins`

- **Input:** None.
- **Output:** JSON array (`PlatformAdminResponse`).

#### `POST /admin/v1/admins`

- **Input:** JSON (`PlatformAdminCreate`): `email` (existing member).
- **Output:** JSON (`PlatformAdminResponse`).

#### `DELETE /admin/v1/admins/{member_id}`

- **Input:** Path `member_id` (cannot delete self).
- **Output:** 204.

### Audit log

#### `GET /admin/v1/audit-log`

- **Input:** Query: `admin_member_id`, `action`, `target_type`, `offset`, `limit`.
- **Output:** JSON array (`AdminAuditLogResponse`).

---

## Router registration order

`app/api/router.py`: **auth → members → organizations → billing → quotas → plans → internal**.

---

## Related docs

- [02_control_plane.md](02_control_plane.md) — product behavior
- [04_admin.md](04_admin.md) — admin auth and UI notes
