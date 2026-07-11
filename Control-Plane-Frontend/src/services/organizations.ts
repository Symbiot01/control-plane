import { apiClient } from '@/lib/api-client';
import type {
  OrganizationWithRole,
  OrganizationResponse,
  OrganizationCreate,
  MemberProfile,
  InviteMemberRequest,
  UpdateMemberRoleRequest,
  AdminOrgMember,
  ProductResponse,
  OrganizationInviteResponse,
} from '@/types/api';

export const getMyOrganizations = () =>
  apiClient<MemberProfile>('/members/me').then((profile) => profile.organization ? [profile.organization] : []);

export const getOrganization = (orgId: string) =>
  apiClient<OrganizationResponse>(`/organizations/${orgId}`);

export const getOrganizationProducts = (orgId: string) =>
  apiClient<ProductResponse[]>(`/organizations/${orgId}/products`);

export const updateOrganization = (orgId: string, data: { name?: string }) =>
  apiClient<OrganizationResponse>(`/organizations/${orgId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });

export const getMembers = (orgId: string) =>
  apiClient<AdminOrgMember[]>(`/organizations/${orgId}/members`);

export const getMyProfile = () =>
  apiClient<MemberProfile>('/members/me');

export const inviteMember = (orgId: string, data: InviteMemberRequest) =>
  apiClient<OrganizationInviteResponse>(
    `/organizations/${orgId}/invite`,
    { method: 'POST', body: JSON.stringify(data) },
  );

export const updateMemberRole = (orgId: string, memberId: string, data: UpdateMemberRoleRequest) =>
  apiClient<{ status: string; member_id: string; role: string }>(
    `/organizations/${orgId}/member/${memberId}`,
    { method: 'PATCH', body: JSON.stringify(data) },
  );

export const removeMember = (orgId: string, memberId: string) =>
  apiClient<{ status: string; member_id: string }>(
    `/organizations/${orgId}/member/${memberId}`,
    { method: 'DELETE' },
  );

export const getAuditLogs = (orgId: string) =>
  apiClient<any[]>(`/organizations/${orgId}/audit-logs`);

export const getInvites = (orgId: string) =>
  apiClient<any[]>(`/organizations/${orgId}/invites`);
