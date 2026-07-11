import { apiClient } from '@/lib/api-client';
import type {
  PlanResponse,
  SubscriptionResponse,
  InvoiceResponse,
  InvoiceSummaryResponse,
  CreditBalanceResponse,
  UsageSummaryResponse,
} from '@/types/api';

function usageSummaryQuery(params?: { from?: string; to?: string }) {
  if (!params?.from && !params?.to) return '';
  const sp = new URLSearchParams();
  if (params.from) sp.set('from', params.from);
  if (params.to) sp.set('to', params.to);
  return `?${sp.toString()}`;
}

export const getPlans = () =>
  apiClient<PlanResponse[]>('/plans');

export const getCurrentSubscription = (orgId: string) =>
  apiClient<SubscriptionResponse | null>(`/organizations/${orgId}/subscriptions/current`);

export const getInvoices = (orgId: string) =>
  apiClient<InvoiceSummaryResponse[]>(`/organizations/${orgId}/invoices`);

export const getInvoice = (orgId: string, invoiceId: string) =>
  apiClient<InvoiceResponse>(`/organizations/${orgId}/invoices/${invoiceId}`);

export const getCredits = (orgId: string) =>
  apiClient<CreditBalanceResponse>(`/admin/v1/organizations/${orgId}/credits`);

export const getUsage = (orgId: string) =>
  apiClient<any[]>(`/organizations/${orgId}/usage`);

export const getUsageSummary = (orgId: string, params?: { from?: string; to?: string }) =>
  apiClient<UsageSummaryResponse>(`/organizations/${orgId}/usage/summary${usageSummaryQuery(params)}`);
