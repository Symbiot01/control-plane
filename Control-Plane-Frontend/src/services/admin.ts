import { apiClient } from '@/lib/api-client';
import type {
  AdminStats,
  OrganizationResponse,
  AdminOrgMember,
  SubscriptionResponse,
  SubscriptionCreate,
  SubscriptionStatusUpdate,
  SubscriptionChangePlanRequest,
  InvoiceResponse,
  InvoiceGenerateRequest,
  InvoiceStatusUpdate,
  InvoicePaymentUpdate,
  CreditBalanceResponse,
  CreditLedgerEntry,
  CreditGrantRequest,
  PlanResponse,
  AuditLogEntry,
  UsageSummaryResponse,
} from '@/types/api';

const A = '/admin/v1';

function usageSummaryQuery(params?: { from?: string; to?: string }) {
  if (!params?.from && !params?.to) return '';
  const sp = new URLSearchParams();
  if (params.from) sp.set('from', params.from);
  if (params.to) sp.set('to', params.to);
  return `?${sp.toString()}`;
}

export const getAdminStats = () => apiClient<AdminStats>(`${A}/stats`);

// Organizations
export const getAdminOrganizations = (params?: { search?: string; status?: string; page?: string }) => {
  const cleanParams = Object.fromEntries(Object.entries(params || {}).filter(([_, v]) => !!v));
  const qs = Object.keys(cleanParams).length > 0 ? '?' + new URLSearchParams(cleanParams).toString() : '';
  return apiClient<OrganizationResponse[]>(`${A}/organizations${qs}`);
};
export const adminCreateOrganization = (data: { name: string; slug?: string; owner_email: string }) =>
  apiClient<OrganizationResponse>(`${A}/organizations`, { method: 'POST', body: JSON.stringify(data) });
export const createAdminInvite = (data: import('@/types/api').InviteOrgRequest) =>
  apiClient<import('@/types/api').InviteOrgResponse>(`${A}/invites`, { method: 'POST', body: JSON.stringify(data) });
