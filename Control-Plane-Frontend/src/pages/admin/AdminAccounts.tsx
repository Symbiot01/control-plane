import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getAdminMembers, updateMemberRole, getAdminOrganizations, deleteAdminMember } from '@/services/admin';
import { Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from '@/hooks/use-toast';
import type { AdminMemberResponse, GlobalRole } from '@/types/api';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';

function AssignOrgDialog({ member, onAssigned }: { member: AdminMemberResponse, onAssigned: () => void }) {
  const [open, setOpen] = useState(false);
  const [selectedOrg, setSelectedOrg] = useState<string>('');
  const [selectedRole, setSelectedRole] = useState<'owner' | 'member' | 'viewer'>('member');
  
  const { data: orgs, isLoading: orgsLoading } = useQuery({
    queryKey: ['admin', 'organizations'],
    queryFn: () => getAdminOrganizations(),
    enabled: open
  });
  
  const updateRoleMut = useMutation({
    mutationFn: () => updateMemberRole(member.member_id, selectedRole, selectedOrg),
    onSuccess: () => {
      toast({ title: 'User assigned to organization successfully' });
      setOpen(false);
      onAssigned();
    },
    onError: (err: Error) => toast({ title: 'Failed to assign user', description: err.message, variant: 'destructive' })
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrg || !selectedRole) return;
    updateRoleMut.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="h-7 text-xs font-medium">Assign to Org</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Assign User to Organization</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          <div className="space-y-2">
            <Label>Select Organization</Label>
            <Select value={selectedOrg} onValueChange={setSelectedOrg}>
              <SelectTrigger>
                <SelectValue placeholder="Select an organization" />
              </SelectTrigger>
              <SelectContent>
                {orgsLoading ? (
                  <SelectItem value="loading" disabled>Loading...</SelectItem>
                ) : orgs?.map((o) => (
                  <SelectItem key={o.id} value={o.id}>{o.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Select Role</Label>
            <Select value={selectedRole} onValueChange={(val) => setSelectedRole(val as 'owner' | 'member' | 'viewer')}>
              <SelectTrigger>
                <SelectValue placeholder="Select a role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="owner">Owner</SelectItem>
                <SelectItem value="member">Member</SelectItem>
                <SelectItem value="viewer">Viewer</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex justify-end pt-2">
            <Button type="submit" disabled={!selectedOrg || !selectedRole || updateRoleMut.isPending}>
              {updateRoleMut.isPending ? 'Assigning...' : 'Assign User'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function AdminAccounts() {
  const qc = useQueryClient();
  const { data: members, isLoading } = useQuery({ 
    queryKey: ['admin', 'members'], 
    queryFn: getAdminMembers 
  });

  const { data: orgs } = useQuery({
    queryKey: ['admin', 'organizations'],
    queryFn: () => getAdminOrganizations()
  });

  const getOrgName = (orgId: string | null) => {
    if (!orgId) return 'N/A';
    const org = orgs?.find(o => o.id === orgId);
    return org ? org.name : orgId;
  };

  const deleteMut = useMutation({
    mutationFn: deleteAdminMember,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'members'] });
      toast({ title: 'Account removed successfully' });
    },
    onError: (err: Error) => toast({ title: 'Failed to remove account', description: err.message, variant: 'destructive' })
  });

  const updateRoleMut = useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: 'owner' | 'member' | 'viewer' }) => updateMemberRole(memberId, role),
    onSuccess: () => { 
      qc.invalidateQueries({ queryKey: ['admin', 'members'] }); 
      toast({ title: 'Role updated successfully' }); 
    },
    onError: (err: Error) => toast({ title: 'Failed to update role', description: err.message, variant: 'destructive' }),
  });

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-32" /><Skeleton className="h-64" /></div>;

  const superAdmins = members?.filter(m => m.global_role === 'super_admin') || [];
  const owners = members?.filter(m => m.global_role === 'owner') || [];
  const orgMembers = members?.filter(m => m.global_role === 'member') || [];
  const viewers = members?.filter(m => m.global_role === 'viewer') || [];
  const guests = members?.filter(m => m.global_role === 'guest') || [];

  const handleRoleChange = (memberId: string, currentRole: GlobalRole, newRole: string) => {
    if (newRole !== 'owner' && newRole !== 'member' && newRole !== 'viewer') return;
    if (newRole === currentRole) return;
    updateRoleMut.mutate({ memberId, role: newRole as 'owner' | 'member' | 'viewer' });
  };

  const renderTable = (groupTitle: string, groupMembers: AdminMemberResponse[], showRoleSelect: boolean, allowDelete: boolean) => {
    const isGuests = groupTitle === "Guests / Unassigned";
    if (groupMembers.length === 0) return null;
    return (
      <Card className="mb-6">
        <CardHeader className="py-4 border-b border-border/50 bg-muted/20">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            {groupTitle} <Badge variant="secondary" className="text-[10px] font-mono px-1.5">{groupMembers.length}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>

            <TableBody>
              {groupMembers.map((m) => (
                <TableRow key={m.member_id} className="group">
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Avatar className="h-8 w-8 border border-border">
                        <AvatarFallback className="text-xs font-semibold uppercase bg-primary/10 text-primary">
                          {m.display_name?.[0] || m.email?.[0] || 'U'}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-foreground">{m.display_name || 'No Name'}</span>
                        <span className="text-xs text-muted-foreground">{m.email}</span>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-center align-middle w-1/3">
                    <div className="flex justify-center items-center">
                      <span className="text-xs font-medium text-muted-foreground bg-muted px-3 py-1.5 rounded-md max-w-[200px] truncate">
                        {getOrgName(m.organization_id)}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      {showRoleSelect ? (
                        <select
                          className="h-8 w-32 rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-ring capitalize cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                          value={m.global_role}
                          onChange={(e) => handleRoleChange(m.member_id, m.global_role, e.target.value)}
                          disabled={updateRoleMut.isPending}
                        >
                          <option value="owner">Owner</option>
                          <option value="member">Member</option>
                          <option value="viewer">Viewer</option>
                        </select>
                      ) : (
                        <>
                          {isGuests && (
                            <AssignOrgDialog member={m} onAssigned={() => qc.invalidateQueries({ queryKey: ['admin', 'members'] })} />
                          )}
                          <Badge variant="outline" className="uppercase font-label-caps text-[10px]">
                            {m.global_role.replace('_', ' ')}
                          </Badge>
                        </>
                      )}
                      {allowDelete && (
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-8 w-8 bg-admin-coral/20 text-admin-coral-foreground hover:bg-admin-coral hover:text-admin-coral-foreground/90 ml-1 rounded"
                          onClick={() => {
                            if (window.confirm('Are you sure you want to remove this account?')) {
                              deleteMut.mutate(m.member_id);
                            }
                          }}
                          disabled={deleteMut.isPending}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between pb-4 border-b border-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Accounts Management</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage global members and roles across the platform.</p>
        </div>
      </div>

      <div className="space-y-2">
        {renderTable("Super Admins", superAdmins, false, false)}
        {renderTable("Workspace Owners", owners, true, false)}
        {renderTable("Workspace Members", orgMembers, true, true)}
        {renderTable("Workspace Viewers", viewers, true, true)}
        {renderTable("Guests / Unassigned", guests, false, true)}
      </div>
    </div>
  );
}
