import { apiClient } from '@/lib/api-client';
import type { QuotaLimitResponse, QuotaLimitsUpdate } from '@/types/api';

export const getQuotas = (orgId: string) =>
  apiClient<QuotaLimitResponse[]>(`/quotas/${orgId}`);

export const updateQuota = (orgId: string, data: QuotaLimitsUpdate) =>
  apiClient<{ status: string; action_id: string; period: string; limit_value: number }>(
    `/quotas/${orgId}`,
    { method: 'PATCH', body: JSON.stringify(data) },
  );