export const getAdminOrganization = (id: string) => apiClient<OrganizationResponse>(`${A}/organizations/${id}`);
export const patchAdminOrganization = (id: string, data: Partial<OrganizationResponse>) =>
  apiClient<OrganizationResponse>(`${A}/organizations/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
export const suspendOrganization = (id: string) =>
  apiClient(`${A}/organizations/${id}/suspend`, { method: 'PATCH' });
export const activateOrganization = (id: string) =>
  apiClient(`${A}/organizations/${id}/activate`, { method: 'PATCH' });
export const scrubOrganization = (id: string) =>
  apiClient(`${A}/organizations/${id}/scrub`, { method: 'DELETE' });
export const hardDeleteOrganization = (id: string) =>
  apiClient(`${A}/organizations/${id}/hard`, { method: 'DELETE' });
export const getAdminOrgMembers = (orgId: string) =>
  apiClient<AdminOrgMember[]>(`${A}/organizations/${orgId}/members`);

export const getAdminUsageSummary = (orgId: string, params?: { from?: string; to?: string }) =>
  apiClient<UsageSummaryResponse>(`${A}/organizations/${orgId}/usage/summary${usageSummaryQuery(params)}`);

// Subscriptions
export const getAdminSubscriptions = (orgId: string) =>
  apiClient<SubscriptionResponse[]>(`${A}/organizations/${orgId}/subscriptions`);
export const getAdminCurrentSubscription = (orgId: string) =>
  apiClient<SubscriptionResponse | null>(`${A}/organizations/${orgId}/subscriptions/current`);
export const createSubscription = (orgId: string, data: SubscriptionCreate) =>
  apiClient<SubscriptionResponse>(`${A}/organizations/${orgId}/subscriptions`, { method: 'POST', body: JSON.stringify(data) });
export const updateSubscriptionStatus = (subId: string, data: SubscriptionStatusUpdate) =>
  apiClient<SubscriptionResponse>(`${A}/subscriptions/${subId}/status`, { method: 'PATCH', body: JSON.stringify(data) });
export const changePlan = (subId: string, data: SubscriptionChangePlanRequest) =>
  apiClient<SubscriptionResponse>(`${A}/subscriptions/${subId}/change-plan`, { method: 'POST', body: JSON.stringify(data) });

// Invoices
export const getAdminInvoices = (orgId: string) =>
  apiClient<InvoiceResponse[]>(`${A}/organizations/${orgId}/invoices`);
export const getAdminInvoice = (invoiceId: string) =>
  apiClient<InvoiceResponse>(`${A}/invoices/${invoiceId}`);
export const generateInvoice = (orgId: string, data: InvoiceGenerateRequest) =>
  apiClient<{ invoice_id: string }>(`${A}/organizations/${orgId}/invoices/generate`, { method: 'POST', body: JSON.stringify(data) });
export const updateInvoiceStatus = (invoiceId: string, data: InvoiceStatusUpdate) =>
  apiClient<{ invoice_id: string; status: string }>(`${A}/invoices/${invoiceId}/status`, { method: 'PATCH', body: JSON.stringify(data) });
export const updateInvoicePayment = (invoiceId: string, data: InvoicePaymentUpdate) =>
  apiClient<{ invoice_id: string }>(`${A}/invoices/${invoiceId}/payment`, { method: 'PATCH', body: JSON.stringify(data) });

// Credits
export const getAdminCredits = (orgId: string) =>
  apiClient<CreditBalanceResponse>(`${A}/organizations/${orgId}/credits`);
export const grantCredits = (orgId: string, data: CreditGrantRequest) =>
  apiClient<{ organization_id: string; amount_cents: number }>(`${A}/organizations/${orgId}/credits/grant`, { method: 'POST', body: JSON.stringify(data) });
export const getCreditLedger = (orgId: string) =>
  apiClient<CreditLedgerEntry[]>(`${A}/organizations/${orgId}/credits/ledger`);

// Plans
export const getAdminPlans = () => apiClient<PlanResponse[]>(`${A}/plans`);
export const createPlan = (data: Partial<PlanResponse>) =>
  apiClient<PlanResponse>(`${A}/plans`, { method: 'POST', body: JSON.stringify(data) });
export const updatePlan = (planId: string, data: Partial<PlanResponse>) =>
  apiClient<PlanResponse>(`${A}/plans/${planId}`, { method: 'PATCH', body: JSON.stringify(data) });

// Admins
export const getAdmins = () =>
  apiClient<{ member_id: string; email: string; display_name: string | null; created_at: string }[]>(`${A}/admins`);
export const addAdmin = (email: string) =>
  apiClient(`${A}/admins`, { method: 'POST', body: JSON.stringify({ email }) });
export const removeAdmin = (adminId: string) =>
  apiClient(`${A}/admins/${adminId}`, { method: 'DELETE' });

// Global Members
export const getAdminMembers = () => apiClient<import('@/types/api').AdminMemberResponse[]>(`${A}/members`);
export const updateMemberRole = (memberId: string, role: 'owner' | 'member' | 'viewer', organization_id?: string) => 
  apiClient(`${A}/members/${memberId}/role`, { method: 'PATCH', body: JSON.stringify({ role, ...(organization_id ? { organization_id } : {}) }) });
export const deleteAdminMember = (memberId: string) => apiClient(`${A}/members/${memberId}`, { method: 'DELETE' });

// Audit
export const getAuditLog = (params?: Record<string, string>) => {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return apiClient<AuditLogEntry[]>(`${A}/audit-log${qs}`);
};

// Products & Entitlements
export const getAdminProducts = () => apiClient<import('@/types/api').ProductResponse[]>(`${A}/products`);
export const createAdminProduct = (data: import('@/types/api').ProductCreate) =>
  apiClient<import('@/types/api').ProductResponse>(`${A}/products`, { method: 'POST', body: JSON.stringify(data) });
export const updateAdminProduct = (productId: string, data: import('@/types/api').ProductUpdate) =>
  apiClient<import('@/types/api').ProductResponse>(`${A}/products/${productId}`, { method: 'PATCH', body: JSON.stringify(data) });
export const deleteAdminProduct = (productId: string) =>
  apiClient(`${A}/products/${productId}`, { method: 'DELETE' });
export const grantEntitlement = (orgId: string, data: import('@/types/api').EntitlementGrantRequest) =>
  apiClient(`${A}/organizations/${orgId}/entitlements`, { method: 'POST', body: JSON.stringify(data) });
export const revokeEntitlement = (orgId: string, productKey: string) =>
  apiClient(`${A}/organizations/${orgId}/entitlements/${productKey}`, { method: 'DELETE' });

// Actions (Services)
export const getAdminActions = () => apiClient<import('@/types/api').ActionResponse[]>(`${A}/actions`);
export const createAdminAction = (data: import('@/types/api').ActionCreate) =>
  apiClient<import('@/types/api').ActionResponse>(`${A}/actions`, { method: 'POST', body: JSON.stringify(data) });
export const updateAdminAction = (actionKey: string, data: import('@/types/api').ActionUpdate) =>
  apiClient<import('@/types/api').ActionResponse>(`${A}/actions/${actionKey}`, { method: 'PATCH', body: JSON.stringify(data) });
export const deleteAdminAction = (actionKey: string) =>
  apiClient(`${A}/actions/${actionKey}`, { method: 'DELETE' });
