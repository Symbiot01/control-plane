import { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getAdminOrganizations, 
  adminCreateOrganization,
  getAdminProducts,
  grantEntitlement,
  revokeEntitlement,
  suspendOrganization,
  activateOrganization,
  createAdminInvite,
  getAdminPlans,
  scrubOrganization,
  hardDeleteOrganization,
  getAdminPendingInvites,
  revokeAdminInvite
} from '@/services/admin';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from '@/hooks/use-toast';
import { Link } from 'react-router-dom';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Search, X, Trash2, Copy, Check } from 'lucide-react';
import type { EntitlementGrantRequest, InviteOrgRequest, PlanResponse } from '@/types/api';

function DeleteOrgDialog({ org, onDeleted }: { org: { id: string; name: string; status?: string }, onDeleted: () => void }) {
  const [open, setOpen] = useState(false);
  const [deleteMode, setDeleteMode] = useState<'scrub' | 'hard'>('scrub');
  const [hardDeleteStep, setHardDeleteStep] = useState<1 | 2>(1);
  const [confirmName, setConfirmName] = useState('');
  const [confirmHard, setConfirmHard] = useState('');
  
  const [isPressing, setIsPressing] = useState(false);
  const pressTimeout = useRef<NodeJS.Timeout | null>(null);

  const scrubMut = useMutation({
    mutationFn: () => scrubOrganization(org.id),
    onSuccess: () => {
      toast({ title: 'Organization deleted' });
      setOpen(false);
      onDeleted();
    },
    onError: (err: Error) => toast({ title: 'Error deleting organization', description: err.message, variant: 'destructive' })
  });

  const hardMut = useMutation({
    mutationFn: () => hardDeleteOrganization(org.id),
    onSuccess: () => {
      toast({ title: 'Organization hard deleted' });
      setOpen(false);
      onDeleted();
    },
    onError: (err: Error) => toast({ title: 'Error hard deleting organization', description: err.message, variant: 'destructive' })
  });

  const handlePressStart = () => {
    setIsPressing(true);
    pressTimeout.current = setTimeout(() => {
      setDeleteMode('hard');
      const isScrubbed = org.status === 'scrubbed' || org.status === 'deleted' || org.name.toLowerCase().includes('deleted');
      setHardDeleteStep(isScrubbed ? 2 : 1);
      setOpen(true);
      setIsPressing(false);
    }, 800);
  };

  const handlePressEnd = () => {
    if (pressTimeout.current) {
      clearTimeout(pressTimeout.current);
      pressTimeout.current = null;
    }
    if (isPressing) {
      // It was a short click
      setIsPressing(false);
      setDeleteMode('scrub');
      setOpen(true);
    }
  };

  const handleOpenChange = (val: boolean) => {
    setOpen(val);
    if (!val) {
      setConfirmName('');
      setConfirmHard('');
      setHardDeleteStep(1);
    }
  };

  return (
    <>
      <style>{`
        @keyframes custom-shake {
          0% { transform: translateX(0); }
          25% { transform: translateX(-2px) rotate(-5deg); }
          50% { transform: translateX(2px) rotate(5deg); }
          75% { transform: translateX(-2px) rotate(-5deg); }
          100% { transform: translateX(0); }
        }
        .animate-custom-shake {
          animation: custom-shake 0.2s infinite;
        }
      `}</style>
      <Button 
        variant="ghost" 
        size="sm" 
        className={`h-7 w-7 p-0 text-destructive hover:text-destructive hover:bg-destructive/10 ${isPressing ? 'animate-custom-shake bg-destructive/10' : ''}`}
        title="Delete Organization"
        onMouseDown={handlePressStart}
        onMouseUp={handlePressEnd}
        onMouseLeave={handlePressEnd}
        onTouchStart={handlePressStart}
        onTouchEnd={handlePressEnd}
      >
        <Trash2 className="h-4 w-4" />
      </Button>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {deleteMode === 'hard' 
                ? (hardDeleteStep === 1 ? 'Delete Organization' : 'HARD DELETE Organization')
                : 'Delete Organization'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            {deleteMode === 'hard' ? (
              hardDeleteStep === 1 ? (
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    Are you sure you want to delete <strong className="text-foreground">{org.name}</strong>?
                  </p>
                  <div className="space-y-2">
                    <Label>Type the organization name to confirm:</Label>
                    <Input 
                      value={confirmName} 
                      onChange={e => setConfirmName(e.target.value)} 
                      placeholder={org.name}
                    />
                  </div>
                  <div className="flex justify-end pt-2 gap-2">
                    <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                    <Button 
                      variant="destructive" 
                      disabled={confirmName !== org.name}
                      onClick={() => setHardDeleteStep(2)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="bg-destructive/10 text-destructive p-3 rounded-md text-sm font-medium border border-destructive/20">
                    This will permanently destroy all financial records, invoices, and ledgers for this organization.
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Type "confirm" below to execute the hard delete.
                  </p>
                  <div className="space-y-2">
                    <Label>Confirm destruction:</Label>
                    <Input 
                      value={confirmHard} 
                      onChange={e => setConfirmHard(e.target.value)} 
                      placeholder="confirm"
                    />
                  </div>
                  <div className="flex justify-end pt-2 gap-2">
                    <Button variant="outline" onClick={() => setHardDeleteStep(1)}>Back</Button>
                    <Button 
                      variant="destructive" 
                      disabled={confirmHard !== 'confirm' || hardMut.isPending}
                      onClick={() => hardMut.mutate()}
                    >
                      {hardMut.isPending ? 'Deleting...' : 'Hard Delete Org'}
                    </Button>
                  </div>
                </div>
              )
            ) : (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  Are you sure you want to delete <strong className="text-foreground">{org.name}</strong>? 
                </p>
                <div className="space-y-2">
                  <Label>Type the organization name to confirm:</Label>
                  <Input 
                    value={confirmName} 
                    onChange={e => setConfirmName(e.target.value)} 
                    placeholder={org.name}
                  />
                </div>
                <div className="flex justify-end pt-2 gap-2">
                  <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                  <Button 
                    variant="destructive" 
                    disabled={confirmName !== org.name || scrubMut.isPending}
                    onClick={() => scrubMut.mutate()}
                  >
                    {scrubMut.isPending ? 'Deleting...' : 'Delete Org'}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function AddProductDialog({ orgId, onGranted }: { orgId: string, onGranted: () => void }) {
  const [open, setOpen] = useState(false);
  const [productKey, setProductKey] = useState('');
  const [isTemporary, setIsTemporary] = useState(false);
  const [expiresAt, setExpiresAt] = useState('');
  
  const { data: products } = useQuery({ queryKey: ['admin', 'products'], queryFn: getAdminProducts });
  
  const grantMut = useMutation({
    mutationFn: (data: EntitlementGrantRequest) => grantEntitlement(orgId, data),
    onSuccess: () => { 
      toast({ title: 'Product granted successfully' }); 
      setOpen(false); 
      setProductKey('');
      setIsTemporary(false);
      setExpiresAt('');
      onGranted();
    },
    onError: (err: Error) => toast({ title: 'Error granting product', description: err.message, variant: 'destructive' })
  });

  const handleGrant = () => {
    if (!productKey) return;
    const payload: EntitlementGrantRequest = { product_key: productKey };
    if (isTemporary && expiresAt) {
      payload.expires_at = new Date(expiresAt).toISOString();
    } else {
      payload.expires_at = null;
    }
    grantMut.mutate(payload);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="h-7 text-xs">Add Product</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Grant Product Entitlement</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <Select value={productKey} onValueChange={setProductKey}>
            <SelectTrigger><SelectValue placeholder="Select a product" /></SelectTrigger>
            <SelectContent>
              {products?.map((p: { product_key: string; name: string }) => (
                <SelectItem key={p.product_key} value={p.product_key}>{p.name} ({p.product_key})</SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          <div className="flex items-center gap-2 pt-2 pb-2">
            <Switch id={`temporary-${orgId}`} checked={isTemporary} onCheckedChange={setIsTemporary} />
            <Label htmlFor={`temporary-${orgId}`}>Temporary Access</Label>
          </div>
          
          {isTemporary && (
            <div className="space-y-2 border-l-2 pl-4 border-muted">
              <Label htmlFor={`expiresAt-${orgId}`}>Expires At</Label>
              <Input 
                type="date" 
                id={`expiresAt-${orgId}`} 
                value={expiresAt} 
                onChange={(e) => setExpiresAt(e.target.value)} 
              />
              <p className="text-[10px] text-muted-foreground">Access will be revoked at midnight on this date.</p>
            </div>
          )}

          <div className="flex justify-end pt-2">
            <Button onClick={handleGrant} disabled={!productKey || grantMut.isPending || (isTemporary && !expiresAt)}>
              {grantMut.isPending ? 'Granting...' : 'Grant Product'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function InviteOrgDialog() {
  const [open, setOpen] = useState(false);
  const [formData, setFormData] = useState<{ name: string; email: string; plan_id: string; expiration_hours: number; initial_credits: number }>({
    name: '',
    email: '',
    plan_id: '',
    expiration_hours: 72,
    initial_credits: 150
  });
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: plans } = useQuery({ queryKey: ['admin', 'plans'], queryFn: getAdminPlans });

  const inviteMut = useMutation({
    mutationFn: (data: InviteOrgRequest) => createAdminInvite(data),
    onSuccess: (data) => {
      setInviteUrl(data.invite_url);
      if (data.email_sent === true) {
        toast({ title: 'Success', description: 'Invite email sent successfully!' });
      } else if (data.email_sent === false) {
        toast({ title: 'Warning', description: 'Invite created, but the email failed to send.', variant: 'destructive' });
      }
    },
    onError: (err: Error) => toast({ title: 'Error creating invite', description: err.message, variant: 'destructive' })
  });

  const handleCopy = () => {
    if (inviteUrl) {
      navigator.clipboard.writeText(inviteUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast({ title: 'Link copied to clipboard' });
    }
  };

  const handleOpenChange = (val: boolean) => {
    setOpen(val);
    if (!val) {
      setFormData({ name: '', email: '', plan_id: '', expiration_hours: 72, initial_credits: 150 });
      setInviteUrl(null);
      setCopied(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.email || !formData.name || !formData.plan_id) return;
    
    inviteMut.mutate({
      name: formData.name,
      email: formData.email,
      organization_id: null,
      plan_id: formData.plan_id,
      role: 'owner',
      expiration_hours: Number(formData.expiration_hours) || 72,
      initial_credits: Math.round(Number(formData.initial_credits) * 100)
    });
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">Invite Org</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{inviteUrl ? 'Invitation Created' : 'Invite New Organization'}</DialogTitle>
        </DialogHeader>
        
        {inviteUrl ? (
          <div className="space-y-4 pt-4">
            <div className="bg-muted/30 p-4 rounded-lg space-y-3">
              <p className="text-sm text-foreground">
                An invitation has been generated for <strong>{formData.email}</strong>. 
                They will not receive an email automatically. Please copy the link below and send it to them.
              </p>
              <div className="flex items-center gap-2">
                <Input value={inviteUrl} readOnly className="font-mono text-xs" />
                <Button variant="secondary" size="icon" onClick={handleCopy} title="Copy Link">
                  {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
                </Button>
              </div>
            </div>
            <div className="flex justify-end pt-2">
              <Button onClick={() => handleOpenChange(false)}>Close</Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label htmlFor="invite_name">Owner Name</Label>
              <Input 
                id="invite_name" 
                type="text" 
                required 
                value={formData.name} 
                onChange={e => setFormData({...formData, name: e.target.value})} 
                placeholder="Jane Doe" 
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite_email">Owner Email</Label>
              <Input 
                id="invite_email" 
                type="email" 
                required 
                value={formData.email} 
                onChange={e => setFormData({...formData, email: e.target.value})} 
                placeholder="founder@startup.com" 
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite_plan">Billing Plan</Label>
              <Select value={formData.plan_id} onValueChange={(val) => setFormData({...formData, plan_id: val})}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a plan to attach" />
                </SelectTrigger>
                <SelectContent>
                  {plans?.map(p => (
                    <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite_expires">Expiration (Hours)</Label>
              <Input 
                id="invite_expires" 
                type="number" 
                min="1" 
                required 
                value={formData.expiration_hours} 
                onChange={e => setFormData({...formData, expiration_hours: parseInt(e.target.value, 10)})} 
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite_credits">Initial Credits ($)</Label>
              <Input 
                id="invite_credits" 
                type="number" 
                min="0" 
                max="1000"
                step="1"
                required 
                value={formData.initial_credits} 
                onChange={e => setFormData({...formData, initial_credits: Number(e.target.value)})} 
              />
            </div>
            <div className="flex justify-end pt-2">
              <Button type="submit" disabled={inviteMut.isPending || !formData.email || !formData.name || !formData.plan_id}>
                {inviteMut.isPending ? 'Generating...' : 'Generate Invite Link'}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function AdminOrganizations() {
  const qc = useQueryClient();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createData, setCreateData] = useState({ name: '', slug: '', owner_email: '' });
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const { data: orgs, isLoading: isOrgsLoading } = useQuery({
    queryKey: ['admin', 'organizations', search, statusFilter],
    queryFn: () => getAdminOrganizations({ search, status: statusFilter === 'all' ? '' : statusFilter }),
    enabled: statusFilter !== 'pending',
  });

  const { data: pendingInvites, isLoading: isInvitesLoading } = useQuery({
    queryKey: ['admin', 'invites', search],
    queryFn: () => getAdminPendingInvites(),
    enabled: statusFilter === 'pending',
  });

  const isLoading = isOrgsLoading || isInvitesLoading;

  const { data: products } = useQuery({ queryKey: ['admin', 'products'], queryFn: getAdminProducts });

  const createMut = useMutation({
    mutationFn: adminCreateOrganization,
    onSuccess: () => { 
      qc.invalidateQueries({ queryKey: ['admin', 'organizations'] }); 
      toast({ title: 'Organization created successfully' }); 
      setIsCreateOpen(false);
      setCreateData({ name: '', slug: '', owner_email: '' });
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const revokeMut = useMutation({
    mutationFn: ({ orgId, productKey }: { orgId: string, productKey: string }) => revokeEntitlement(orgId, productKey),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'organizations'] });
      toast({ title: 'Product revoked' });
    },
    onError: (err: Error) => toast({ title: 'Error revoking product', description: err.message, variant: 'destructive' })
  });

  const activateMut = useMutation({
    mutationFn: activateOrganization,
    onSuccess: () => { 
      qc.invalidateQueries({ queryKey: ['admin', 'organizations'] }); 
      toast({ title: 'Organization activated' }); 
    },
    onError: (err: Error) => toast({ title: 'Error activating organization', description: err.message, variant: 'destructive' }),
  });

  const suspendMut = useMutation({
    mutationFn: suspendOrganization,
    onSuccess: () => { 
      qc.invalidateQueries({ queryKey: ['admin', 'organizations'] }); 
      toast({ title: 'Organization suspended' }); 
    },
    onError: (err: Error) => toast({ title: 'Error suspending organization', description: err.message, variant: 'destructive' }),
  });

  const revokeInviteMut = useMutation({
    mutationFn: revokeAdminInvite,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'invites'] });
      toast({ title: 'Invite revoked' });
    },
    onError: (err: Error) => toast({ title: 'Error revoking invite', description: err.message, variant: 'destructive' })
  });

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-48" /><Skeleton className="h-64" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Orgs</h1>
        
        <div className="flex items-center gap-2">
          <InviteOrgDialog />
          <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
            <DialogTrigger asChild>
              <Button size="sm">Create Org</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Organization</DialogTitle>
              </DialogHeader>
              <form onSubmit={(e) => { e.preventDefault(); createMut.mutate(createData); }} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Organization Name</Label>
                  <Input id="name" required value={createData.name} onChange={e => setCreateData({...createData, name: e.target.value})} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="slug">Slug (Optional)</Label>
                  <Input id="slug" value={createData.slug} onChange={e => setCreateData({...createData, slug: e.target.value})} placeholder="my-org" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="owner_email">Owner Email</Label>
                  <Input id="owner_email" type="email" required value={createData.owner_email} onChange={e => setCreateData({...createData, owner_email: e.target.value})} placeholder="user@example.com" />
                  <p className="text-[10px] text-muted-foreground">The user must have already signed up to the platform.</p>
                </div>
                <div className="flex justify-end pt-2">
                  <Button type="submit" disabled={createMut.isPending}>
                    {createMut.isPending ? 'Creating...' : 'Create Org'}
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input 
            type="search" 
            placeholder="Search by name, slug, or email..." 
            className="pl-8 h-9 text-xs" 
            value={search} 
            onChange={(e) => setSearch(e.target.value)} 
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[150px] h-9 text-xs">
            <SelectValue placeholder="All Statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="suspended">Suspended</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                {statusFilter === 'pending' ? (
                  <>
                    <TableHead className="text-xs font-semibold text-foreground">Email</TableHead>
                    <TableHead className="text-xs font-semibold text-foreground">Role</TableHead>
                    <TableHead className="text-xs font-semibold text-foreground">Created</TableHead>
                    <TableHead className="text-xs font-semibold text-foreground">Expires</TableHead>
                    <TableHead className="text-xs w-32" />
                  </>
                ) : (
                  <>
                    <TableHead className="text-xs font-semibold text-foreground">Name</TableHead>
                    <TableHead className="text-xs font-semibold text-foreground">Products</TableHead>
                    <TableHead className="text-xs w-32" />
                  </>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {statusFilter === 'pending' ? (
                pendingInvites?.map((invite: any) => (
                  <TableRow key={invite.id} className="group">
                    <TableCell className="text-sm font-medium">{invite.email}</TableCell>
                    <TableCell><Badge variant="secondary" className="capitalize">{invite.role}</Badge></TableCell>
                    <TableCell className="text-xs text-muted-foreground">{new Date(invite.created_at).toLocaleDateString()}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{new Date(invite.expires_at).toLocaleDateString()}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="h-7 w-7 p-0 text-destructive hover:text-destructive hover:bg-destructive/10"
                          title="Revoke Invite"
                          onClick={() => revokeInviteMut.mutate(invite.id)}
                          disabled={revokeInviteMut.isPending}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                orgs?.map((org: { id: string; name: string; status: string; entitlements: { product_key: string }[] }) => (
                  <TableRow key={org.id}>
                    <TableCell className="text-sm font-medium">
                      <Link to={`/admin/organizations/${org.id}`} className="text-primary hover:underline font-semibold">
                        {org.name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-2">
                        {(org.entitlements || []).length === 0 ? (
                          <span className="text-xs text-muted-foreground">No products</span>
                        ) : (
                          (org.entitlements || []).map((ent: { product_key: string }) => {
                            const productName = products?.find((p: { product_key: string; name: string }) => p.product_key === ent.product_key)?.name || ent.product_key;
                            return (
                              <Badge key={ent.product_key} variant="secondary" className="flex items-center gap-1 font-mono text-[10px] pr-1">
                                {productName}
                                <div 
                                  role="button"
                                  onClick={() => revokeMut.mutate({ orgId: org.id, productKey: ent.product_key })}
                                  className="w-4 h-4 rounded-full hover:bg-destructive/20 hover:text-destructive flex items-center justify-center cursor-pointer transition-colors"
                                  title="Revoke product"
                                >
                                  <X className="w-3 h-3" />
                                </div>
                              </Badge>
                            );
                          })
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-3">
                        <DeleteOrgDialog org={org} onDeleted={() => qc.invalidateQueries({ queryKey: ['admin', 'organizations'] })} />
                        <AddProductDialog 
                          orgId={org.id} 
                          onGranted={() => qc.invalidateQueries({ queryKey: ['admin', 'organizations'] })} 
                        />
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
