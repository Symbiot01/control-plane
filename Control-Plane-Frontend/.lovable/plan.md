

## MedCore Console — Phase 1 Plan

**Data-dense dashboard** frontend connecting to existing API at `http://localhost:8000`. Firebase Auth with token exchange flow.

---

### 1. Foundation & Auth

- **Firebase Auth integration** — sign-in (email/password + Google), sign-out, session persistence
- **Token exchange service** — `POST /auth/exchange` to get Control JWT, auto-refresh on expiry
- **Auth context** — React context providing user state, JWT, loading/error states
- **Protected routes** — redirect unauthenticated users to login
- **API client** — Axios/fetch wrapper with JWT injection, base URL config, error handling

### 2. Layout & Navigation

- **Sidebar navigation** — collapsible, with sections: Overview, Usage, Quotas, Subscription, Invoices, Credits, Members
- **Org switcher** — dropdown in sidebar header showing current org name, role badge, switch between orgs (`GET /organizations/me`)
- **Top bar** — user profile menu, current org/role indicator

### 3. Overview Dashboard

- Current org status, tier, billing mode at a glance
- Key metrics cards: current usage vs quota, active subscription plan, wallet balance, member count
- Quick links to detailed sections

### 4. Organization & Members

- **Org profile page** — name, slug, status, tier, billing mode (`GET /organizations/{org_id}`)
- **Member list** — table with email, role, status, joined date (`GET /members/me` for context)
- **Invite member** — modal with email + role picker (`POST /organizations/{org_id}/invite`)
- **Change role** — inline dropdown or modal (`PATCH .../member/{member_id}`)
- **Remove member** — confirmation dialog with last-owner safety check (`DELETE .../member/{member_id}`)

### 5. Usage & Quotas

- **Usage dashboard** — filterable by product (medsight/medrecs/medvault), action key, date range
- **Usage table** — dense table with action, units, compute_units, timestamps
- **Quota limits view** — table showing action key, period, limit, current usage, remaining (`GET /quotas/{org_id}`)
- **Quota management** (owner/admin) — edit limits per action/period (`PATCH /quotas/{org_id}`)
- **Usage vs limit bars** — progress indicators per quota

### 6. Subscription & Plans

- **Current subscription card** — plan name, price, included units, overage rate, billing cycle dates, status badge (`GET .../subscriptions/current`)
- **Available plans** — plan comparison from `GET /plans`
- **Subscription history** — list of past subscriptions

### 7. Invoices

- **Invoice list** — table with period, total, status badge, date (`GET .../invoices`)
- **Invoice detail** — full breakdown with line items per action, amounts, compute units (`GET .../invoices/{id}`)
- **Status indicators** — color-coded: draft/sent/paid/overdue

### 8. Credits

- **Wallet summary** — balance, billing mode indicator
- **Credit ledger** — table of grant/top_up/consume entries with timestamps
- **Prepay vs postpay** — clear explanation banners based on org billing_mode

### 9. Technical Foundations

- **API service layer** — typed service functions for every endpoint, organized by domain
- **TypeScript types** — full type definitions matching all API schemas
- **React Query** — for data fetching, caching, optimistic updates
- **Data tables** — sortable, filterable tables using shadcn table components
- **Toast notifications** — success/error feedback for all mutations
- **Role-based UI** — conditionally render actions based on user's org role
- **Configurable API base URL** — environment variable for API endpoint

