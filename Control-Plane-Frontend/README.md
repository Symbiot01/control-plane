# org-nexus-console

React (Vite) UI for the Control Plane. Configure `VITE_API_BASE_URL` (see `.env`).

## Org console (member JWT)

- **Usage** (`/usage`): calls `GET /organizations/{org_id}/usage/summary` for metered totals from `usage_ledger`. Optional custom UTC date range; default matches API (last 30 days).
- Other routes: overview, quotas, subscription, invoices, credits, members.

## Platform admin

- **User menu → Platform admin** (visible if `GET /admin/v1/stats` succeeds).
- Routes under `/admin/*`: dashboard, organizations (with per-org **Usage (metered)** using `GET /admin/v1/organizations/{id}/usage/summary`), plans, invoices, credits, admins, audit log.

See the control plane [docs/api_endpoints.md](../Control-Plane/docs/api_endpoints.md) for API details.
