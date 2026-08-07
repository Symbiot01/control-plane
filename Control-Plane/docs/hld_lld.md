# MedRecs ↔ Control Plane — HLD / LLD (devs)

Source of truth: [control_plane_integration.md](control_plane_integration.md).
This is how the services **connect**. Not a green light on production code.

**Planes:** Control Plane (CP) = identity, orgs, entitlements, quota, billing.
MedRecs = cases, files, GCS, OCR, pipeline, chat. CP is a **MedRecs-backend
sidecar**. The SPA talks to MedRecs (+ Firebase Auth) only.

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
       │                    GET {CP}/organizations/{id} ──► PHI lock
       │                    if status != active → 403 GET too
       │
       │  POST .../processing/start | chat
       ├──────────────────► quota_gate.allow(...)
       │                    POST {CP}/internal/v1/quota/* ──► allow/deny
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
| MedRecs | CP `/auth/exchange`, `/members/me`, `/organizations/{id}` | user JWT after exchange | Session + PHI projection |
| MedRecs / workers | CP `/internal/v1/quota/*` | `X-Internal-Api-Key` | Metering. Key never in browser |
| Super admin | CP `/admin/v1` | Control JWT `super_admin` | Plans, entitlements, seed |

**Trust rules:** tenant = JWT `org_id` (no `X-Org-Id`, no `organization_id` in
JSON). Roles = `level_of_access` `owner`\|`member` only. Guest / super_admin
→ 403 on cases. Quota is **metering**, not the PHI lock.

---

## LLD

### 1. Identity

1. SPA: Firebase `getIdToken` → `POST {MEDRECS}/api/auth/exchange`.
2. MedRecs: `POST {CP}/auth/exchange` `{id_token}` → `{access_token, token_type: Bearer, expires_in, has_pending_invites}`.
3. JWT (RS256, `kid: control-plane-1`): `sub` = CP `member_id`, `iss`, `iat`, `exp`, optional `org_id`, `level_of_access`. **No `roles[]`.** Verify via `{CP}/.well-known/jwks.json`. Require `CONTROL_PLANE_JWT_ISSUER`.
4. Upsert local `users` on `control_member_id = sub`. Join by `sub`, not email.
5. `GET {MEDRECS}/api/auth/session` = projection (`GET {CP}/members/me` + products). SPA never calls CP.
6. Refresh: `getIdToken(true)` → MedRecs exchange again. ~30 min TTL. Quota 402/403 ≠ logout.
7. After invite accept, **exchange again** (accept does not mint a new JWT).

Invite GET/accept live on **org console**. MedRecs proxies them **only** if it
hosts an invite page.

### 2. PHI lock (every org-scoped route, including GET)

Middleware, before use cases:

1. Verify JWT. Require `org_id` + `level_of_access` in `{owner, member}`.
2. Resource `org_id` must equal JWT `org_id`. Else 403.
3. Short-TTL cache (~60s) of `GET {CP}/organizations/{id}` (**Postgres**, not
   quota Redis). Require `status == active`. Writes also need entitlement
   `medical` unexpired.
4. If CP is down **and** TTL elapsed → **403/503 on GET too**. Never serve PHI
   because “CP is down.”
5. GCS signed URLs: same lock + path prefixed by JWT `org_id`. Quota does not
   see downloads.

CP Redis `org_status` can lie `active` for 10 minutes after suspend (bug 3b).
Do **not** use quota status for reads.

### 3. Quota (after PHI lock, before expensive work)

Header: `X-Internal-Api-Key`. Body: `organization_id` + `member_id` from
**verified JWT**, copied onto the **job row** at enqueue. Workers read the
row, not task kwargs. `request_id` = UUID v4, reused on retry.

| Job | `action_key` | Call |
|---|---|---|
| OCR | `medical.ocr.page.v1` | `POST /internal/v1/quota/check` `units=pages` |
| Analyze / report / chronology / synthesis | `*.v1` | `check` `units=1` (per run) |
| Chat | `medical.chat.message.v1` | `reserve` → work → `commit`/`rollback`; server `max_units` cap (e.g. 8k) |

HTTP: 401 = bad key; **200** `{allowed, reason}` for business deny; 400
commit/rollback; 5xx/timeout → MedRecs **503**. Map `reason`: suspended /
not entitled → 403; no sub / `insufficient_credits` → 402; `*_limit exceeded`
→ 429. Do not retry `allowed: false`. Quota timeout ≤ 2s. No PHI in CP payloads.

Analyze `check` has **nothing to roll back** if the job later fails (already
billed). Chat holds must finish **&lt; 1h** if the reaper runs.

Until CP patches postpay `NameError`: **prepay test orgs**, or no postpay
`quota/check`. Chat reserve is not a substitute for analyze.

### 4. MedRecs module split

```text
control_jwt.py           JWKS verify only
control_plane/client.py  HTTP (exchange, org GET, quota_*)
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
2. PHI lock on GET + signed URLs.
3. Sidecar session; SPA drops CP URLs.
4. `quota_gate.allow`; wire metering; job row for workers.

**Write before guessing in PRs:** editor origin, cookie vs storage, GCS prefix,
surviving local org, chat token counting, max agentic wall time, staff-in-case.
Do not wait on JWT `org_status` or cookies.

Full HTTP/reason tables: [control_plane_integration.md](control_plane_integration.md).
