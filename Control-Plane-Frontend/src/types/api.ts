export type OrgRole = 'owner' | 'admin' | 'member' | 'viewer';
export type OrgStatus = 'active' | 'suspended' | 'pending';
export type OrgTier = 'free' | 'starter' | 'pro' | 'enterprise';
export type BillingMode = 'postpay' | 'prepay';
export type QuotaPeriod = 'per_minute' | 'per_hour' | 'per_day' | 'per_month' | 'lifetime';
export type SubscriptionStatus = 'active' | 'canceled' | 'past_due' | 'trialing';
export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'overdue' | 'void';
export type CreditType = 'grant' | 'top_up' | 'consume';

export interface OrganizationWithRole {
  id: string;
  name: string;
  slug: string;
  status: string;
  tier: string;
  created_at: string;
  updated_at: string;
  role: OrgRole;
}

export interface MemberProfile {
  id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
  created_at: string;
  organization: OrganizationWithRole | null;
  entitlements?: Entitlement[];
}

export interface Entitlement {
  product_key: string;
  product_name?: string | null;
  product_link?: string | null;
  is_active?: boolean | null;
  expires_at: string | null;
  max_compute_units: number | null;
  created_at: string;
}

export interface OrganizationResponse {
  id: string;
  name: string;
  slug: string;
  status: string;
  tier: string;
  billing_mode?: BillingMode;
  wallet_balance_cents?: number;
  overdraft_limit_cents?: number;
  entitlements: Entitlement[];
  created_at: string;
  updated_at: string;
}

export interface QuotaLimitResponse {
  id: string;
  organization_id: string;
  action_id: string;
  action_key: string | null;
  limit_value: number;
  period: QuotaPeriod;
  current_usage?: number;
  created_at: string;
}

export interface PlanResponse {
  id: string;
  name: string;
  monthly_price: number;
  included_compute_units: number;
  overage_rate: number;
  currency: string;
  created_at: string;
}

export interface SubscriptionResponse {
  id: string;
  organization_id: string;
  plan_id: string;
  status: SubscriptionStatus;
  billing_cycle_start: string;
  billing_cycle_end: string;
  created_at: string;
  plan?: PlanResponse;
}

export interface InvoiceLineItem {
  id: string;
  invoice_id: string;
  action_id: string;
  units: number;
  compute_units: number;
  amount: number;
}

export interface InvoiceResponse {
  id: string;
  organization_id: string;
  billing_period_start: string;
  billing_period_end: string;
  total_compute_units: number;
  included_units: number;
  overage_units: number;
  amount_due: number;
  amount_paid?: number;
  credits_applied?: number;
  status: InvoiceStatus;
  external_id: string | null;
  created_at: string;
  line_items: InvoiceLineItem[] | null;
}

export type InvoiceSummaryResponse = Omit<InvoiceResponse, 'line_items'>;

export interface UsageActionBreakdown {
  action_id: string | null;
  action_key: string | null;
  units: number;
  compute_units: number;
}

export interface UsageSummaryResponse {
  organization_id: string;
  period_start: string;
  period_end: string;
  total_compute_units: number;
  total_units: number;
  by_action: UsageActionBreakdown[];
}

export interface CreditLedgerEntry {
  id: string;
  amount_cents: number;
  type: CreditType;
  reference_id: string | null;
  created_at: string;
}

export interface CreditBalanceResponse {
  balance_cents: number;
  billing_mode: BillingMode;
  overdraft_limit_cents: number;
  recent_ledger: CreditLedgerEntry[];
}

export interface AuthExchangeResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  has_pending_invites?: boolean;
}

export interface AdminStats {
  total_orgs: number;
  active_orgs: number;
  suspended_orgs: number;
  archived_orgs: number;
  active_subscriptions: number;
  draft_invoices: number;
  overdue_invoices: number;
  total_members: number;
}

