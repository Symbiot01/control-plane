import React, { useState, useEffect } from 'react';
import { useAuth } from '@/components/contexts/AuthContext';
import { useTheme } from '@/components/theme-provider';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getMyProfile, getMyOrganizations, getOrganization, getMembers, getAuditLogs, getOrganizationProducts, getInvites, updateMemberRole, removeMember, updateOrganization } from '@/services/organizations';
import { useToast } from '@/hooks/use-toast';
import InviteMemberModal from '@/components/InviteMemberModal';
import BillingDashboard from '@/components/BillingDashboard';
export default function RoleDashboard() {
  const { levelOfAccess, signOut } = useAuth();
  const { theme, setTheme } = useTheme();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [isSidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<'Dashboard' | 'Audit Log' | 'Members' | 'Products' | 'Settings' | 'Billing'>('Dashboard');
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [memberToRemove, setMemberToRemove] = useState<{id: string, name: string} | null>(null);
  const [editOrgName, setEditOrgName] = useState('');

  const { data: profile } = useQuery({ queryKey: ['profile'], queryFn: getMyProfile });
  const { data: myOrgs } = useQuery({ queryKey: ['myOrgs'], queryFn: getMyOrganizations });
  const orgId = myOrgs?.[0]?.id;
  
  const { data: orgDetail } = useQuery({ 
    queryKey: ['orgDetail', orgId], 
    queryFn: () => getOrganization(orgId as string), 
    enabled: !!orgId 
  });

  useEffect(() => {
    if (orgDetail?.name) {
      setEditOrgName(orgDetail.name);
    }
  }, [orgDetail?.name]);

  const { data: products } = useQuery({
    queryKey: ['orgProducts', orgId],
    queryFn: () => getOrganizationProducts(orgId as string),
    enabled: !!orgId
  });

  const { data: membersList } = useQuery({ 
    queryKey: ['orgMembers', orgId], 
    queryFn: () => getMembers(orgId as string), 
    enabled: !!orgId 
  });

  const { data: auditLogs } = useQuery({
    queryKey: ['auditLogs', orgId],
    queryFn: () => getAuditLogs(orgId!),
    enabled: !!orgId && activeTab === 'Audit Log'
  });

  const { data: invitesList } = useQuery({ 
    queryKey: ['invites', orgId], 
    queryFn: () => getInvites(orgId!), 
    enabled: !!orgId && activeTab === 'Members' 
  });


  const updateOrgMutation = useMutation({
    mutationFn: (name: string) => updateOrganization(orgId!, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orgDetail', orgId] });
      queryClient.invalidateQueries({ queryKey: ['myOrgs'] });
      toast({
        title: "Success",
        description: "Organization name updated successfully.",
      });
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Failed to update organization name.",
        variant: "destructive",
      });
    }
  });

  const updateRoleMutation = useMutation({
    mutationFn: (data: { memberId: string, role: string }) => updateMemberRole(orgId!, data.memberId, { role: data.role as any }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orgMembers', orgId] });
    }
  });

  const removeMemberMutation = useMutation({
    mutationFn: (memberId: string) => removeMember(orgId!, memberId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orgMembers', orgId] });
      setMemberToRemove(null);
    }
  });

  useEffect(() => {
    document.title = 'Medcore';
    const link = document.querySelector("link[rel*='icon']") || document.createElement('link');
    (link as any).type = 'image/svg+xml';
    (link as any).rel = 'icon';
    (link as any).href = '/medcore-favicon.svg?v=2';
    document.getElementsByTagName('head')[0].appendChild(link);
    
    return () => {
      document.title = 'ControlPlane';
      (link as any).href = '/favicon.svg';
    };
  }, []);

  return (
    <div className="theme-org flex h-full w-full bg-background text-foreground font-body-md overflow-hidden transition-colors duration-200">
      {/* Sidebar */}
      <aside className={`flex flex-col transition-all duration-300 bg-card border-r-2 border-border z-50 ${isSidebarCollapsed ? 'w-20' : 'w-52'}`}>
        <div className="h-16 flex items-center justify-between px-md border-b-2 border-border shrink-0">
          {!isSidebarCollapsed && (
            <span className="font-headline-lg text-title-md text-foreground dark:!text-[#E4E2E3] tracking-tight uppercase whitespace-nowrap truncate">
              MedCore
            </span>
          )}
          <button 
            className="w-8 h-8 flex items-center justify-center hover:bg-muted transition-colors rounded-none text-muted-foreground hover:text-slate-900 dark:hover:text-foreground border-2 border-transparent hover:border-slate-900 dark:hover:border-border flex-shrink-0 mx-auto"
            onClick={() => setSidebarCollapsed(!isSidebarCollapsed)}
          >
            <span className="material-symbols-outlined text-lg">
              {isSidebarCollapsed ? 'menu' : 'menu_open'}
            </span>
          </button>
        </div>

        <nav className="flex-1 py-lg px-md space-y-sm overflow-y-auto overflow-x-hidden min-h-0">
          <NavItem icon="dashboard" label="Dashboard" active={activeTab === 'Dashboard'} collapsed={isSidebarCollapsed} onClick={() => setActiveTab('Dashboard')} />
          <NavItem icon="apps" label="Products" active={activeTab === 'Products'} collapsed={isSidebarCollapsed} onClick={() => setActiveTab('Products')} />
          {levelOfAccess !== 'member' && (
            <>
              <NavItem icon="group" label="Members" active={activeTab === 'Members'} collapsed={isSidebarCollapsed} onClick={() => setActiveTab('Members')} />
              <NavItem icon="receipt_long" label="Billing" active={activeTab === 'Billing'} collapsed={isSidebarCollapsed} onClick={() => setActiveTab('Billing')} />
              <NavItem icon="history" label="Audit Log" active={activeTab === 'Audit Log'} collapsed={isSidebarCollapsed} onClick={() => setActiveTab('Audit Log')} />
              <NavItem icon="settings" label="Settings" active={activeTab === 'Settings'} collapsed={isSidebarCollapsed} onClick={() => setActiveTab('Settings')} />
            </>
          )}
        </nav>

        <div className={`p-3 border-t-2 border-border shrink-0 flex ${isSidebarCollapsed ? 'flex-col' : 'flex-row'} justify-center items-center gap-3`}>
           <button 
             onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
             title="Toggle Appearance"
             className="w-10 h-10 flex items-center justify-center rounded-none border-2 border-border hover:bg-[#B9CAFE] dark:hover:bg-[#B9CAFE] hover:text-[#273B69] dark:hover:text-[#273B69] transition-all text-foreground active:translate-y-1 !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:shadow-none"
           >
             <span className="material-symbols-outlined text-lg">
               {theme === 'dark' ? 'light_mode' : 'dark_mode'}
             </span>
           </button>

           <button 
             onClick={() => void signOut()}
             title="Sign Out"
             className="w-10 h-10 flex items-center justify-center rounded-none border-2 border-border hover:bg-[#FF857F] dark:hover:bg-[#FF857F] hover:text-[#611F1D] dark:hover:text-[#611F1D] transition-colors text-foreground active:translate-y-1 !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:shadow-none"
           >
             <span className="material-symbols-outlined text-lg">logout</span>
           </button>
        </div>
      </aside>

      {/* Main Wrapper */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">


        {/* Main Content */}
        <main className="flex-1 flex flex-col p-margin-mobile md:p-margin-desktop bg-transparent transition-colors duration-200 overflow-y-auto overflow-x-hidden">
          
          {activeTab === 'Dashboard' && (
            <div className="max-w-7xl w-full mx-auto flex flex-col gap-4 pb-2 h-full flex-1">
              {/* Page Header */}
              <div className="mb-2 shrink-0 flex flex-col items-start gap-0">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-[#FF857F] rounded-none border-[1.5px] border-border animate-pulse !shadow-[1px_1px_0px_0px_rgba(15,23,42,1)]"></div>
                  <p className="font-mono text-[11px] text-muted-foreground uppercase font-bold tracking-widest">
                    Organization -
                  </p>
                </div>
                
                <h1 className="font-display-lg text-4xl md:text-5xl text-foreground dark:!text-[#E4E2E3] uppercase tracking-tighter font-black drop-shadow-[2px_2px_0px_rgba(15,23,42,1)] dark:drop-shadow-[2px_2px_0px_rgba(255,255,255,0.1)] leading-none mt-1">
                  {orgDetail?.name || 'Loading...'}
                </h1>
                
                <div className="flex items-center gap-3 mt-2">
                  <div className="flex items-center gap-1.5 px-2 py-0.5 bg-muted border-2 border-border !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[5px_5px_0px_0px_rgba(0,0,0,1)]">
                    <span className="material-symbols-outlined text-[14px]">calendar_today</span>
                    <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-foreground">
                      Est. {orgDetail?.created_at ? new Date(orgDetail.created_at).toLocaleDateString() : 'N/A'}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 px-2 py-0.5 bg-[#E8E6FF] text-[#2F2B66] border-2 border-border !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[5px_5px_0px_0px_rgba(0,0,0,1)]">
                    <span className="material-symbols-outlined text-[14px]">shield_person</span>
                    <span className="font-mono text-[10px] font-bold uppercase tracking-wider">
                      Owner: {membersList?.find((m: any) => m.role === 'owner')?.display_name?.split(' ')[0] || membersList?.find((m: any) => m.role === 'owner')?.email?.split('@')[0] || 'Loading...'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 shrink-0">
                {/* Finance Overview */}
                <div className="bg-card rounded-none border-2 border-border p-5 col-span-1 transition-colors duration-200 !shadow-[5px_5px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[10px_10px_0px_0px_rgba(0,0,0,1)] flex flex-col justify-between gap-4">
                  <div className="flex justify-between items-start shrink-0 border-b-2 border-border pb-3">
                    <div>
                      <h2 className="font-title-md text-title-md text-foreground dark:!text-[#E4E2E3] uppercase tracking-wider">Finance</h2>
                      <p className="font-mono text-xs text-muted-foreground mt-1 uppercase">Plan & Credits</p>
                    </div>
                  </div>
                  
                  {/* Plan Section */}
                  <div>
                    <p className="font-mono text-xs text-muted-foreground uppercase font-bold mb-1">Plan</p>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-sm">
                        <div className="w-10 h-10 flex items-center justify-center bg-[#9CF1C7] text-[#0A5636] border-2 border-border rounded-none !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)]">
                          <span className="material-symbols-outlined text-lg">workspace_premium</span>
                        </div>
                        <span className="font-title-md text-xl font-bold uppercase tracking-tight text-foreground dark:!text-[#E4E2E3]">
                          {orgDetail?.tier || 'Loading...'}
                        </span>
                      </div>
                      <div className="border-2 border-border px-3 py-1 font-mono text-xs font-bold uppercase text-foreground bg-muted !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)]">
                        Active
                      </div>
                    </div>
                  </div>

                  {/* Credit Balance Section */}
                  <div className="border-2 border-border p-3 flex items-center justify-between bg-muted/30 !shadow-[3px_3px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[7px_7px_0px_0px_rgba(0,0,0,1)] shrink-0">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 flex items-center justify-center bg-[#9CF1C7] text-[#0A5636] border-2 border-border rounded-none !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)]">
                        <span className="material-symbols-outlined text-sm">account_balance_wallet</span>
                      </div>
                      <span className="font-mono text-sm text-muted-foreground font-bold uppercase">Credit Balance</span>
                    </div>
                    <span className="font-display-lg text-2xl text-foreground dark:!text-[#E4E2E3] font-bold tracking-tight">
                      ${((orgDetail?.wallet_balance_cents || 0) / 100).toFixed(2)}
                    </span>
                  </div>
                </div>

                {/* Product Access */}
                <div className="bg-card rounded-none border-2 border-border p-5 col-span-1 transition-colors duration-200 !shadow-[5px_5px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[10px_10px_0px_0px_rgba(0,0,0,1)] flex flex-col min-h-0">
                  <div className="flex justify-between items-start shrink-0 border-b-2 border-border pb-3">
                    <div>
                      <h2 className="font-title-md text-title-md text-foreground dark:!text-[#E4E2E3] uppercase tracking-wider">Products</h2>
                      <p className="font-mono text-xs text-muted-foreground mt-1 uppercase">Entitlements</p>
                    </div>
                  </div>
                  <div className="space-y-sm mt-4 flex-1 overflow-y-auto pr-2 min-h-0">
                    {products && products.length > 0 ? (
                      products.map((product: any, idx: number) => (
                        <ProductItem 
                          key={product.product_key} 
                          icon="deployed_code" 
                          name={product.product_key} 
                          status={product.is_active ? "Active" : "Inactive"} 
                          active={product.is_active ?? false} 
                          color={idx % 2 === 0 ? "mint" : "sage"} 
                        />
                      ))
                    ) : (
                      <div className="text-sm text-muted-foreground text-center py-4 border-2 border-dashed border-border rounded-none uppercase font-mono font-bold">
                        No products found
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Active Members */}
              <div className="bg-card rounded-none border-2 border-border p-md transition-colors duration-200 !shadow-[5px_5px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[10px_10px_0px_0px_rgba(0,0,0,1)] flex flex-col flex-1 min-h-0">
                <div className="flex justify-between items-center mb-2 shrink-0 border-b-2 border-border pb-2">
                  <h2 className="font-title-md text-title-md text-foreground dark:!text-[#E4E2E3] uppercase tracking-wider">Active Members</h2>
                </div>
                <div className="overflow-auto mt-2 flex-1 min-h-0">
                  <table className="w-full text-left border-collapse">

                    <tbody>
                      {membersList?.map((member: any, idx: number) => (
                        <MemberRow 
                          key={member.id}
                          initials={(member.display_name?.substring(0,2) || member.email.substring(0,2)).toUpperCase()} 
                          name={member.display_name || member.email} 
                          role={member.role} 
                          time={new Date(member.created_at).toLocaleDateString()} 
                          active={true} 
                          colorClass={idx % 2 === 0 ? "bg-[#B9CAFE] text-[#273B69]" : "bg-[#B9CCBB] text-[#2B3E30]"} 
                        />
                      ))}
                      {!membersList || membersList.length === 0 && (
                        <tr>
                          <td colSpan={3} className="py-8 text-center text-muted-foreground font-mono uppercase font-bold border-t-2 border-border">Loading members...</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'Audit Log' && (
            <div className="w-full space-y-lg pb-10">
              <div className="mb-8 border-b-4 border-border pb-4 inline-block">
                <h1 className="font-display-lg text-headline-lg md:text-display-lg text-foreground dark:!text-[#E4E2E3] uppercase tracking-tight">Audit Log</h1>
                <p className="font-mono text-body-md text-muted-foreground mt-2 font-bold uppercase tracking-wider">Organization Activity History</p>
              </div>

              <div className="bg-card rounded-none border-2 border-border p-lg transition-colors duration-200 !shadow-[5px_5px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[10px_10px_0px_0px_rgba(0,0,0,1)]">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="text-foreground font-mono text-label-md border-b-2 border-border uppercase bg-muted/20">
                        <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border">Action</th>
                        <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border">Result</th>
                        <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border">Performed By</th>
                        <th className="py-3 px-4 font-bold tracking-wider">Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {auditLogs?.map((log: any) => {
                        const actor = membersList?.find((m: any) => m.id === log.member_id);
                        const actorName = actor ? (actor.display_name || actor.email) : (log.member_id || 'System');
                        return (
                          <tr key={log.id} className="border-b-2 border-border hover:bg-muted/50 transition-colors">
                            <td className="py-3 px-4 font-body-sm text-foreground font-bold border-r-2 border-border">{log.action_key}</td>
                            <td className="py-3 px-4 font-mono text-xs uppercase font-bold border-r-2 border-border">
                              <span className={`px-2 py-1 border-2 border-border rounded-none ${log.result === 'success' || log.result === 'removed' ? 'bg-[#9CF1C7] text-[#0A5636]' : 'bg-[#FF857F] text-[#611F1D]'}`}>
                                {log.result}
                              </span>
                            </td>
                            <td className="py-3 px-4 font-body-sm text-muted-foreground border-r-2 border-border">{actorName}</td>
                            <td className="py-3 px-4 font-mono text-xs text-muted-foreground">{new Date(log.created_at).toLocaleString()}</td>
                          </tr>
                        );
                      })}
                      {(!auditLogs || auditLogs.length === 0) && (
                        <tr>
                          <td colSpan={4} className="py-8 text-center text-muted-foreground font-mono uppercase font-bold border-t-2 border-border">No audit logs found</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'Members' && (
            <div className="w-full space-y-lg pb-10">
              <div className="flex justify-between items-end mb-8 border-b-4 border-border pb-4">
                <div>
                  <h1 className="font-display-lg text-headline-lg md:text-display-lg text-foreground dark:!text-[#E4E2E3] uppercase tracking-tight">Members</h1>
                  <p className="font-mono text-body-md text-muted-foreground mt-2 font-bold uppercase tracking-wider">Manage your organization's team</p>
                </div>
                <button 
                  onClick={() => setShowInviteModal(true)}
                  className="px-6 py-3 bg-[#E8E6FF] text-[#2F2B66] hover:bg-[#B9CAFE] transition-colors border-2 border-border font-bold uppercase tracking-widest text-sm !shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] hover:translate-y-1 hover:shadow-none"
                >
                  + Invite Member
                </button>
              </div>

              {/* Active Members Table */}
              <div className="bg-card rounded-none border-2 border-border p-lg transition-colors duration-200 !shadow-[5px_5px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[10px_10px_0px_0px_rgba(0,0,0,1)]">
                <h2 className="font-title-md text-title-md text-foreground dark:!text-[#E4E2E3] uppercase tracking-wider mb-4">Active Members</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="text-foreground font-mono text-label-md border-b-2 border-border uppercase bg-muted/20">
                        <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border">Name / Email</th>
                        <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border">Role</th>
                        <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border">Joined</th>
                        <th className="py-3 px-4 font-bold tracking-wider text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {membersList?.map((member: any) => (
                        <tr key={member.id || member.member_id} className="border-b-2 border-border hover:bg-muted/50 transition-colors">
                          <td className="py-3 px-4 font-body-sm text-foreground font-bold border-r-2 border-border">
                            {member.display_name || 'No Name'}
                            <div className="text-xs text-muted-foreground font-normal">{member.email}</div>
                          </td>
                          <td className="py-3 px-4 font-mono text-xs uppercase font-bold border-r-2 border-border">
                            {member.role}
                          </td>
                          <td className="py-3 px-4 font-mono text-xs text-muted-foreground border-r-2 border-border">
                            {member.created_at ? new Date(member.created_at).toLocaleDateString() : 'N/A'}
                          </td>
                          <td className="py-3 px-4 flex items-center justify-end gap-2">
                            <select 
                              value={member.role}
                              onChange={(e) => updateRoleMutation.mutate({ memberId: member.id || member.member_id, role: e.target.value })}
                              disabled={profile?.id && profile.id === (member.id || member.member_id)}
                              className="bg-background text-foreground border-2 border-border font-mono text-xs uppercase p-1 rounded-none !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              <option value="member">Member</option>
                              <option value="owner">Owner</option>
                            </select>
                            
                            <button
                              onClick={() => setMemberToRemove({ id: member.id || member.member_id, name: member.display_name || member.email })}
                              disabled={profile?.id && profile.id === (member.id || member.member_id)}
                              className="w-8 h-8 flex items-center justify-center bg-[#FF857F] text-[#611F1D] border-2 border-border rounded-none !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] hover:translate-y-0.5 hover:!shadow-[1px_1px_0px_0px_rgba(15,23,42,1)] disabled:opacity-50 disabled:cursor-not-allowed"
                              title="Remove Member"
                            >
                              <span className="material-symbols-outlined text-sm">delete</span>
                            </button>
                          </td>
                        </tr>
                      ))}
                      {(!membersList || membersList.length === 0) && (
                        <tr>
                          <td colSpan={4} className="py-8 text-center text-muted-foreground font-mono uppercase font-bold border-t-2 border-border">No members found</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Pending Invites Table */}
              <div className="bg-card rounded-none border-2 border-border p-lg transition-colors duration-200 !shadow-[5px_5px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[10px_10px_0px_0px_rgba(0,0,0,1)] mt-8">
                <h2 className="font-title-md text-title-md text-foreground dark:!text-[#E4E2E3] uppercase tracking-wider mb-4">Pending Invites</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="text-foreground font-mono text-label-md border-b-2 border-border uppercase bg-muted/20">
                        <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border">Email</th>
                        <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border">Role</th>
                        <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border">Status</th>
                        <th className="py-3 px-4 font-bold tracking-wider">Date Sent</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invitesList?.map((invite: any) => (
                        <tr key={invite.id} className="border-b-2 border-border hover:bg-muted/50 transition-colors">
                          <td className="py-3 px-4 font-body-sm text-foreground font-bold border-r-2 border-border">{invite.email}</td>
                          <td className="py-3 px-4 font-mono text-xs uppercase font-bold border-r-2 border-border">{invite.role}</td>
                          <td className="py-3 px-4 font-mono text-xs uppercase font-bold border-r-2 border-border text-yellow-600 dark:text-yellow-400">{invite.status || 'Pending'}</td>
                          <td className="py-3 px-4 font-mono text-xs text-muted-foreground">{invite.created_at ? new Date(invite.created_at).toLocaleDateString() : 'N/A'}</td>
                        </tr>
                      ))}
                      {(!invitesList || invitesList.length === 0) && (
                        <tr>
                          <td colSpan={4} className="py-8 text-center text-muted-foreground font-mono uppercase font-bold border-t-2 border-border">No pending invites</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'Products' && (
            <div className="w-full space-y-lg pb-10">
              <div className="mb-8 border-b-4 border-border pb-4 inline-block">
                <h1 className="font-display-lg text-headline-lg md:text-display-lg text-foreground dark:!text-[#E4E2E3] uppercase tracking-tight">My Products</h1>
                <p className="font-mono text-body-md text-muted-foreground mt-2 font-bold uppercase tracking-wider">App Drawer & Integrations</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {products && products.length > 0 ? (
                  products.map((product: any) => {
                    const isExpired = product.expires_at ? new Date(product.expires_at).getTime() < Date.now() : false;
                    const isActive = product.is_active;

                    return (
                      <div key={product.product_key} className="bg-card rounded-none border-4 border-border p-6 flex flex-col transition-colors duration-200 !shadow-[8px_8px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] hover:-translate-y-1 hover:!shadow-[12px_12px_0px_0px_rgba(15,23,42,1)] dark:hover:!shadow-[12px_12px_0px_0px_rgba(0,0,0,1)]">
                        <div className="flex justify-between items-start mb-4 gap-4">
                          <h2 className="font-display-lg text-2xl font-bold uppercase tracking-tight text-foreground dark:!text-[#E4E2E3] truncate">
                            {product.name}
                          </h2>
                          <div className="flex flex-col gap-2 shrink-0 items-end">
                            {!isActive ? (
                              <span className="px-3 py-1 font-mono text-xs font-bold uppercase tracking-wider bg-muted text-muted-foreground border-2 border-border !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                                Maintenance
                              </span>
                            ) : isExpired ? (
                              <span className="px-3 py-1 font-mono text-xs font-bold uppercase tracking-wider bg-[#FF857F] text-[#611F1D] border-2 border-border !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                                Expired
                              </span>
                            ) : (
                              <span className="px-3 py-1 font-mono text-xs font-bold uppercase tracking-wider bg-[#9CF1C7] text-[#0A5636] border-2 border-border !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
                                Active
                              </span>
                            )}
                            
                            {product.max_compute_units !== null && product.max_compute_units !== undefined && (
                              <span className="px-2 py-0.5 font-mono text-[10px] font-bold uppercase bg-[#E8E6FF] text-[#2F2B66] border-2 border-border">
                                {product.max_compute_units.toLocaleString()} CU Limit
                              </span>
                            )}
                          </div>
                        </div>

                        <p className="font-body-sm text-muted-foreground flex-1 mb-6 line-clamp-3">
                          {product.description || "No description provided."}
                        </p>
                        
                        <div className="mt-auto pt-4 border-t-2 border-border">
                          {(isActive && !isExpired && product.product_link) ? (
                            <a 
                              href={product.product_link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="w-full py-3 flex items-center justify-center gap-2 border-2 border-border font-bold uppercase tracking-wider text-white bg-black dark:text-[#223243] dark:bg-[#B8C8DE] transition-colors !shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-y-1 hover:!shadow-none"
                            >
                              <span className="material-symbols-outlined text-sm">open_in_new</span>
                              Launch App
                            </a>
                          ) : (
                            <button 
                              disabled
                              className="w-full py-3 flex items-center justify-center gap-2 border-2 border-border font-bold uppercase tracking-wider text-muted-foreground bg-muted transition-colors opacity-50 cursor-not-allowed"
                            >
                              <span className="material-symbols-outlined text-sm">lock</span>
                              Unavailable
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="col-span-1 md:col-span-2 text-center py-16 border-4 border-dashed border-border bg-muted/20">
                    <span className="material-symbols-outlined text-4xl text-muted-foreground mb-4">inventory_2</span>
                    <h3 className="font-display-lg text-xl uppercase font-bold text-foreground">No Products Found</h3>
                    <p className="font-mono text-sm text-muted-foreground mt-2 uppercase">Your organization currently has no active entitlements.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'Settings' && (
            <div className="w-full space-y-lg pb-10">
              <div className="mb-8 border-b-4 border-border pb-4 inline-block">
                <h1 className="font-display-lg text-headline-lg md:text-display-lg text-foreground dark:!text-[#E4E2E3] uppercase tracking-tight">Settings</h1>
                <p className="font-mono text-body-md text-muted-foreground mt-2 font-bold uppercase tracking-wider">Organization Details</p>
              </div>

              <div className="bg-card max-w-2xl border-4 border-border p-8 !shadow-[8px_8px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
                <div className="space-y-6">
                  <div>
                    <label className="block font-mono text-xs font-bold text-foreground uppercase mb-2">Organization Name</label>
                    <input 
                      type="text" 
                      value={editOrgName}
                      onChange={(e) => setEditOrgName(e.target.value)}
                      maxLength={40}
                      placeholder="My Organization"
                      className="w-full bg-background border-2 border-border p-3 text-foreground font-body-sm focus:outline-none focus:border-slate-900 !shadow-[3px_3px_0px_0px_rgba(15,23,42,1)]"
                    />
                  </div>
                  
                  <div>
                    <label className="block font-mono text-xs font-bold text-muted-foreground uppercase mb-2 flex items-center gap-2">
                      Slug
                      <span className="material-symbols-outlined text-[10px]" title="Read Only">lock</span>
                    </label>
                    <input 
                      type="text" 
                      value={orgDetail?.slug || ''}
                      disabled
                      className="w-full bg-muted border-2 border-border p-3 text-muted-foreground font-body-sm opacity-60 cursor-not-allowed"
                    />
                  </div>

                  <div>
                    <label className="block font-mono text-xs font-bold text-muted-foreground uppercase mb-2 flex items-center gap-2">
                      Billing Tier
                      <span className="material-symbols-outlined text-[10px]" title="Read Only">lock</span>
                    </label>
                    <input 
                      type="text" 
                      value={orgDetail?.tier ? orgDetail.tier.toUpperCase() : ''}
                      disabled
                      className="w-full bg-muted border-2 border-border p-3 font-mono font-bold tracking-widest text-muted-foreground font-body-sm opacity-60 cursor-not-allowed"
                    />
                  </div>

                  <div className="pt-6 border-t-2 border-border mt-8">
                    <button 
                      onClick={() => updateOrgMutation.mutate(editOrgName)}
                      disabled={!editOrgName || editOrgName === orgDetail?.name || updateOrgMutation.isPending}
                      className="w-full py-4 border-2 border-border font-bold uppercase tracking-widest text-white bg-black dark:text-[#223243] dark:bg-[#B8C8DE] transition-all !shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-y-1 hover:!shadow-none disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:!shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] disabled:cursor-not-allowed"
                    >
                      {updateOrgMutation.isPending ? 'Saving...' : 'Save Changes'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'Billing' && orgId && (
            <BillingDashboard orgId={orgId} />
          )}

        {/* Modals */}
        <InviteMemberModal 
          isOpen={showInviteModal} 
          onClose={() => setShowInviteModal(false)} 
          orgId={orgId as string} 
        />

        {memberToRemove && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="bg-card w-full max-w-md border-4 border-border rounded-none !shadow-[12px_12px_0px_0px_rgba(15,23,42,1)] p-6 text-center">
              <div className="w-16 h-16 mx-auto bg-[#FF857F] text-[#611F1D] border-4 border-border flex items-center justify-center !shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] mb-4">
                <span className="material-symbols-outlined text-3xl">warning</span>
              </div>
              <h2 className="font-display-lg text-2xl text-foreground dark:!text-[#E4E2E3] uppercase font-bold tracking-tight mb-2">Remove Member</h2>
              <p className="font-body-sm text-muted-foreground mb-6">Are you sure you want to remove <strong>{memberToRemove.name}</strong> from this organization? This action cannot be undone.</p>
              
              <div className="flex gap-4">
                <button 
                  onClick={() => setMemberToRemove(null)}
                  className="flex-1 py-3 border-2 border-border font-bold uppercase text-foreground bg-muted hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors !shadow-[3px_3px_0px_0px_rgba(15,23,42,1)] hover:translate-y-1 hover:shadow-none"
                >
                  Cancel
                </button>
                <button 
                  onClick={() => removeMemberMutation.mutate(memberToRemove.id)}
                  disabled={removeMemberMutation.isPending}
                  className="flex-1 py-3 border-2 border-border font-bold uppercase text-white bg-[#FF3B30] transition-colors !shadow-[3px_3px_0px_0px_rgba(15,23,42,1)] hover:translate-y-1 hover:shadow-none disabled:opacity-50"
                >
                  {removeMemberMutation.isPending ? 'Removing...' : 'Yes, Remove'}
                </button>
              </div>
            </div>
          </div>
        )}
        </main>
      </div>
    </div>
  );
}

function NavItem({ icon, label, active, collapsed, onClick }: { icon: string, label: string, active?: boolean, collapsed: boolean, onClick?: () => void }) {
  return (
    <button 
      onClick={(e) => { e.preventDefault(); onClick?.(); }}
      className={`w-full flex items-center gap-sm p-sm transition-all font-bold uppercase tracking-tight rounded-none ${
        active 
          ? 'bg-black !text-white dark:bg-[#B8C8DE] dark:!text-[#223243] border-2 border-border !shadow-[3px_3px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[7px_7px_0px_0px_rgba(0,0,0,1)]' 
          : 'border-2 border-transparent hover:border-slate-900 dark:hover:border-border hover:bg-muted text-muted-foreground hover:text-slate-900 dark:hover:text-foreground'
      } ${collapsed ? 'justify-center px-0' : ''}`}
    >
      <span className="material-symbols-outlined flex-shrink-0 text-inherit">{icon}</span>
      {!collapsed && <span className="sidebar-text text-inherit">{label}</span>}
    </button>
  );
}

function ProductItem({ icon, name, status, active, color }: { icon: string, name: string, status: string, active: boolean, color: 'mint' | 'sage' | 'none' }) {
  const bgColor = active ? (color === 'mint' ? 'bg-[#9CF1C7]' : 'bg-[#B9CCBB]') : 'bg-slate-200 dark:bg-muted';
  const textColor = active ? (color === 'mint' ? 'text-[#0A5636]' : 'text-[#2B3E30]') : 'text-muted-foreground';

  return (
    <div className={`flex items-center justify-between py-1 px-2 rounded-none border-2 transition-all hover:translate-y-1 !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[5px_5px_0px_0px_rgba(0,0,0,1)] hover:shadow-none ${
      active 
        ? 'bg-card border-border cursor-pointer' 
        : 'bg-muted border-border border-dashed opacity-70 cursor-not-allowed'
    }`}>
      <div className="flex items-center gap-2">
        <div className={`w-8 h-8 rounded-none flex items-center justify-center border-2 border-border ${bgColor} ${textColor}`}>
          <span className="material-symbols-outlined text-[18px]">{icon}</span>
        </div>
        <div>
          <p className="font-title-md text-sm text-foreground uppercase tracking-tight">{name}</p>
          <p className={`font-mono text-[9px] mt-0 font-bold uppercase ${active ? 'text-slate-700 dark:text-muted-foreground' : 'text-muted-foreground'}`}>{status}</p>
        </div>
      </div>
      <span className={`material-symbols-outlined text-lg font-bold ${textColor}`}>
        {active ? 'check_box' : 'disabled_by_default'}
      </span>
    </div>
  );
}

function MemberRow({ initials, name, role, time, active, colorClass }: { initials: string, name: string, role: string, time: string, active: boolean, colorClass: string }) {
  return (
    <tr className="border-b-2 border-border hover:bg-muted/50 transition-colors group">
      <td className="py-3 px-4 border-r-2 border-border">
        <div className="flex items-center gap-sm">
          <div className={`w-8 h-8 flex items-center justify-center font-mono font-bold text-sm rounded-none border-2 border-border ${active ? colorClass : 'bg-muted text-muted-foreground'}`}>
            {initials}
          </div>
          <span className="font-body-sm text-foreground font-bold">{name}</span>
        </div>
      </td>
      <td className="py-3 px-4 font-mono text-muted-foreground font-bold uppercase text-xs border-r-2 border-border">{role}</td>
      <td className="py-3 px-4 font-mono text-muted-foreground font-bold text-xs">{time}</td>
    </tr>
  );
}
