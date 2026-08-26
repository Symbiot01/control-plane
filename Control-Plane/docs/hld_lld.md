# MedRecs ↔ Control Plane — HLD / LLD (devs)

Source of truth: [control_plane_integration.md](control_plane_integration.md).
This is how the services **connect**. Not a green light on production code.

**Planes:** Control Plane (CP) = identity, orgs, entitlements, quota, billing.
MedRecs = cases, files, GCS, OCR, pipeline, chat. CP is a **MedRecs-backend
sidecar**. The SPA talks to MedRecs (+ Firebase Auth) only.

**Suspend policy (accepted):** login and **GET/read** stay allowed. OCR /
analyze / chat / reports are **denied by quota**. No per-request org-status
lock on reads. GCS paths still must match JWT `org_id` (other-org leak).

---

## HLD

```text
  Browser / Editor          MedRecs API + workers           Control Plane
  ─────────────────         ─────────────────────           ──────────────
  Firebase sign-in
       │
       │  POST /api/auth/exchange {id_token}
       ├──────────────────► upsert users.control_member_id
       │                    POST {CP}/auth/exchange  ──────► Control JWT
       │  GET /api/auth/session
       │◄── member_id, org_id, role, products, exp
       │
       │  Bearer JWT (cookie later; not a gate)
       ├──────────────────► verify JWKS (RS256, iss)
       │                    JWT org_id must match the resource
       │                    GET cases/files allowed even if org suspended
       │
       │  POST .../processing/start | chat
       ├──────────────────► quota_gate.allow(...)
       │                    POST {CP}/internal/v1/quota/* ──► allow/deny
       │                    suspended → allowed:false (processing only)
       │                    persist request_id on job row
       │                          │
       │                          ▼ Celery / OCR
       │                    load org/member/request_id from DB
       │                    check: billed already
       │                    chat: commit / rollback
```

**Who calls whom**

| From | To | Auth | Why |
|---|---|---|---|
| Browser | Firebase | SDK | Login only |
| Browser | MedRecs | Control JWT (Bearer; cookie TBD) | All product APIs |
| Browser | Org console | Control JWT | Invites (default), billing **link** |
| Browser | CP | **never** | Except org-console pages |
| MedRecs | CP `/auth/exchange`, `/members/me`, `/organizations/{id}` | user JWT after exchange | Session + products UX (not a read lock) |
| MedRecs / workers | CP `/internal/v1/quota/*` | `X-Internal-Api-Key` | Metering / suspend on **processing**. Key never in browser |
| Super admin | CP `/admin/v1` | Control JWT `super_admin` | Plans, entitlements, seed |

**Trust rules:** tenant = JWT `org_id` (no `X-Org-Id`, no `organization_id` in
JSON). Roles = `level_of_access` `owner`\|`member`\|`viewer`. Guest / super_admin
→ 403 on cases. Viewer → GET cases/files/history only; mutate 403 before quota;
quota with `member_id=sub` returns `viewer_readonly`. Quota blocks **processing**
when suspended; reads stay open.

---

## LLD

### 1. Identity

1. SPA: Firebase `getIdToken` → `POST {MEDRECS}/api/auth/exchange`.
2. MedRecs: `POST {CP}/auth/exchange` `{id_token}` → `{access_token, token_type: Bearer, expires_in, has_pending_invites}`.
3. JWT (RS256, `kid: control-plane-1`): `sub` = CP `member_id`, `iss`, `iat`, `exp`, optional `org_id`, `level_of_access`. **No `roles[]`.** Verify via `{CP}/.well-known/jwks.json`. Require `CONTROL_PLANE_JWT_ISSUER`.
4. Upsert local `users` on `control_member_id = sub`. Join by `sub`, not email.
5. `GET {MEDRECS}/api/auth/session` = projection (`GET {CP}/members/me` including
   `entitlements[]` + products). SPA never calls CP. Suspended orgs may still get a
   session (reads allowed). Viewers must **not** call `GET .../products` (403);
   use `/members/me` entitlements.