export interface AdminOrgMember {
  member_id: string;
  email: string;
  display_name: string | null;
  role: OrgRole;
  is_active?: boolean;
  created_at?: string;
}

export type GlobalRole = 'super_admin' | 'owner' | 'member' | 'viewer' | 'guest';

export interface AdminMemberResponse {
  member_id: string;
  email: string;
  display_name: string | null;
  organization_id: string | null;
  global_role: GlobalRole;
}

export interface AuditLogEntry {
  id: string;
  admin_member_id: string;
  actor_email?: string;
  action: string;
  target_type: string;
  target_id: string | null;
  detail?: string | null;
  created_at: string;
}

// Request types
export interface OrganizationCreate {
  name: string;
  slug?: string;
}

export interface InviteOrgRequest {
  email: string;
  organization_id: string | null;
  plan_id: string | null;
  role: string;
  expiration_hours: number;
}

export interface InviteOrgResponse {
  id: string;
  email: string;
  status: string;
  invite_url: string;
}

export interface InviteMemberRequest {
  email: string;
  role: OrgRole;
  expiration_hours?: number;
}

export interface OrganizationInviteResponse {
  id: string;
  email: string;
  organization_id: string | null;
  plan_id: string | null;
  role: string;
  status: string;
  invited_by: string | null;
  expires_at: string;
  created_at: string;
  invite_url: string;
  account_exists: boolean;
}

export interface UpdateMemberRoleRequest {
  role: OrgRole;
}

export interface QuotaLimitsUpdate {
  action_id: string;
  period: QuotaPeriod;
  limit_value: number;
}

export interface SubscriptionCreate {
  plan_id: string;
  billing_cycle_start: string;
  billing_cycle_end: string;
}

export interface SubscriptionChangePlanRequest {
  new_plan_id: string;
  new_billing_cycle_start: string;
  new_billing_cycle_end: string;
}

export interface InvoiceGenerateRequest {
  billing_period_end: string;
}

export interface InvoiceStatusUpdate {
  status: InvoiceStatus;
}

export interface InvoicePaymentUpdate {
  amount_paid_cents?: number;
  credits_applied_cents?: number;
}

export interface CreditGrantRequest {
  amount_cents: number;
  type: string;
  reference_id?: string | null;
}

export interface SubscriptionStatusUpdate {
  status: SubscriptionStatus;
}

export interface ProductResponse {
  id: string;
  name: string;
  product_key: string;
  description?: string;
  product_link?: string | null;
  is_active?: boolean;
  expires_at?: string | null;
  max_compute_units?: number | null;
  created_at: string;
}

export interface ProductCreate {
  name: string;
  product_key: string;
  description?: string;
  product_link?: string | null;
}

export interface ProductUpdate {
  name?: string;
  description?: string | null;
  product_link?: string | null;
  is_active?: boolean;
}

export interface EntitlementGrantRequest {
  product_key: string;
  expires_at?: string | null;
  max_compute_units?: number | null;
}

export interface ActionResponse {
  id: string;
  name: string;
  action_key: string;
  product_id: string;
  domain?: string;
  unit_type?: string;
  description?: string;
  rate_cents_per_compute_unit?: number;
  is_active: boolean;
  created_at: string;
}

export interface ActionCreate {
  name: string;
  action_key: string;
  product_id: string;
  domain: string;
  unit_type: string;
}

export interface ActionUpdate {
  name?: string;
  action_key?: string;
  domain?: string;
  description?: string;
  is_active?: boolean;
  rate_cents_per_compute_unit?: number;
}

export interface InviteDetailResponse {
  id: string;
  email: string;
  organization_name?: string;
  role: string;
  status: string;
  account_exists?: boolean;
}

export interface PendingInviteResponse {
  id: string;
  email: string;
  role: string;
  status: string;
  created_at: string;
  organization_id?: string | null;
}

export interface AcceptInviteRequest {
  organization_name: string;
}
