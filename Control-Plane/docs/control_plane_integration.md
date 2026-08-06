# Control Plane integration contract (MedRecs)

This is the **shared contract** between MedRecs (product plane) and Kwikee
Control Plane (policy, identity, metering, billing). JWT, quota, and invite
behavior below is from the **Control Plane repo**, not from older MedRecs
assumptions.

Control Plane is a **mandatory MedRecs-backend sidecar**, not a third SPA
origin. It does not run OCR, opinions, chat, or reports. It issues identity,
then **meters and bills**. MedRecs must not duplicate a wallet or usage
ledger as source of truth.

**Highest-risk gap today:** a valid Control JWT still lets a **suspended or
de-entitled** tenant **read PHI** (`GET /cases`, files, GCS signed URLs).
Quota only runs on OCR/pipeline/chat. Quota is metering; it is **not** the
PHI lock. See [Gate reads, not only models](#2-jwt-is-identity-not-authorization-for-phi).

**Status of this document:** Required MedRecs architecture is **agreed**:
sidecar, PHI lock on reads, delete `X-Org-Id`, per-run analyze, chat-only
reserve, no `super_admin` → owner, `quota_gate.allow`. Control Plane
HTTP/JWT answers are frozen for this build.

**Written contract: green to ship against.** That is **not** a green light
on running systems: MedRecs has not implemented it; CP still has postpay
NameError, commit counters, unique `request_id`, and **3b**. Do not start
PRs that guess the [open MedRecs answers](#7-questions-cp-still-wants-medrecs-to-answer).
Slices 1–2 (JWT verifier + PHI lock) may start once those answers are
written here — without waiting on JWT `org_status` or cookies.

Do **not** treat `org_status` on the JWT, per-product internal keys, or
impersonation as how MedRecs solves PHI or confused deputy. Ship the
projection + JWT tenant + private `/internal/v1` without waiting on those
specs.

Last updated from Control Plane code plus agreed MedRecs contract edits.

---

## Roles of the two planes

| Plane | Owns | Does not own |
|---|---|---|
| **Control Plane** | Firebase → Control JWT, tenants, invites, products, entitlements, quotas, subscriptions, credits, invoices | Medical records, cases, files, pipeline, chat |
| **MedRecs** | Cases, files, GCS, OCR, agentic/legacy pipeline, chat, reports, chronology | Wallet, invoices, org creation, plan changes |

Product APIs do the work. The **browser talks only to MedRecs** (plus Firebase
Auth). MedRecs talks to CP for exchange, profile, products, and quota.
Invite GET/accept is **org-console** unless MedRecs hosts an invite page
(then it may proxy those two calls). The SPA must not know CP URLs except
an org-console **link** for billing and, by default, invites.

```text
Browser
  Firebase sign-in
  POST {MEDRECS}/api/auth/exchange  { id_token }
  MedRecs upserts users.control_member_id; session cookie preferred later
    (not a gate — Bearer JWT is fine until editor origin is decided)
  GET {MEDRECS}/api/auth/session   (projection: member_id, org_id, role, products, exp)
    organization == null           → invite UX, no case work
    level_of_access == super_admin → 403 on cases; send to CP admin console
    org status != active           → 403 on all org-scoped routes (reads too)
    no product_key medical         → "not provisioned"
  all MedRecs / editor / OCR API calls: cookie or Bearer Control JWT
  no X-Org-Id header, no organization_id in JSON

MedRecs API (every org-scoped route, including GET)
  verify JWT via {CP}/.well-known/jwks.json
  require iss, exp, sub, org_id, level_of_access in {owner, member}
  bind local user by JWT sub (control_member_id); org_id from token only
  short-TTL projection from GET /organizations/{id} (Postgres): status == active
    (PHI lock — not quota Redis, not a JWT org_status claim)
  on CP outage: if projection TTL elapsed → 403/503 on GET too (not fail-open)
  writes / processing: entitlement medical present and not expired
  before expensive work:
    request_id = server-issued UUID, persist on the job row at enqueue
    POST {CP}/internal/v1/quota/check|reserve
      X-Internal-Api-Key: <backend secret only>
      organization_id = JWT org_id     // never from client
      member_id = JWT sub
    allowed == false → 402/403/429 from reason; do not enqueue
    401 / 5xx / timeout → 503 fail-closed
  worker: load org/member/request_id from the job row, not task kwargs
  MedRecs 401 → frontend getIdToken(true) → POST /api/auth/exchange again
```

Quota calls are **never** from the browser. The client must not name the
tenant or the bill.

---

## Current MedRecs vs this contract

These are the mismatches that will break against the new CP.

| MedRecs today | Required |
|---|---|
| Most product routes verify a **Firebase ID token** (`get_tenant_context` → `require_authenticated_user`) | Product APIs verify **Control JWT** via JWKS (one verifier shared with editor + OCR) |
| Tenant from **`X-Org-Id` + local membership** | **Delete `X-Org-Id`.** Tenant = JWT `org_id` only. Do not accept `organization_id` in JSON |
| JWT decoder reads `roles[]` | Read `level_of_access`. `roles` is always absent → `[]` |
| Local roles `owner/admin/member/viewer` | CP roles: `owner` and `member` only. Do not mint admin/viewer that look like CP roles |
| `GET /api/me/organizations` syncs multi-org from `GET /organizations/me` | One org. Session projection from MedRecs exchange. No org picker |
| Quota client exists; **use cases never call it**; GET cases ungated | **PHI lock on every org-scoped route** (status==active). Quota before models. Use cases call `quota_gate.allow(...)` — zero `action_key` strings in domain |
| `QuotaDenied` always HTTP **403** | Map exact `reason` strings (402 / 403 / 429 / 400) |
| Frontend talks to CP and MedRecs; JWT in `sessionStorage`; hardcoded org UUID | Browser → MedRecs only. Cookie preferred later (not a gate). No CP URLs in the SPA except org-console link |
| `getSession()` uses `useControlPlane: true` against `/api/auth/session` | Keep `/api/auth/session` as a **MedRecs** projection (MedRecs called CP). Never send the SPA to CP for session |
| Editor middleware falls back to `X-Org-Id` if JWT has no `org_id` | Same verifier as MedRecs. No header fallback. 403 guest/super_admin |
| `CONTROL_PLANE_ENABLED` defaults **false** | **true** in staging and prod. Flag is local laptop only |
| Celery can take org ids in task kwargs | Worker loads org/member/`request_id` from the **job row created at enqueue** |

`GET /organizations/me` **does exist** on CP (it will not 404). Prefer
`GET /members/me` as the “who am I + my one org” call.

CP **does** verify `iss` on its own tokens. MedRecs must do the same:
`CONTROL_PLANE_JWT_ISSUER` is optional in code today and must be **required**.

---

## Identity and JWT

### Exchange

`POST /auth/exchange`

Body: `{ "id_token": "<Firebase ID token>", "display_name": optional }`

Response:

```json
{
  "access_token": "<RS256 JWT>",
  "token_type": "Bearer",
  "expires_in": 1800,
  "has_pending_invites": false
}
```

`expires_in` is `JWT_EXPIRATION_MINUTES * 60`. `.env.example` is **30 minutes**
(1800s). Docs that say 5400 assume a 90-minute setting. MedRecs should persist
`expires_in` and refresh **before** expiry (see
[Token refresh](#token-refresh-and-long-lived-requests)).

`has_pending_invites` is a first-class UX signal for guests. Use it; do not
only discover invites after a 403 on cases.

On first exchange, pending invites are frozen to year 2099 so they stop
expiring. That is a CP behavior MedRecs should know about (invites do not
time out after first login).

### Claims (`app/core/jwt.py` on CP)

`sub` is UUID `member_id` as a string. **Firebase UID is not in the JWT.**
After product APIs stop verifying Firebase, look up the local `users` row by
`control_member_id = sub`, not by `firebase_uid`. Upsert email/display name
from `GET /members/me` when needed.

| User | Claims |
|---|---|
| **Guest** (Firebase user, no membership) | `sub`, `iss`, `iat`, `exp`, `level_of_access: "guest"`. **No `org_id` key. No `roles`.** |
| **Member / owner** | same + `org_id` + `level_of_access: "member"` or `"owner"` |
| **Super admin** | `sub`, `iss`, `iat`, `exp`, `level_of_access: "super_admin"`. **No `org_id`**, even if they also have a membership |

Audience is **not** checked. Product must still require:

- algorithm `RS256`
- `iss` == env `CONTROL_PLANE_JWT_ISSUER` for that environment (example:
  `control-plane`; staging vs prod can differ)
- `sub`, `iat`, `exp`
- `kid: "control-plane-1"` (hardcoded in CP)

JWKS: `GET /.well-known/jwks.json` — `kty: RSA`, `use: sig`, `alg: RS256`,
`kid: "control-plane-1"`. Keys are env PEMs, **not rotated via a new kid**.
If CP rotates the PEM and keeps the same kid, **short JWKS cache TTL** is
required (minutes, not hours). PyJWKClient default lifespan in MedRecs is
600s; do not raise it.

Clock skew: allow a small leeway (30–60s) on `exp`/`iat` so browser and API
clocks do not flap 401s.

### Who may hit MedRecs case APIs

| `level_of_access` | MedRecs cases / files / processing / chat / reports |
|---|---|
| `owner` | allow **only if** short-TTL projection says `status == active` |
| `member` | same |
| `guest` | **403**. Invite + re-exchange only |
| `super_admin` | **403**. They belong on CP `/admin/v1`. Do **not** map to owner |
| any role, org suspended/archived | **403 on GET and writes** (PHI lock). JWT may still be valid |

Accepting an invite does **not** issue a new JWT. After
`POST /invites/{id}/accept`, the client **must exchange again** so `org_id`
appears.

Invite GET/accept live on CP for the **org console**
(`{ORG_CONSOLE_URL}/invite?token=`). The MedRecs SPA does not call CP.
MedRecs **must** proxy `POST /auth/exchange` and session. It proxies invite
GET/accept **only if** product hosts a MedRecs invite page (still an open
UX choice). Guest session is only for invite-accept + re-exchange. Guests
**must not** create cases or start jobs.

---

## Tenancy (one org is final)

- A member belongs to **at most one org** (`organization_members.member_id`
  UNIQUE). Second invite accept → **400** `"User is already a member of an organization"`.
- No org-switch endpoint. Exchange stamps the only membership.
- Org-scoped CP APIs require JWT `org_id` to **match the path**.
- **Delete `X-Org-Id`.** Do not keep it as a hint, and do not “ignore if it
  disagrees.” If the header is sent, **400**. Do not accept `organization_id`
  in product JSON bodies. Derive tenant from the JWT only.
- Delete the org picker. Polling `GET /organizations/me` as a fake switcher
  is forbidden.
- If a client sends a different org than the JWT, that is an attack.

Local projection MedRecs **may** keep:

- `users` row keyed by Firebase UID **and** `control_member_id` (still need
  local `users.id` for cases)
- copy of `org_id`, name, slug, role — **refresh from JWT / `GET /members/me`**

Local projection must **not**:

- let the client pick another org
- treat stale local membership as authorization when JWT `org_id` differs
- mint `admin` / `viewer` from CP. A local “viewer” who is a CP `member`
  can still mutate. Collapse to owner/member, or a **stricter** MedRecs ACL
  that never loosens CP.

### User-facing CP reads (MedRecs proxies these)

The SPA does **not** call these. MedRecs calls them with the Control JWT
(or after exchange) and returns a session / settings projection.

| CP endpoint | Shape | MedRecs use |
|---|---|---|
| `GET /organizations/me` | **Array**. 0–1 orgs + `role` | Do not expose as a multi-org picker |
| `GET /members/me` | `{ id, email, display_name, is_active, created_at, organization: { ...org, role } \| null }` | Preferred “who am I + my one org” for `/api/auth/session` |
| `GET /organizations/{org_id}` | org including `entitlements`; JWT `org_id` must match | Status + entitlements for the PHI lock projection |
| `GET /organizations/{org_id}/products` | entitled products | “not provisioned” UX |

Org objects include: `id`, `name`, `slug`, `status`, `tier`,
`prepaid_balance_cents`, `entitlements[]`, timestamps, plus `role`.

Usage/billing reads (member of that org):

- `GET /organizations/{org_id}/subscriptions/current`
- `GET /organizations/{org_id}/invoices` and `.../invoices/{id}`
- `GET /organizations/{org_id}/usage/summary?from=&to=`

Writes (pay, grant credits, generate invoice, change plan, suspend) are
**admin only**. Billing UI is an **org-console link**, not a MedRecs ledger.
Optionally proxy usage summary into settings. Do not rebuild invoices.

---

## Onboarding (how an org appears)

There is **no public `POST /organizations`**.

1. Super admin `POST /admin/v1/invites` with `organization_id: null` + optional
   `plan_id` → user creates an org via `POST /invites/{id}/accept` with
   `{ "organization_name": "..." }`.
2. Super admin `POST /admin/v1/organizations` with `owner_email` — owner must
   already exist (one successful exchange).
3. Org owner `POST /organizations/{org_id}/invite` — join existing org.

Invite details:

- `GET /invites/{invite_id}` is **public** (no JWT). **410** if used or expired.
- `POST /invites/{id}/accept` requires Control JWT; email must match invite
  (case-insensitive).
- Deep-link: `{ORG_CONSOLE_URL}/invite?token={invite.id}` — not a MedRecs URL
  unless product proxies it.

Until the org has an **active subscription**, every metered call is denied
with `no active subscription`. Signed in ≠ provisioned.

### Seed path before any pipeline (SLA)

JWT works and **every pipeline is denied** until all of this is true:

1. User exists in `members` (one `/auth/exchange`).
2. Org exists; user is `owner` or `member`.
3. **Active subscription** whose billing window contains now.
4. **Entitlement** for `product_key` `medical`.
5. **Quota limits** per action (owner `PATCH /quotas/{org_id}` or admin). If
   no limit rows exist, limit checks are skipped (unlimited on that axis) but
   subscription + entitlement still apply.
6. Prepay: wallet + **price rows**. Postpay: see blocker #1 in
   [Must-fix in this CP tree](#must-fix-in-this-cp-tree-before-production-traffic)
   (NameError on allow until patched).

Who does this: **super admin**, except peer invites and owner quota PATCH.
After exchange, MedRecs probes products **server-side** and fails the UI
with “not provisioned” instead of starting Celery. The SPA does not call
CP products itself.

Org **quota** status is cached in Redis up to **10 minutes**, and **admin
suspend does not invalidate that cache** in this tree (must-fix). Limits
cache **5 minutes**.

**PHI lock must not use quota’s Redis status.** MedRecs projection must
call `GET /organizations/{id}` (Postgres) or `GET /members/me`. That is
fresh on suspend. UI copy should not promise instant cut-off on **metered**
paths until CP invalidates Redis on suspend.

---

## Product and action registration

Register in CP admin **before** MedRecs ships keys in code. Do not invent
`action_key`s only in Python.

Create `POST /admin/v1/products` with `product_key: "medical"` (freeze this
string). Pass that product’s UUID as `product_id` on every action.

If `product_id` is null, quota **skips entitlement**. Do not leave MedRecs
actions unlinked.

Seeded today: `medical.opinion.generate.v1` — **not** the keys below. Those
must be created.

Proposed freeze (CP accepts these exact strings; register them in admin
**before** MedRecs ships):

| `action_key` | `domain` | `unit_type` | When MedRecs calls it |
|---|---|---|---|
| `medical.case.analyze.v1` | `medical` | `count` | `POST /api/cases/{id}/processing/start` — **per run**, `quota/check` `units=1` |
| `medical.chat.message.v1` | `medical` | `tokens` | chat send / SSE — **only** reserve/commit path until commit counters exist |
| `medical.report.generate.v1` | `medical` | `count` | report generation — per run `quota/check` `units=1` |
| `medical.ocr.page.v1` | `medical` | `count` | extraction / OCR when page count is known — `quota/check` |
| `medical.chronology.generate.v1` | `medical` | `count` | chronology start — per run `quota/check` `units=1` |

**CP answer on extra keys:** do **not** meter `medical.case.create.v1` unless
product explicitly wants to bill case creation. If synthesis stays a distinct
expensive job, register `medical.synthesis.generate.v1` with `product_id`
before shipping; do not invent it only in MedRecs.

`unit_type` is a free string. Billing math is always:

```text
cost_cents = compute_units * rate_cents_per_compute_unit
```

If `compute_units` is omitted, it defaults to `units` / `max_units` /
`actual_units`.

**Gemini counting (chat only):** freeze prompt+completion vs completion, and
whether cached tokens count, next to `medical.chat.message.v1`. Pass **the
same dimension** on reserve `max_units`/`compute_units` and commit
`actual_units`/`compute_units`. On commit, CP reconstructs rate as
`held_cents / held_units` (**integer division**). Always set `compute_units`
explicitly to tokens when `unit_type` is `tokens`. Analyze is **count / per
run**, not Gemini tokens.

A price row is required for prepay; missing price → deny
`"No pricing configured for action_id=..."`.

`max_compute_units` on entitlements is **stored and returned, never enforced**
in quota check. Do not rely on it as a cap.

---

## The gate: quota (product-plane contract)

Auth is **not** the user JWT. It is:

```http
X-Internal-Api-Key: <INTERNAL_API_KEY>
```

(`Authorization: Bearer <same key>` also works.) Header names are
case-insensitive. The key is the **only** code-level guard. There is no mTLS
and no IP allowlist in CP. `/internal/v1/*` must not be on the public
internet.

**Confused deputy:** a leaked key can debit **any** `organization_id` the
caller sends. MedRecs must always set `organization_id` and `member_id` from
the **verified JWT**, never from the client body. Log `request_id` + org +
action; never log the key or medical content.

### HTTP status (branch on `allowed`, not status)

| Situation | Status | Body |
|---|---|---|
| Missing/wrong internal key | **401** | `{"detail": "Invalid or missing internal API key"}` |
| Business deny | **200** | `{ "allowed": false, "reason": "<string>", "current_usage"?, "limit"? }` |
| Business allow | **200** | `{ "allowed": true, "current_usage"?, "limit"? }` |
| `commit` / `rollback` reservation missing or bad | **400** | `{"detail": "..."}` |
| Unhandled (including postpay NameError) | **500** | `{"message": "Internal Server Error"}` |

Quota is **not** 403 when the org is not entitled. It is **200 + allowed=false**.

Fail-closed: CP **401 / 5xx / timeout** → MedRecs **503**, **do not run the
model**. Do not fail-open when `CONTROL_PLANE_ENABLED=false` in production.

### Deny `reason` → product HTTP

Match **full strings** where possible. Prefix-match entitlement and org
status. Do **not** map all `QuotaDenied` to 403.

| `reason` | Product HTTP |
|---|---|
| `organization status is suspended` / `archived` / `unknown` | 403 |
| `no active subscription` | 402 |
| `action not found or inactive` | 400 |
| `Organization is not entitled to product '{key}'` | 403 |
| `Entitlement to product '{key}' has expired` | 403 |
| `per_day limit exceeded` | 429 |
| `per_month limit exceeded` | 429 |
| `lifetime limit exceeded` | 429 |
| `insufficient_credits` | 402 |
| `request_id required for prepaid organizations` | 400 |
| `No pricing configured for action_id=...` | 503 (misconfig) or 400 |

JWT stays valid on deny. UI must show 402/403/429-style errors **without
logout**. Re-exchange will still succeed. Suspend/entitlement expiry is a
billing event, not an auth event.

CP does not send `Retry-After` on 429-equivalent denies. Product may add a
conservative retry delay locally; do not hammer quota/check in a loop.

### Two metering styles

**A. Known cost — `POST /internal/v1/quota/check`**

Use when units are known before work (page count, one chronology run). On
allow, usage is recorded **immediately**. If MedRecs then fails, the customer
has already been billed. Use only when failure is rare or you can compensate.

**B. Unknown cost — reserve / commit / rollback**

1. `POST /internal/v1/quota/reserve` — hold max units / max credits, `status=held`
2. Do the work
3. Success → `POST /internal/v1/quota/commit` with `actual_units` (+ `compute_units`)
4. Failure / cancel → `POST /internal/v1/quota/rollback`

### Practical MedRecs split (required until CP patches commit counters)

**Not fixed:** `quota_commit` writes `usage_ledger` and captures credits. It
does **not** increment Redis day/month or DB lifetime counters. Reserve only
*checks* limits against `max_units`; it does not consume them.

**Do not** bill the full case pipeline per token via reserve/commit until
commit counters exist. **Do not** reserve analyze with `max_units=50000`
(that can hold the whole prepaid wallet). Cap `max_units` **server-side**;
reject client-supplied caps.

| Work | Use |
|---|---|
| OCR pages known | `quota/check` `units=page_count` (known pages only; never optimistic OCR-then-quota) |
| Chronology / report / synthesis / **full analyze** | `quota/check` `units=1` (per run) |
| Chat only | `reserve` → work → `commit`/`rollback`; server cap on `max_units` (e.g. 8k tokens) |

Until commit counters ship, monthly/lifetime caps are **not** enforced on
reserve/commit. That is why analyze is per-run check, not a token hold.

### Idempotency, async jobs, hold TTL

- Always send `request_id`. Retries must reuse it. Prepaid orgs double-charge
  without it.
- **Format (this build):** opaque string. PostgreSQL column is unbounded
  `VARCHAR`. **Contract for MedRecs:** UUID v4 (lowercase, with hyphens),
  length ≤ 128, printable ASCII (`[A-Za-z0-9._:-]`). Do not put PHI in it.
  CP does not validate charset today; treat the contract as binding anyway.
- **No UNIQUE (`organization_id`, `request_id`)** in CP schema. Idempotency is
  SELECT-then-insert. Concurrent retries can double-insert. Product should
  still send a stable id and **serialize retries per job** (one in-flight
  reserve per `request_id` in MedRecs).
- **No hold TTL in Redis.** A `held` row lives until commit, rollback, or the
  reaper.
- Reaper (`scripts/reap_orphaned_holds.py`) rolls back holds **older than 1
  hour**. It is a **cron/manual script**, not in-app. If it is not scheduled,
  holds last forever and prepaid `held_balance_cents` stays locked.
- If Celery runs **> 1 hour** and the reaper is on, the hold can be rolled
  back while the worker is still running; commit then sees `status != held`
  and returns current status **without charging**. **Chat holds** must finish
  **< reaper cutoff** (analyze is per-run `check` — no hold). Or do not
  schedule the reaper until CP adds TTL + extend/heartbeat.

`X-Request-Id` already used for MedRecs request logs is **not** the quota
`request_id`. Quota id must be persisted on the job (processing start,
chat turn, report run) and passed to Celery. Prefer a dedicated
`Idempotency-Key` or job UUID, not the per-HTTP log id (retries of the
**same logical job** must share quota id; distinct HTTP calls must not).

### Worker identity

Celery and the OCR extractor **do not have the user JWT**. They must:

- use `INTERNAL_API_KEY`
- load `organization_id`, `member_id`, `action_key`, `request_id` from the
  **job row created at enqueue** — not from task kwargs the client could
  influence (confused deputy against the internal key)
- **Chat only:** commit on success, rollback on failure **and** on cancel.
  Analyze/OCR/report/chronology are `quota/check` — there is nothing to
  roll back if the job fails after allow (already billed).

Do not accept `X-Org-Id` or a client `organization_id` anywhere in this path.

### Partial pipelines

A case run may bill **more than one action** (OCR `quota/check`, then
analyze `quota/check`). Cancelling analyze does **not** un-bill OCR.
UX must say extraction is charged even if analysis is cancelled, or fold
OCR into the analyze run and drop the extra key. There is no multi-leg
transaction on CP.

---

## Request examples

**Fixed unit (OCR):**

```http
POST /internal/v1/quota/check
X-Internal-Api-Key: <secret>
Content-Type: application/json

{
  "organization_id": "<jwt org_id>",
  "action_key": "medical.ocr.page.v1",
  "units": 42,
  "compute_units": 42,
  "member_id": "<jwt sub>",
  "request_id": "<stable per logical request>"
}
```

**Analyze per run (required until commit counters exist):**

```http
POST /internal/v1/quota/check
X-Internal-Api-Key: <secret>

{
  "organization_id": "<from verified JWT, copied onto the job row>",
  "action_key": "medical.case.analyze.v1",
  "units": 1,
  "compute_units": 1,
  "member_id": "<jwt sub>",
  "request_id": "<job uuid persisted at enqueue>"
}
```

**Reserve (chat only — server-capped `max_units`, never 50000 for a pipeline):**

```http
POST /internal/v1/quota/reserve
X-Internal-Api-Key: <secret>

{
  "organization_id": "<from job row>",
  "action_key": "medical.chat.message.v1",
  "max_units": 8000,
  "compute_units": 8000,
  "member_id": "<from job row>",
  "request_id": "<job uuid>"
}
```

**Commit from Celery (success):**

```http
POST /internal/v1/quota/commit
X-Internal-Api-Key: <secret>

{
  "organization_id": "<same>",
  "request_id": "<same job uuid>",
  "actual_units": 1820,
  "compute_units": 1820
}
```

---

## What MedRecs must change

Will not work as-is. Highest risk first:

1. **PHI lock on every org-scoped route** — including GET cases, files, chat
   history, and GCS signed-URL minting. Require `owner|member`, JWT `org_id`
   matching the resource, and a short-TTL projection of `status == active`
   from **`GET /organizations/{id}` (Postgres)**. Do not use quota Redis
   status (can stay `active` 10 minutes after suspend). Do not wait on
   `org_status` in the JWT. On CP outage: if the projection TTL has elapsed
   → **403/503 on GET too**. Never serve GET because “CP is down.”
2. **CP is a backend sidecar** — keep `POST /api/auth/exchange` on MedRecs,
   upsert `control_member_id`, return `/api/auth/session` projection. SPA
   must not know CP URLs except the org-console billing **link**. httpOnly
   cookie is **preferred, not a gate** — do not block the PHI-lock PR on
   cookies; answer [editor origin](#7-questions-cp-still-wants-medrecs-to-answer)
   first (`SameSite=None` if the editor is another origin).
3. **Delete `X-Org-Id`** (400 if sent). Do not take `organization_id` in JSON
   bodies. Celery reads org/member/`request_id` from the **job row**.
4. **One JWT verifier** (MedRecs + editor + OCR). Read `level_of_access`,
   require `iss`. Join users by `sub`, not email.
5. **Guest and super_admin** — 403 on case APIs. Never map `super_admin` →
   owner. Never keep `admin`/`viewer` that look like CP roles.
6. **Remove hardcoded org UUID** in `Frontend/medrecs-app/src/lib/apiClient.js`.
7. **Use cases call `quota_gate.allow(...)`** — zero `action_key` strings in
   domain. Tests mock the HTTP client, not the use case (that is why metering
   never ran).
8. **Metering freeze:** analyze/report/chronology/synthesis = `quota/check`
   `units=1`. OCR = `check` with known pages. **Chat only** = reserve/commit
   with a **server-side** `max_units` cap. Quota **before** work; no
   optimistic OCR-then-quota; no retry of `allowed: false`.
9. **Map quota `reason`** as in the table. 503 (not 502) when CP is down.
10. **`CONTROL_PLANE_ENABLED=true` in staging and prod.** Flag is laptop-only.
11. **Never put `INTERNAL_API_KEY` in the browser.** No staff backdoor that
    skips quota. No second invoice ledger.

Can keep (projection, not source of truth):

- Local `users` + org row copies, refreshed from CP, authorized from the
  **request JWT**
- Existing exchange proxy `POST /api/auth/exchange` — **required**, not
  optional (sidecar)

Must not keep:

- Org switcher / polling `/organizations/me` as multi-org sync
- `X-Org-Id` “ignored if it disagrees”
- Local wallet / `quota_allowed` / rebuilt invoices
- Browser calling CP except nothing (org-console link only)
- `useControlPlane` dual-token picker
- Four-role enum that can authorize a local viewer who is a CP `member`

### Token refresh and long-lived requests

Control JWTs are short-lived (~30 minutes). Chat SSE and long uploads can
outlive the token that started them.

- Frontend: Firebase `getIdToken(true)` → **MedRecs** `/api/auth/exchange`
  **before** `exp`, with a single-flight lock. Cookie refresh is server-side
  if using httpOnly.
- Do not treat quota 402/403 or org-suspended 403 as auth expiry (no logout).
- In-flight SSE: finishing the stream is OK; the **next** send must use a
  fresh session. Starting a new metered turn with an expired JWT is 401.

### What must never go to Control Plane

Quota and identity payloads: ids, action keys, unit counts. **No PHI** — no
case text, filenames of records, chat messages, or GCS URLs.

### Observability

Correlate `request_id` (quota), MedRecs `X-Request-Id` (HTTP), and Celery
task id. Log `allowed`, `reason`, `action_key`, `org_id`. Redact tokens,
API keys, and medical payloads.

---

## What Control Plane will change (answers)

Status is against **this git tree**. “Will fix” means CP owns the patch before
production traffic. “Not this build” means MedRecs must design around it.

### Must-fix in this CP tree before production traffic

| # | Item | CP answer |
|---|---|---|
| 1 | Postpay `NameError` in `quota_check` | **Will fix.** `charge_compute_units` / `cost_cents` are only set on the prepay path, then always passed to `record_usage`. Default `billing_mode` is `postpay`. Allow can **500**. MedRecs analyze/OCR/report/chronology use **`quota/check`**, so “use reserve/commit only” is **not** a workaround for those paths. Until patched: **prepay test orgs**, or do not send postpay traffic to `quota/check`. Chat reserve/commit is safer for postpay today (`cost_cents` defaults to 0) but is **not** a substitute for analyze. |
| 2 | Commit updates day/month/lifetime counters | **Will fix.** Until then, reserve/commit does **not** consume Redis/DB limits. MedRecs must use `quota/check` when limits must stick. |
| 3 | UNIQUE `(organization_id, request_id)` + hold TTL + in-process reaper | **Will fix.** Today: no unique constraint, no Redis TTL, reaper is `scripts/reap_orphaned_holds.py` (1 hour, cron/manual). MedRecs must serialize retries and keep chat holds &lt; 1h if the reaper is scheduled. |
| 3b | Invalidate Redis `org_status` on admin suspend/activate | **Will fix.** `invalidate_org_status` exists but suspend does **not** call it. Quota can keep allowing for **10 minutes** after suspend. **PHI lock must use `GET /organizations/{id}` (DB), not quota status.** |
| 4 | CORS allowlist | **Will fix** for org-console → CP. MedRecs SPA must **not** call CP (sidecar). Still restrict MedRecs CORS (today also `*` + credentials). |
| 5 | `/internal/v1` private URL | **Ops, not app code.** Key is the only code-level guard. Deploy behind a private network / gateway. No mTLS in this tree. |
| 6 | Admin seed for MedRecs | **Ops before go-live.** Create `product_key=medical`, the frozen `action_key`s, prices, and per-customer active subscription + entitlement + limits. Not a MedRecs bug if this is missing. |

### Not this build (MedRecs must not wait)

| # | Item | CP answer |
|---|---|---|
| 7 | Machine-stable deny codes | **Not this build.** Match the `reason` strings in [Deny reason](#deny-reason--product-http). Prefix-match entitlement and org status. |
| 8 | Hold heartbeat / extend | **Not this build.** **Chat holds** must finish **&lt; 1 hour** if the reaper runs, or do not schedule the reaper until a heartbeat exists. Analyze has no hold. |
| 9 | Dual-role token for super admins | **Not this build.** Exchange prefers `super_admin` and **omits `org_id`**. MedRecs **403** super_admin on case APIs. Do not map to owner. They use `/admin/v1` only. |
| 10 | JWT `aud` claim | **Not this build.** Product must still require `iss` + JWKS from **this** CP base URL. Do not share JWKS across issuers. |
| 11 | Key rotation with a new `kid` | **Not this build.** `kid` is always `control-plane-1`. Short JWKS cache (minutes). |
| 12 | `Retry-After` / `quota_decision_id` | **Not this build.** Product may add a local delay; do not loop quota/check. Trace with `request_id`. |
| 13 | Suspend webhook | **Not this build.** Quota Redis `org_status` can stay `active` **10 minutes** after suspend (`invalidate_org_status` is not called — must-fix **3b**). PHI lock uses org GET (Postgres), so this lag is a **quota** problem, not the PHI signal. |
| 14 | Separate OpenAPI for internal quota | **Not this build.** Contract is this doc + FastAPI `/docs` on CP. |
| 15 | `request_id` format | **Answered in this doc:** UUID v4, ≤ 128 chars, `[A-Za-z0-9._:-]`, no PHI. |
| 16 | Integer division on commit rate | **Not this build.** Always pass `compute_units` equal to the billed dimension on both reserve and commit. |
| 17 | Enforce `max_compute_units` on entitlements | **Not this build.** Field is stored and returned, **never enforced**. Use quota limits + credits. |
| 18 | In-app reaper + metrics | **Same as #3.** Will fix as part of hold TTL work; not available today. |
| 19 | 409 after reaper rollback | **Not this build.** Commit on a non-`held` row returns `{ "status": "<current>" }` without charging. Treat that as a billing miss; do not retry commit blindly. |
| 20 | Invite freeze to 2099 | **Current behavior.** First `/auth/exchange` sets pending invite `expires_at` to 2099-12-31. MedRecs UX can treat pending invites as non-expiring after first login. Do not rely on wall-clock expiry after that. |

---

## Security notes

- Internal key comparison on CP uses `secrets.compare_digest` — good. Rotate
  `INTERNAL_API_KEY` with CP; keep it only in product-plane **backend** env
  (API + workers + OCR worker). A leaked MedRecs key can still charge **every
  medical org** until `/internal/v1` is private and tenant is taken only
  from the JWT.
- Control JWTs are claim-based RBAC. Role changes apply on **next exchange**,
  not live DB lookup. Org **suspend** is not in the JWT; PHI lock is the
  org GET projection.
- Same quota path for every user. No “trusted internal” skip.
- Same Firebase **project** as CP. If not, exchange fails.
- Browser → MedRecs only. MedRecs → CP for exchange, profile, products,
  quota. SPA knows CP only as an org-console **link** (billing, and by
  default invites). Invite GET/accept is proxied by MedRecs **only** if it
  hosts an invite page.

---

## Questions closed by Control Plane

These were the original MedRecs blockers. Answers are from this repo.

| # | Question | Answer |
|---|---|---|
| 1 | JWT dump, `kid`, `iss`, field names, `sub` | See [Identity and JWT](#identity-and-jwt). `sub` is UUID `member_id`. `token_type` is `Bearer`. `kid` is `control-plane-1`. No `roles`. |
| 2 | Does `GET /organizations/me` exist? | **Yes.** Array of 0–1 orgs. Prefer `GET /members/me` (`organization` singular, includes name/slug/status/`role`). |
| 3 | How does a user get an org? | Invite-only on the public API. Deep-link `{ORG_CONSOLE_URL}/invite?token={id}`. Accept requires JWT + matching email. Second org → 400. |
| 4 | Product / action registration | Freeze `product_key=medical` and the action table in [Product and action registration](#product-and-action-registration). Every action **must** have `product_id` + a price row (prepay). |
| 5 | Who seeds a customer org? | Super admin: org (or org-create invite), plan subscription, entitlement, limits. Owner may PATCH quotas. Signed in ≠ provisioned. |
| 6 | check vs reserve/commit | See [Two metering styles](#two-metering-styles). Commit does **not** increment limit counters until CP patches #2. |
| 7 | Postpay NameError | **Not patched in this tree.** Blocker #1. |
| 8 | Hold TTL / dead worker | No Redis TTL. Reaper is 1 hour **if scheduled**. Dead worker leaves `held` until reaper or rollback. |
| 9 | Quota HTTP status | 401 bad key; **200** `{allowed, reason}` for business allow/deny; 400 bad commit/rollback; 500 unhandled. Fail-closed on 401/5xx/timeout. |
| 10 | Network / key | Key only. `/internal/v1` must be private. Rotate `INTERNAL_API_KEY` with CP. Never in the browser. |
| 11 | `admin` / `viewer` | **Will not add in this build.** Only `owner` and `member`. Collapse MedRecs roles. |
| 12 | Org switch | **Final: one org.** No switch endpoint. **Delete `X-Org-Id`** (400 if sent). |
| 13 | Guest token | Store only for invite-accept + re-exchange. 403 on all MedRecs case APIs. |
| 14 | Super admin on product APIs | **Deny.** No `org_id` on that JWT. `/admin/v1` only. Do not map to owner. |
| 15 | Gemini `actual_units` vs `compute_units` | Same billed dimension on both. Cost = `compute_units * rate_cents_per_compute_unit`. Default: `compute_units = units`. |
| 16 | JWT vs quota deny | JWT stays valid. That is why **reads need a status projection**, not only quota. UI must not logout on 402/403/429. |
| 17 | JWKS / issuer / kid | Per-env `JWT_ISSUER` (example `control-plane`). `kid` always `control-plane-1`. Fetch JWKS from that CP (**MedRecs backend**). |
| 18 | CORS | Wildcard today. Will fix. **Do not** depend on browser→CP. Sidecar makes CORS on CP less critical for MedRecs SPA. |
| 19 | Deny `reason` codes | Human strings only. Table in [Deny reason](#deny-reason--product-http). |
| 20 | Can product read usage? | Yes, MedRecs may proxy member GETs. Writes are admin. Billing UI = org-console link. |

---

## What MedRecs still decides

CP **mandates** the rows marked required. Remaining items are listed as
[open questions](#7-questions-cp-still-wants-medrecs-to-answer) — answer them
in product, then freeze here.

| Topic | Required (not optional) | Still a MedRecs choice |
|---|---|---|
| Org picker / `X-Org-Id` | **Delete.** 400 if header sent. No `organization_id` in JSON. | **Migration:** which local org is the surviving CP membership; leftover case data plan |
| `admin` / `viewer` | **Must not look like CP roles.** Map owner/member only. A local viewer who is a CP `member` can still mutate if you only check the overlay | Delete those roles, or a **stricter** MedRecs ACL that never loosens CP |
| Billing UI | No second ledger. Writes stay on CP admin | Org-console **link** (required default). Proxy usage summary only if needed |
| Invite UX | SPA does not call CP. Re-exchange after accept. Canonical deep-link is `{ORG_CONSOLE_URL}/invite?token=` | MedRecs invite page that **proxies** accept vs send users to org console |
| Pipeline metering | **Frozen:** analyze/report/chronology/synthesis = per-run `check` `units=1`. OCR = pages. Chat = reserve/commit with server cap | Token-counting rule for chat (prompt+completion vs completion; cached tokens) |
| Fail-closed | **Required** for writes, models, signed URLs, **and GET when projection TTL elapsed**. `CONTROL_PLANE_ENABLED=false` is laptop only — **not staging** | None. Serving GET because CP is down reopens PHI after a suspend you cannot see |
| Job duration vs 1h reaper | No heartbeat in this build. Analyze is per-run check so long jobs do not hold wallet | Max agentic **wall time** (must be known; holds only used for chat) |
| Firebase project | **Same project** as that CP env | None |
| Browser vs backend | **Sidecar.** SPA does not call CP. Quota never from browser | JWT storage: httpOnly cookie (preferred) vs localStorage + XSS story; editor origin / SameSite |
| Email verification | CP does **not** require it | Keep MedRecs verify-before-exchange or not |
| Staff access to a customer case | **Do not** map `super_admin` → owner | If needed, that is a **CP impersonation** feature — see [CP work to spec](#cp-work-to-spec-on-the-control-plane-side) |

---

## Integration sequence (implementation order)

Suggested PR slices so auth is not half-migrated and PHI is not left open.
Do **not** block slice 2 on cookies or on `org_status` in the JWT.

1. **One JWT verifier** — `iss`, `kid`, `level_of_access`; reject
   guest/super_admin; bind user by `sub`; **delete `X-Org-Id`**.
2. **PHI lock** — short-TTL `status == active` from org GET (Postgres) on
   **every** org-scoped route including GET and signed URLs. Expired cache +
   CP outage → 403/503 on GET. Bearer JWT is enough.
3. **Sidecar session** — MedRecs `POST /api/auth/exchange` + `/api/auth/session`
   projection; SPA drops CP base URL and dual tokens. Cookie vs storage after
   editor-origin (question 2) is answered.
4. **Quota port** — `quota_gate.allow(...)`; constants module for `action_key`s;
   reason → HTTP; tests mock HTTP client.
5. **Wire metering** — per-run `check` on analyze/report/chronology/OCR;
   reserve/commit **chat only** with server cap; persist `request_id` on the
   job row; workers read the row.
6. **Editor + OCR** on the same verifier. No header fallback.
7. **Admin seed** in CP and a contract test against a mock CP.

---

## Local development

- `CONTROL_PLANE_ENABLED=true` (including **staging**; laptop-only exception)
- `CONTROL_PLANE_BASE_URL` / `CONTROL_PLANE_JWKS_URL`
- `CONTROL_PLANE_JWT_ISSUER` (must match that CP)
- `INTERNAL_API_KEY` matching CP (never commit the real value)
- Same Firebase project as that CP environment

Without an active subscription + `medical` entitlement, every metered call
returns `allowed: false` with `no active subscription` or not-entitled. That
is expected, not a MedRecs bug.

Until postpay `quota/check` is patched, use a **prepay** test org. Do not
route postpay analyze/OCR through `quota/check`. Chat reserve/commit is
safer for postpay today (`cost_cents` defaults to 0) but is **not** a
substitute for analyze.

---

## Related code (MedRecs today)

| Piece | Path |
|---|---|
| Exchange proxy | `backend/app/api/routes/auth.py` |
| JWT verify | `backend/app/core/control_jwt.py` |
| Tenant (Firebase + `X-Org-Id`) | `backend/app/core/tenant_context.py` |
| CP HTTP client | `backend/app/infrastructure/integrations/control_plane/client.py` |
| Port | `backend/medrecs/ports/control_plane.py` |
| Error mapping | `backend/app/api/errors.py` |
| Frontend tokens | `Frontend/medrecs-app/src/lib/apiClient.js` |
| Editor JWT | `editor_backend/src/auth/middleware.js` |

---

## CP recommendations to MedRecs

These are **required MedRecs architecture**, not optional style notes. The
HTTP/JWT contract above is what CP does; this section is what MedRecs must
not get wrong.

### 1. Make CP a backend sidecar, not a third origin for the SPA

**Counter:** browser → CP for exchange / `members/me` / products, and browser
→ MedRecs for cases.

That splits auth across two APIs, two CORS policies, two token lifetimes, and
a race where the first case call happens before `users` exists.

**Prefer:**

```text
Browser  →  MedRecs only (session cookie or Control JWT)
MedRecs  →  CP (exchange, members, products, quota;
           invite GET/accept only if MedRecs hosts an invite page)
```

- Keep `POST /api/auth/exchange` on MedRecs. Upsert `users.control_member_id`
  in the same request. Return a **session projection** (`member_id`, `org_id`,
  `role`, `products[]`, `exp`).
- Do not teach the SPA CP URLs except the org-console **link** for billing.
- Stronger later: MedRecs sets an **httpOnly, Secure, SameSite** cookie
  after exchange instead of `localStorage` (XSS can steal a Bearer token).
  **Not a ship gate.** If the editor is another origin, cookies need
  `SameSite=None` plus a real XSS story — answer question 2 before choosing
  cookies. Firebase can stay in memory for `getIdToken(true)` only.

Editor and OCR must use the **same** verifier as MedRecs (shared library or
copied JWKS settings). Three slightly different middlewares is how `X-Org-Id`
fallback survived.

### 2. JWT is identity, not authorization for PHI

CP JWT stays valid when the org is **suspended**, entitlement expired, or
subscription dead. Quota only runs on metered paths.

**If MedRecs only gates processing/chat, a suspended tenant can still GET
cases, files, GCS signed URLs, and chat history.** That is the highest-risk
gap in the current plan.

Required on **every** org-scoped MedRecs route (reads included), not only
LLM:

- `level_of_access` in `{owner, member}`
- `org_id` present and equal to the resource’s org
- local projection of `organization.status == active` (refresh from
  `GET /organizations/{id}` or `GET /members/me` on a short TTL, e.g. 60s)
- for writes / processing: entitlement `medical` present and not expired

Do **not** wait for a CP webhook or for `org_status` on the JWT. A 30-minute
claim is **slower** to suspend than a 60s `GET /organizations/{id}`. The
**projection is the lock**; a future claim is only fewer GETs. Still need
the projection after the claim exists (JWT can be stale). Do **not** assume
quota-on-start is enough (quota Redis can stay `active` 10 minutes).

On CP outage: fail-closed for writes and signed URL minting. If the
projection TTL has elapsed and CP cannot be reached → **403/503 on GET
too**. Never fail-open to “allow GET because CP is down.”

### 3. Do not let the client name the tenant or the bill

- Delete `X-Org-Id`. Do not keep it as a “hint.”
- Do not accept `organization_id` in product JSON bodies. Derive from JWT.
- Celery payloads: treat `organization_id` / `member_id` / `request_id` as
  **server-issued**. Persist them on the job row at enqueue; worker reads
  the DB, not the client. A guessed task arg must not debit another org.
- **Per-product internal keys do not fix this.** They only stop MedRecs from
  billing `legal.*` / `vision.*`. A leaked MedRecs key can still charge
  **every medical tenant**. Tenant from JWT + private `/internal/v1` stays
  mandatory.
- GCS object keys and signed URLs must include `org_id` from the JWT and be
  checked again at mint time. Guessable paths are a data leak; quota will
  not see them.

### 4. Design counters (please do not do these)

| Tempting MedRecs choice | Why to reject it |
|---|---|
| Keep `admin` / `viewer` as CP-looking roles | CP will not enforce them. A “viewer” who is a CP `member` can still pass quota and mutate if your use case only checks the local enum. Collapse to owner/member or keep viewer as a **separate** MedRecs ACL that is stricter than CP, never looser. |
| Map `super_admin` → owner “so we can debug cases” | Super-admin JWT has **no** `org_id`. That is impersonation. Use CP admin + a future impersonation API, not MedRecs. |
| `CONTROL_PLANE_ENABLED=false` in staging | Staging will lie; someone will ship it. Use a real CP (or a recorded mock with the same deny reasons). Flag is local laptop only. |
| Reserve pipeline with `max_units=50000` “to be safe” | Prepaid hold can lock the whole wallet. **Do not reserve analyze.** Chat cap is server-side (e.g. 8k). OCR = known pages. Reject client-supplied caps. |
| Bill the full case pipeline per Gemini token via reserve/commit | Hold TTL, integer division, commit **not** updating limit counters, jobs &gt; 1h. **Bill `medical.case.analyze.v1` per run** (`quota/check` `units=1`) until CP patches commit counters. Use reserve/commit for **chat** (short, known-ish). |
| Optimistic UI: start OCR then quota | You will run work you cannot charge and cannot legally justify if deny comes back. Quota first, always. |
| Retry `quota/check` on 200 `allowed: false` | That is not transient. Retry only 401-after-refresh (user JWT), and CP 503/timeout with backoff, same `request_id`. |
| Poll `GET /organizations/me` to sync multi-org | One org. Polling creates a fake switcher. Session from exchange + `members/me` once. |
| Rebuild invoices/credits in MedRecs | Coupling. Link org console. Proxy usage summary if the in-app graph is needed. |
| Skip quota for “internal users” / staff | Same path for everyone. Staff use super-admin on CP, not a MedRecs backdoor. |
| Store Control JWT next to Firebase token and pick with `useControlPlane` | One credential on product APIs after login. The flag is how the editor/API split drifted. |

### 5. Clean division of work (one module, one mapping)

MedRecs should have **one** Control Plane adapter and **zero** CP types in
domain use cases beyond a port:

```text
app/core/control_jwt.py          verify only (JWKS, iss, exp, claims)
app/.../control_plane/client.py  HTTP: exchange, members, products, quota_*
medrecs/ports/control_plane.py   check / reserve / commit / rollback / status
medrecs/domain/*                 no HTTP, no JWT, no action_key strings
```

- Freeze `action_key`s in **one** constants module. Frontend never sends
  action keys. Workers import the same constants.
- Use cases call `quota_gate.allow(...)` and get a domain error. They must
  not import `HttpControlPlaneClient`. That is why `quota_check` exists and
  never runs today.
- Local `organizations` / `organization_memberships`: **cache/projection**
  with `control_member_id` + `org_id`. Authorize from the **request JWT**,
  then load the local row. If JWT `org_id` ≠ local row, 403 and refresh —
  do not “heal” by trusting local.
- Join users by `control_member_id = sub`, not email (email can change in
  Firebase).
- Timeouts: quota HTTP **≤ 2s**, fail-closed. No unbounded retries.
- Circuit breaker: if CP is down **and** the status projection TTL has
  elapsed, org-scoped **GET**, metered routes, and signed-URL minting all
  403/503. Do not queue Celery “to drain later” without a hold (you cannot
  commit later without a reservation). Do not serve GET because CP is down.

Tests: mock at the **HTTP client** boundary with recorded allow/deny
bodies. Stubbing `check_quota` inside the use case is how metering was
skipped. Add one contract test per `reason` string.

### 6. Metering freeze until CP is patched

Required (not a suggestion):

| Job | Action | Style | Why |
|---|---|---|---|
| Create case | none | — | Not billable |
| OCR / extract | `medical.ocr.page.v1` | `check`, `units=pages` | Known up front |
| Full pipeline | `medical.case.analyze.v1` | `check`, `units=1` | Per-run; avoids long holds |
| Chat turn | `medical.chat.message.v1` | reserve → commit/rollback | Tokens unknown, short; **server cap** |
| Report | `medical.report.generate.v1` | `check`, `units=1` | Per-run until commit counters exist |
| Chronology | `medical.chronology.generate.v1` | `check`, `units=1` | Per-run |
| Synthesis (if separate) | `medical.synthesis.generate.v1` | `check`, `units=1` | Same |

Partial pipelines: OCR `check` is already billed if analyze is **cancelled**.
(Analyze is per-run `check`, not reserve — there is nothing to roll back.)
UX should say extraction is charged even if analysis is cancelled, or fold
OCR into the analyze run and drop the extra key.

### 7. Questions CP still wants MedRecs to answer

Do not start implementation PRs that guess these. Write the answers into
this doc. Q4 (Celery job row only) and Q5 (403 GET on suspend via
projection) are **already required architecture** — confirm in code, do not
re-open.

1. **JWT storage:** httpOnly cookie (preferred) vs `localStorage`? **Not a
   gate for the PHI-lock PR.** If localStorage, what is the XSS story (CSP,
   no `eval`, no user HTML)?
2. **Editor origin:** same site as MedRecs or a separate origin that needs
   CORS + cookie `SameSite=None`? **Answer this before choosing cookies.**
3. **GCS:** are object names prefixed by `org_id`? Is minting signed URLs
   on the same auth stack as cases (PHI lock + JWT org, not quota)?
4. ~~Celery enqueue org in task kwargs~~ **Closed:** job row only.
5. ~~Suspended-org GET~~ **Closed:** 403 on GET cases/files/history/signed
   URLs via org GET projection — not quota.
6. **Staff access to a customer case:** if you need this, say so; do not
   overload `super_admin`. That is CP impersonation (below). Not a MedRecs
   backdoor.
7. **Max agentic wall time** (holds are chat-only; still need a bound for
   workers and cancel).
8. **Token counting for chat:** prompt+completion vs completion only; cached
   tokens in or out. Freeze next to `medical.chat.message.v1`.
9. **Multi-org leftovers:** one surviving `org_id`; written migration, not
   “first row in local DB.”
10. **Same Firebase project** ids for staging and prod as the CP envs they
    call.

---

## CP work to spec on the Control Plane side

These are **not** how MedRecs solves PHI or confused deputy. Do **not**
block MedRecs on `org_status` in the JWT. Spec impersonation and
per-product keys **when product actually needs them**.

| Ask | What it actually buys | What it does **not** buy |
|---|---|---|
| **`org_status` on the JWT** | Fewer CP GETs on hot reads | **Not the PHI lock.** A 30-minute claim is slower to suspend than a 60s org GET. Projection stays required even after the claim exists. |
| **Per-product internal API keys** | A leaked MedRecs key cannot bill `legal.*` / `vision.*` | **Does not** stop debiting **any medical org**. Tenant from JWT + private `/internal/v1` stays mandatory. |
| **Impersonation / dual-role token** | Staff open a customer case without mapping `super_admin` → owner | Not a MedRecs backdoor. Until spec’d, staff stay on `/admin/v1`. |
| Must-fix **3b**: call `invalidate_org_status` on suspend/activate | Quota Redis stops lying `active` for 10 minutes | Still **not** the PHI signal. PHI lock uses `GET /organizations/{id}` (Postgres). |
| Hold heartbeat, unique `(org, request_id)`, commit counters, postpay NameError | Billing correctness | Unrelated to PHI reads |

Ship MedRecs PHI lock + sidecar **without waiting on JWT `org_status` or
cookies**. Still write the remaining open answers before guessing them in
PRs. Ask CP for 3b (invalidate on suspend) as a quota correctness fix.
Spec impersonation / per-product keys only when product needs staff-in-case
or multi-product isolation.

---

## Checklist


### Control Plane / ops

- [ ] Patch postpay `NameError` (`quota_check`) or waive with prepay-only orgs
- [ ] Patch commit so day/month/lifetime counters increment, or waive with check-only limits
- [ ] UNIQUE `(organization_id, request_id)` + hold TTL / in-process reaper (or serialize + chat holds &lt; 1h)
- [ ] Invalidate Redis `org_status` on suspend/activate (**3b** — quota lag only; PHI lock uses org GET)
- [ ] CORS allowlist for **org console** → CP; MedRecs SPA does not call CP; `/internal/v1` private
- [ ] Admin seed: `product_key=medical`, frozen `action_key`s, prices
- [ ] Each customer org: active subscription + `medical` entitlement + quota limits (+ wallet if prepay)
- [ ] Shared Firebase project, JWKS URL, `JWT_ISSUER`, rotated `INTERNAL_API_KEY`

### MedRecs

- [ ] Sidecar: browser → MedRecs only; `POST /api/auth/exchange` upserts `sub`; `/api/auth/session` projection
- [ ] **PHI lock (do not wait on JWT `org_status` or cookies):** 403 GET cases/files/signed URLs unless org GET (Postgres) says `active`; expired cache + CP down → 403/503 on GET
- [ ] **Delete `X-Org-Id`** (400 if sent); no client `organization_id`; Celery reads the job row
- [ ] One JWT verifier (MedRecs + editor + OCR); `iss` + `level_of_access`; join users by `sub`
- [ ] `owner`/`member` only; 403 guest and super_admin; no admin/viewer that look like CP roles
- [ ] `quota_gate.allow(...)`; one `action_key` constants module; tests mock HTTP, not the use case
- [ ] Metering freeze: analyze/report/chronology = `check` `units=1`; OCR = pages; **chat only** reserve/commit with server cap (commit `actual_units` ≤ cap)
- [ ] Stable UUID `request_id` on the job row; deny `reason` → 402/403/429
- [ ] `CONTROL_PLANE_ENABLED=true` in staging/prod; no staff quota skip; no second invoice ledger
- [ ] Answer editor origin (Q2) before cookies; cookie vs storage is preferred, **not** a PHI-lock gate
- [ ] Remaining open (write into this doc before guessing in PRs): editor origin, cookie vs storage, GCS prefix + signed URLs, surviving local org, chat token counting, max agentic wall time, staff-in-case (CP impersonation spec)
