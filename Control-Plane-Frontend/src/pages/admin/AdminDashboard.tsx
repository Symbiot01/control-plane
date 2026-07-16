import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import {
  getAdminOrganizations,
  getAdminOrganization,
  getAdminOrgMembers,
  getAdminCurrentSubscription,
  getAdminCredits,
  getAdminUsageSummary,
  getAdminInvoices,
  getAdminProducts,
} from '@/services/admin';
import { Skeleton } from '@/components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { UsageSummaryPanel } from '@/components/usage/UsageSummaryPanel';
import { UsageRangeToolbar, type UsageRangeMode } from '@/components/usage/UsageRangeToolbar';
import { customRangeToParams, defaultUsageDateState } from '@/lib/usage-period';

export default function AdminDashboard() {
  const [selectedOrgId, setSelectedOrgId] = useState<string>('');
  const [usageRangeMode, setUsageRangeMode] = useState<UsageRangeMode>('default');
  const usageDefaults = defaultUsageDateState();
  const [usageFromYmd, setUsageFromYmd] = useState(usageDefaults.fromYmd);
  const [usageToYmdInclusive, setUsageToYmdInclusive] = useState(usageDefaults.toYmdInclusive);

  // 1. Fetch Organizations for dropdown
  const { data: orgs, isLoading: orgsLoading } = useQuery({
    queryKey: ['admin', 'organizations'],
    queryFn: () => getAdminOrganizations(),
  });

  // Auto-select first org if none selected
  useEffect(() => {
    if (orgs && orgs.length > 0 && !selectedOrgId) {
      setSelectedOrgId(orgs[0].id);
    }
  }, [orgs, selectedOrgId]);

  // Data for selected org
  const orgId = selectedOrgId;

  const { data: org, isLoading: orgLoading } = useQuery({
    queryKey: ['admin', 'org', orgId],
    queryFn: () => getAdminOrganization(orgId),
    enabled: !!orgId,
  });

  const { data: products } = useQuery({
    queryKey: ['admin', 'products'],
    queryFn: getAdminProducts,
  });

  const { data: members, isLoading: membersLoading } = useQuery({
    queryKey: ['admin', 'org', orgId, 'members'],
    queryFn: () => getAdminOrgMembers(orgId),
    enabled: !!orgId,
  });

  const { data: subscription, isLoading: subLoading } = useQuery({
    queryKey: ['admin', 'org', orgId, 'subscription'],
    queryFn: () => getAdminCurrentSubscription(orgId),
    enabled: !!orgId,
  });

  const { data: credits, isLoading: creditsLoading } = useQuery({
    queryKey: ['admin', 'org', orgId, 'credits'],
    queryFn: () => getAdminCredits(orgId),
    enabled: !!orgId,
  });

  const { data: invoices, isLoading: invoicesLoading } = useQuery({
    queryKey: ['admin', 'org', orgId, 'invoices'],
    queryFn: () => getAdminInvoices(orgId),
    enabled: !!orgId,
  });

  const usageQueryParams =
    usageRangeMode === 'default'
      ? undefined
      : customRangeToParams(usageFromYmd, usageToYmdInclusive);

  const {
    data: usageSummary,
    isLoading: usageLoading,
    isError: usageError,
    error: usageErr,
  } = useQuery({
    queryKey: [
      'admin',
      'usage-summary',
      orgId,
      usageRangeMode,
      usageRangeMode === 'custom' ? `${usageFromYmd}_${usageToYmdInclusive}` : 'default',
    ],
    queryFn: () => getAdminUsageSummary(orgId, usageQueryParams),
    enabled:
      !!orgId &&
      (usageRangeMode === 'default' ||
        (!!usageFromYmd && !!usageToYmdInclusive && new Date(usageFromYmd) < new Date(usageToYmdInclusive))),
    throwOnError: false,
  });

  const isLoading = orgsLoading || (orgId && (orgLoading || membersLoading || subLoading || creditsLoading || invoicesLoading));

  return (
    <div className="max-w-7xl mx-auto space-y-lg pb-10">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          {org ? (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-8 h-8 rounded bg-admin-blue flex items-center justify-center text-admin-blue-foreground shadow-sm">
                  <span className="material-symbols-outlined text-sm">domain</span>
                </div>
                <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Organization</span>
              </div>
              <h1 className="font-headline-lg text-headline-lg md:text-display-lg md:font-display-lg text-foreground leading-none">{org.name}</h1>
              <p className="font-body-md text-body-md text-muted-foreground mt-2">
                Created: {new Date(org.created_at).toLocaleDateString()} | Owner: {members?.find((m: { role: string; email: string }) => m.role === 'owner')?.email || 'Unknown Owner'}
              </p>
            </div>
          ) : (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-8 h-8 rounded bg-admin-blue flex items-center justify-center text-admin-blue-foreground shadow-sm">
                  <span className="material-symbols-outlined text-sm">dashboard</span>
                </div>
                <h1 className="font-headline-lg text-headline-lg md:text-display-lg md:font-display-lg text-foreground">Dashboard</h1>
              </div>
              <p className="font-body-md text-body-md text-muted-foreground mt-1">Super Admin Organization View</p>
            </div>
          )}
        
        {/* Org Selector */}
        <div className="w-full md:w-80">
          <Select value={selectedOrgId} onValueChange={setSelectedOrgId}>
            <SelectTrigger className="w-full bg-card">
              <SelectValue placeholder="Select an organization..." />
            </SelectTrigger>
            <SelectContent>
              {orgs?.map(o => (
                <SelectItem key={o.id} value={o.id}>{o.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {!selectedOrgId ? (
        <div className="flex items-center justify-center h-64 bg-card rounded-lg border border-border text-muted-foreground">
          Please select an organization from the dropdown above to view its dashboard.
        </div>
      ) : isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : org ? (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Finance Card */}
            <Card className="flex flex-col">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-bold text-muted-foreground uppercase tracking-wider">Finance</CardTitle>
              </CardHeader>
              <CardContent className="flex-1 flex flex-col gap-6 justify-center pt-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Plan</p>
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded bg-admin-mint flex items-center justify-center text-admin-mint-foreground shadow-sm">
                        <span className="material-symbols-outlined text-xl">workspace_premium</span>
                      </div>
                      <p className="text-xl font-semibold text-foreground">{subscription?.plan?.name || 'None'}</p>
                    </div>
                  </div>
                  <Badge variant="outline" className="uppercase text-[10px]">{subscription?.status || 'Inactive'}</Badge>
                </div>
                
                <div className="bg-muted/30 p-5 rounded-xl border border-border/50">
                  <div className="text-sm text-muted-foreground mb-3 flex items-center gap-2">
                    <div className="w-8 h-8 rounded bg-admin-palemint flex items-center justify-center text-admin-palemint-foreground shadow-sm">
                      <span className="material-symbols-outlined text-lg">account_balance_wallet</span>
                    </div>
                    Credit Balance
                  </div>
                  <p className="text-5xl font-bold tracking-tight text-foreground">
                    ${((credits?.balance_cents || 0) / 100).toFixed(2)}
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Products (Entitlements) */}
            <Card className="flex flex-col">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-bold text-muted-foreground uppercase tracking-wider">Product</CardTitle>
              </CardHeader>
              <CardContent className="flex-1 flex flex-col pt-2">
                <div className="flex-1 space-y-3">
                  {(org.entitlements || []).length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-sm text-muted-foreground py-8">
                      <span className="material-symbols-outlined text-4xl mb-2 opacity-20">inventory_2</span>
                      No products granted.
                    </div>
                  ) : (
                    (org.entitlements || []).map((ent: { product_key: string; expires_at: string | null }) => {
                      const productName = products?.find((p: { product_key: string; name: string }) => p.product_key === ent.product_key)?.name || ent.product_key;
                      return (
                        <div key={ent.product_key} className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-muted/20 hover:bg-muted/40 transition-colors">
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded bg-admin-paleblue flex items-center justify-center text-admin-paleblue-foreground shadow-sm">
                              <span className="material-symbols-outlined text-sm">deployed_code</span>
                            </div>
                            <div>
                              <p className="font-medium text-sm text-foreground">{productName}</p>
                              {ent.expires_at && (
                                <p className="text-xs text-muted-foreground">Expires {format(new Date(ent.expires_at), 'MMM d, yyyy')}</p>
                              )}
                            </div>
                          </div>
                          {!ent.expires_at && (
                            <Badge variant="secondary" className="text-[10px] bg-admin-sage text-admin-sage-foreground hover:bg-admin-sage/90 border-transparent">Permanent</Badge>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Usage Panel */}
          <div className="space-y-4 pt-4">
            <h2 className="text-xl font-semibold text-foreground">Usage</h2>
            <UsageRangeToolbar
              rangeMode={usageRangeMode}
              setRangeMode={setUsageRangeMode}
              fromYmd={usageFromYmd}
              setFromYmd={setUsageFromYmd}
              toYmdInclusive={usageToYmdInclusive}
              setToYmdInclusive={setUsageToYmdInclusive}
            />
            {usageError && (
              <p className="text-sm text-destructive">
                {usageErr instanceof Error ? usageErr.message : 'Failed to load usage summary'}
              </p>
            )}
            <UsageSummaryPanel data={usageSummary} isLoading={usageLoading} />
          </div>
        </div>
      ) : (
        <div className="text-sm text-muted-foreground">Error loading organization details.</div>
      )}
    </div>
  );
}