6. Refresh: `getIdToken(true)` → MedRecs exchange again. ~30 min TTL. Quota 402/403 ≠ logout.
7. After invite accept, **exchange again** (accept does not mint a new JWT).

Invite GET/accept live on **org console**. MedRecs proxies them **only** if it
hosts an invite page.

### 2. Tenant on every org-scoped route (including GET)

Middleware, before use cases:

1. Verify JWT. Require `org_id` + `level_of_access` in `{owner, member, viewer}` for GET.
   Mutating / metered: `{owner, member}` only (viewer → 403 before quota).
2. Resource `org_id` must equal JWT `org_id`. Else 403.
3. **Do not** require `organization.status == active` on GET. Suspended
   tenants may read cases, files, history, and existing URLs.
4. GCS object keys / new signed URLs: prefix and check JWT `org_id` (stop
   cross-org access). Quota does not see downloads. Status is **not** checked.
5. Unmetered writes (PATCH, upload) are **not** blocked by quota. Default:
   same as GET (allowed while suspended) unless product later gates them.
   **Exception:** viewer must still be denied on writes.

### 3. Quota (before expensive work only)

Header: `X-Internal-Api-Key`. Body: `organization_id` + `member_id` from
**verified JWT**, copied onto the **job row** at enqueue. Workers read the
row, not task kwargs. `request_id` = UUID v4, reused on retry.

This is what **stops processing** when the org is suspended, has no
subscription, is not entitled, or is out of credits/limits.

| Job | `action_key` | Call |
|---|---|---|
| OCR | `medical.ocr.page.v1` | `POST /internal/v1/quota/check` `units=pages` |
| Analyze / report / chronology / synthesis | `*.v1` | `check` `units=1` (per run) |
| Chat | `medical.chat.message.v1` | `reserve` → work → `commit`/`rollback`; server `max_units` cap (e.g. 8k) |

HTTP: 401 = bad key; **200** `{allowed, reason, status}` for business deny;
**404** missing reservation; **400** validation; **409** idempotency/state
conflicts; 5xx/timeout → MedRecs **503**. Map `reason`: suspended /
not entitled → 403; no sub / `insufficient_credits` → 402; `*_limit exceeded`
→ 429. Do not retry `allowed: false`. Quota timeout ≤ 2s. No PHI in CP payloads.

Analyze `check` has **nothing to roll back** if the job later fails (already
billed). Chat holds must finish before `QUOTA_HOLD_TTL_SECONDS` (default 1h)
or commit returns **409** after expiry.

PostgreSQL `quota_usage_buckets` are authoritative for limits. Postpay
`quota/check` is safe (`cost_cents=0`; invoices still use `compute_units`).
Chat reserve is not a substitute for analyze.

Quota caches org status in Redis (~10 min). After suspend, processing may
keep succeeding until that cache expires. Allowed usage in that window is
still written to `usage_ledger` and billed. Do not promise instant cut-off.

### 4. MedRecs module split

```text
control_jwt.py           JWKS verify only
control_plane/client.py  HTTP (exchange, members/products, quota_*)
ports/control_plane.py   quota_gate.allow / reserve / commit / rollback
domain/*                 no HTTP, no JWT, no action_key strings
```

One `action_key` constants module. Tests mock the **HTTP client**.

### 5. Env (MedRecs)

`CONTROL_PLANE_ENABLED=true` (staging+prod; laptop-only false).
`CONTROL_PLANE_BASE_URL`, `CONTROL_PLANE_JWKS_URL`, `CONTROL_PLANE_JWT_ISSUER`,
`INTERNAL_API_KEY` (backend + workers). Same Firebase project as that CP.

### 6. Implement order

1. JWT verifier; delete `X-Org-Id` (400 if sent).
2. Sidecar session; SPA drops CP URLs.
3. `quota_gate.allow` on OCR / analyze / chat / reports; job row for workers.

**Write before guessing in PRs:** editor origin, cookie vs storage, GCS prefix,
surviving local org, chat token counting, max agentic wall time, staff-in-case.

Full HTTP/reason tables: [control_plane_integration.md](control_plane_integration.md).
