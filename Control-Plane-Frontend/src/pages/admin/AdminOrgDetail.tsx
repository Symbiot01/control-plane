import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { format } from 'date-fns';
import { useQuery } from '@tanstack/react-query';
import {
  getAdminOrganization,
  patchAdminOrganization,
  getAdminOrgMembers,
  getAdminCurrentSubscription,
  getAdminCredits,
  getAdminUsageSummary,
  getAdminProducts,
  grantEntitlement,
  revokeEntitlement,
  getAdminSubscriptions,
  createSubscription,
  updateSubscriptionStatus,
  changePlan,
  getAdminPlans,
  updateMemberRole,
} from '@/services/admin';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { useQueryClient, useMutation } from '@tanstack/react-query';
import { toast } from '@/hooks/use-toast';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft, Trash2, Plus, ChevronDown } from 'lucide-react';
import { Entitlement, EntitlementGrantRequest } from '@/types/api';
import { UsageSummaryPanel } from '@/components/usage/UsageSummaryPanel';
import { UsageRangeToolbar, type UsageRangeMode } from '@/components/usage/UsageRangeToolbar';
import { customRangeToParams, defaultUsageDateState } from '@/lib/usage-period';

export default function AdminOrgDetail() {
  const { orgId } = useParams<{ orgId: string }>();
  const [usageRangeMode, setUsageRangeMode] = useState<UsageRangeMode>('default');
  const usageDefaults = defaultUsageDateState();
  const [usageFromYmd, setUsageFromYmd] = useState(usageDefaults.fromYmd);
  const [usageToYmdInclusive, setUsageToYmdInclusive] = useState(usageDefaults.toYmdInclusive);
  
  const [isGrantOpen, setIsGrantOpen] = useState(false);
  const [newEntitlement, setNewEntitlement] = useState('');
  const [isTemporary, setIsTemporary] = useState(false);
  const [expiresAt, setExpiresAt] = useState('');
  const [maxComputeUnits, setMaxComputeUnits] = useState('');

  const [isEditOrgOpen, setIsEditOrgOpen] = useState(false);
  const [editTier, setEditTier] = useState('');
  const [editBillingMode, setEditBillingMode] = useState('');

  const [isEditLimitsOpen, setIsEditLimitsOpen] = useState(false);
  const [editOverdraft, setEditOverdraft] = useState('');

  const [isManageSubOpen, setIsManageSubOpen] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState('');

  const qc = useQueryClient();

  const { data: org, isLoading } = useQuery({
    queryKey: ['admin', 'org', orgId],
    queryFn: () => getAdminOrganization(orgId!),
    enabled: !!orgId,
  });

  const { data: members } = useQuery({
    queryKey: ['admin', 'org', orgId, 'members'],
    queryFn: () => getAdminOrgMembers(orgId!),
    enabled: !!orgId,
  });

  const { data: subscription } = useQuery({
    queryKey: ['admin', 'org', orgId, 'subscription'],
    queryFn: () => getAdminCurrentSubscription(orgId!),
    enabled: !!orgId,
  });

  const { data: credits } = useQuery({
    queryKey: ['admin', 'org', orgId, 'credits'],
    queryFn: () => getAdminCredits(orgId!),
    enabled: !!orgId,
  });

  const { data: products } = useQuery({
    queryKey: ['admin', 'products'],
    queryFn: getAdminProducts,
  });

  const { data: plans } = useQuery({
    queryKey: ['admin', 'plans'],
    queryFn: getAdminPlans,
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
    queryFn: () => getAdminUsageSummary(orgId!, usageQueryParams),
    enabled:
      !!orgId &&
      (usageRangeMode === 'default' ||
        (!!usageFromYmd &&
          !!usageToYmdInclusive &&
          new Date(usageFromYmd) < new Date(usageToYmdInclusive))),
    throwOnError: false,
  });

  const updateRoleMut = useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: 'owner' | 'member' | 'viewer' }) => 
      updateMemberRole(memberId, role, orgId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'org', orgId, 'members'] });
      toast({ title: 'Role updated successfully' });
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const handleRoleChange = (memberId: string, currentRole: string, newRole: string) => {
    if (newRole !== 'owner' && newRole !== 'member' && newRole !== 'viewer') return;
    if (newRole === currentRole.toLowerCase()) return;
    updateRoleMut.mutate({ memberId, role: newRole as 'owner' | 'member' | 'viewer' });
  };

  const updateOrgMut = useMutation({
    mutationFn: (data: Partial<import('@/types/api').OrganizationResponse>) => patchAdminOrganization(orgId!, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'org', orgId] });
      toast({ title: 'Organization updated' });
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const handleUpdateOrg = (e: React.FormEvent) => {
    e.preventDefault();
    updateOrgMut.mutate({ tier: editTier, billing_mode: editBillingMode as any }, {
      onSuccess: () => setIsEditOrgOpen(false)
    });
  };

  const handleUpdateLimits = (e: React.FormEvent) => {
    e.preventDefault();
    updateOrgMut.mutate({ overdraft_limit_cents: parseInt(editOverdraft, 10) || 0 }, {
      onSuccess: () => setIsEditLimitsOpen(false)
    });
  };

  const createSubMut = useMutation({
    mutationFn: (data: import('@/types/api').SubscriptionCreate) => createSubscription(orgId!, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'org', orgId, 'subscription'] });
      toast({ title: 'Subscription created' });
      setIsManageSubOpen(false);
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const changePlanMut = useMutation({
    mutationFn: ({ subId, data }: { subId: string, data: import('@/types/api').SubscriptionChangePlanRequest }) => changePlan(subId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'org', orgId, 'subscription'] });
      toast({ title: 'Plan changed successfully' });
      setIsManageSubOpen(false);
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const cancelSubMut = useMutation({
    mutationFn: (subId: string) => updateSubscriptionStatus(subId, { status: 'canceled' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'org', orgId, 'subscription'] });
      toast({ title: 'Subscription canceled' });
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const handleManageSub = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPlanId) return;
    const now = new Date();
    const end = new Date(now);
    end.setMonth(end.getMonth() + 1);

    if (subscription) {
      changePlanMut.mutate({
        subId: subscription.id,
        data: { new_plan_id: selectedPlanId, new_billing_cycle_start: now.toISOString(), new_billing_cycle_end: end.toISOString() }
      });
    } else {
      createSubMut.mutate({
        plan_id: selectedPlanId,
        billing_cycle_start: now.toISOString(),
        billing_cycle_end: end.toISOString()
      });
    }
  };

  const grantMut = useMutation({
    mutationFn: (data: EntitlementGrantRequest) => grantEntitlement(orgId!, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'org', orgId] });
      toast({ title: 'Entitlement granted' });
      setNewEntitlement('');
      setIsTemporary(false);
      setExpiresAt('');
      setMaxComputeUnits('');
      setIsGrantOpen(false);
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const revokeMut = useMutation({
    mutationFn: (productKey: string) => revokeEntitlement(orgId!, productKey),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'org', orgId] });
      toast({ title: 'Entitlement revoked' });
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const handleAddEntitlement = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEntitlement || !org) return;
    const current = org.entitlements || [];
    if (current.some((ent: { product_key: string }) => ent.product_key === newEntitlement)) {
      toast({ title: 'Already granted', variant: 'destructive' });
      return;
    }
    
    const payload: EntitlementGrantRequest = { product_key: newEntitlement };
    if (isTemporary) {
      if (expiresAt) payload.expires_at = new Date(expiresAt).toISOString();
      if (maxComputeUnits) payload.max_compute_units = parseInt(maxComputeUnits, 10);
    } else {
      payload.expires_at = null;
      payload.max_compute_units = null;
    }
    grantMut.mutate(payload);
  };

  const handleRemoveEntitlement = (ent: string) => {
    if (!org) return;
    revokeMut.mutate(ent);
  };

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-48" /><Skeleton className="h-40" /><Skeleton className="h-64" /></div>;
  if (!org) return <div className="text-sm text-muted-foreground">Organization not found.</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" className="h-7 w-7" asChild>
          <Link to="/admin/organizations"><ArrowLeft className="h-4 w-4" /></Link>
        </Button>
        <h1 className="text-lg font-semibold">{org.name}</h1>
        <Badge variant={org.status === 'active' ? 'default' : 'destructive'} className="text-[10px]">{org.status}</Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-3 flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm font-medium">Organization Info</CardTitle>
            <Dialog open={isEditOrgOpen} onOpenChange={setIsEditOrgOpen}>
              <DialogTrigger asChild>
                <Button variant="ghost" size="sm" className="h-6 text-xs px-2" onClick={() => { setEditTier(org.tier); setEditBillingMode(org.billing_mode || ''); }}>Edit</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle>Edit Organization</DialogTitle></DialogHeader>
                <form onSubmit={handleUpdateOrg} className="space-y-4 pt-4">
                  <div className="space-y-2">
                    <Label>Tier</Label>
                    <Select value={editTier} onValueChange={setEditTier}>
                      <SelectTrigger><SelectValue placeholder="Select tier" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="free">Free</SelectItem>
                        <SelectItem value="starter">Starter</SelectItem>
                        <SelectItem value="pro">Pro</SelectItem>
                        <SelectItem value="enterprise">Enterprise</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Billing Mode</Label>
                    <Select value={editBillingMode} onValueChange={setEditBillingMode}>
                      <SelectTrigger><SelectValue placeholder="Select mode" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="prepay">Prepay</SelectItem>
                        <SelectItem value="postpay">Postpay</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex justify-end pt-2">
                    <Button type="button" variant="outline" onClick={() => setIsEditOrgOpen(false)} className="mr-2">Cancel</Button>
                    <Button type="submit" disabled={updateOrgMut.isPending}>Save</Button>
                  </div>
                </form>
              </DialogContent>
            </Dialog>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 text-sm">
            <div><p className="text-xs text-muted-foreground">Slug</p><p className="font-mono">{org.slug}</p></div>
            <div><p className="text-xs text-muted-foreground">Tier</p><p>{org.tier}</p></div>
            <div><p className="text-xs text-muted-foreground">Billing Mode</p><p>{org.billing_mode || '—'}</p></div>
            <div><p className="text-xs text-muted-foreground">Created</p><p>{new Date(org.created_at).toLocaleDateString()}</p></div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3 flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm font-medium">Subscription & Credits</CardTitle>
            <div className="flex items-center gap-1">
              <Dialog open={isManageSubOpen} onOpenChange={setIsManageSubOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" size="sm" className="h-6 text-[10px] px-2" onClick={() => setSelectedPlanId(subscription?.plan_id || '')}>
                    {subscription ? 'Change Plan' : 'Subscribe'}
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader><DialogTitle>{subscription ? 'Change Plan' : 'Subscribe to Plan'}</DialogTitle></DialogHeader>
                  <form onSubmit={handleManageSub} className="space-y-4 pt-4">
                    <div className="space-y-2">
                      <Label>Select Plan</Label>
                      <Select value={selectedPlanId} onValueChange={setSelectedPlanId}>
                        <SelectTrigger><SelectValue placeholder="Choose a plan..." /></SelectTrigger>
                        <SelectContent>
                          {plans?.map(p => (
                            <SelectItem key={p.id} value={p.id}>{p.name} - ${(p.monthly_price / 100).toFixed(2)}/mo</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex justify-between items-center pt-2">
                      {subscription && subscription.status !== 'canceled' ? (
                        <Button type="button" variant="destructive" size="sm" onClick={() => { if (confirm('Cancel subscription?')) cancelSubMut.mutate(subscription.id); }} disabled={cancelSubMut.isPending}>
                          Cancel Subscription
                        </Button>
                      ) : <div />}
                      <div className="flex gap-2">
                        <Button type="button" variant="outline" onClick={() => setIsManageSubOpen(false)}>Close</Button>
                        <Button type="submit" disabled={!selectedPlanId || createSubMut.isPending || changePlanMut.isPending}>
                          {subscription ? 'Update Plan' : 'Subscribe'}
                        </Button>
                      </div>
                    </div>
                  </form>
                </DialogContent>
              </Dialog>
              <Dialog open={isEditLimitsOpen} onOpenChange={setIsEditLimitsOpen}>
                <DialogTrigger asChild>
                  <Button variant="ghost" size="sm" className="h-6 text-xs px-2" onClick={() => setEditOverdraft((org.overdraft_limit_cents || 0).toString())}>Edit Limits</Button>
                </DialogTrigger>
                <DialogContent>
                <DialogHeader><DialogTitle>Edit Credit Limits</DialogTitle></DialogHeader>
                <form onSubmit={handleUpdateLimits} className="space-y-4 pt-4">
                  <div className="space-y-2">
                    <Label>Overdraft Limit (cents)</Label>
                    <Input type="number" value={editOverdraft} onChange={(e) => setEditOverdraft(e.target.value)} required />
                    <p className="text-[10px] text-muted-foreground">The amount of negative balance allowed before services are cut off.</p>
                  </div>
                  <div className="flex justify-end pt-2">
                    <Button type="button" variant="outline" onClick={() => setIsEditLimitsOpen(false)} className="mr-2">Cancel</Button>
                    <Button type="submit" disabled={updateOrgMut.isPending}>Save</Button>
                  </div>
                </form>
              </DialogContent>
            </Dialog>
            </div>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 text-sm">
            <div><p className="text-xs text-muted-foreground">Plan</p><p>{subscription?.plan?.name || 'None'}</p></div>
            <div><p className="text-xs text-muted-foreground">Status</p><p>{subscription?.status || '—'}</p></div>
            <div><p className="text-xs text-muted-foreground">Credit Balance</p><p>${((credits?.balance_cents || 0) / 100).toFixed(2)}</p></div>
            <div><p className="text-xs text-muted-foreground">Overdraft Limit</p><p>${((credits?.overdraft_limit_cents || 0) / 100).toFixed(2)}</p></div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <div className="flex items-center justify-between pr-6">
          <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">Product Entitlements (Access)</CardTitle></CardHeader>
          <Dialog open={isGrantOpen} onOpenChange={setIsGrantOpen}>
            <DialogTrigger asChild>
              <Button size="sm"><Plus className="mr-2 h-4 w-4" /> Add Entitlement</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Grant Entitlement</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleAddEntitlement} className="space-y-4 pt-4">
                <div className="space-y-2">
                  <Label>Product</Label>
                  <Select value={newEntitlement} onValueChange={setNewEntitlement}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a product" />
                    </SelectTrigger>
                    <SelectContent>
                      {products?.map(p => (
                        <SelectItem key={p.product_key} value={p.product_key}>{p.name} ({p.product_key})</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center gap-2 pt-2 pb-2">
                  <Switch id="temporary" checked={isTemporary} onCheckedChange={setIsTemporary} />
                  <Label htmlFor="temporary">Temporary Access</Label>
                </div>
                {isTemporary && (
                  <div className="space-y-4 border-l-2 pl-4 border-muted">
                    <div className="space-y-2">
                      <Label htmlFor="expiresAt">Expires At</Label>
                      <Input type="datetime-local" id="expiresAt" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="maxCompute">Max Compute Units</Label>
                      <Input type="number" id="maxCompute" placeholder="Unlimited if left empty" value={maxComputeUnits} onChange={(e) => setMaxComputeUnits(e.target.value)} />
                    </div>
                  </div>
                )}
                <div className="flex justify-end gap-2 pt-2">
                  <Button type="button" variant="outline" onClick={() => setIsGrantOpen(false)}>Cancel</Button>
                  <Button type="submit" disabled={!newEntitlement || grantMut.isPending}>Grant</Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </div>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">Product Key</TableHead>
                <TableHead className="text-xs">Expires At</TableHead>
                <TableHead className="text-xs">Max Compute</TableHead>
                <TableHead className="text-xs w-16">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(org.entitlements || []).length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-xs text-muted-foreground py-6">
                    No entitlements granted.
                  </TableCell>
                </TableRow>
              ) : (
                (org.entitlements || []).map((ent: Entitlement) => (
                  <TableRow key={ent.product_key}>
                    <TableCell className="font-mono text-xs">{ent.product_key}</TableCell>
                    <TableCell className="text-xs">
                      {ent.expires_at ? format(new Date(ent.expires_at), 'MMM d, yyyy, h:mm a') : <Badge variant="secondary" className="text-[10px]">Permanent</Badge>}
                    </TableCell>
                    <TableCell className="text-xs">
                      {ent.max_compute_units !== null && ent.max_compute_units !== undefined ? ent.max_compute_units : 'Unlimited'}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-destructive hover:bg-destructive/10"
                        onClick={() => {
                          if (confirm('Are you sure you want to revoke this entitlement?')) {
                            handleRemoveEntitlement(ent.product_key);
                          }
                        }}
                        disabled={revokeMut.isPending}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="space-y-3">
        <h2 className="text-sm font-medium">Usage (metered)</h2>
        <p className="text-xs text-muted-foreground">
          Aggregated from <code className="text-[10px]">usage_ledger</code> for{' '}
          <span className="font-medium">[period_start, period_end)</span>.
        </p>
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

      <Card>
        <CardHeader className="pb-3"><CardTitle className="text-sm font-medium">Members ({members?.length || 0})</CardTitle></CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">Email</TableHead>
                <TableHead className="text-xs">Name</TableHead>
                <TableHead className="text-xs">Role</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members?.map((m) => (
                <TableRow key={m.member_id}>
                  <TableCell className="text-xs">{m.email}</TableCell>
                  <TableCell className="text-xs">{m.display_name || '—'}</TableCell>
                  <TableCell>
                    {m.role?.toLowerCase() === 'owner' || m.role?.toLowerCase() === 'member' || m.role?.toLowerCase() === 'viewer' ? (
                      <div className="flex items-center">
                        <select
                          className="h-8 w-32 rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring capitalize cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                          value={m.role.toLowerCase()}
                          onChange={(e) => handleRoleChange(m.member_id, m.role, e.target.value)}
                          disabled={updateRoleMut.isPending}
                        >
                          <option value="owner">Owner</option>
                          <option value="member">Member</option>
                          <option value="viewer">Viewer</option>
                        </select>
                      </div>
                    ) : (
                      <Badge variant="outline" className="text-[10px] uppercase font-label-caps">{m.role}</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
