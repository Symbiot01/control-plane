import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getCurrentSubscription, getUsageSummary, getInvoices } from '@/services/billing';
import { getQuotas, updateQuota } from '@/services/quotas';
import { useToast } from '@/hooks/use-toast';

export default function BillingDashboard({ orgId }: { orgId: string }) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: subscription, isLoading: loadingSub } = useQuery({
    queryKey: ['subscription', orgId],
    queryFn: () => getCurrentSubscription(orgId)
  });

  const { data: usageSummary, isLoading: loadingUsage } = useQuery({
    queryKey: ['usageSummary', orgId],
    queryFn: () => getUsageSummary(orgId)
  });

  const { data: invoices, isLoading: loadingInvoices } = useQuery({
    queryKey: ['invoices', orgId],
    queryFn: () => getInvoices(orgId)
  });

  const { data: quotas, isLoading: loadingQuotas } = useQuery({
    queryKey: ['quotas', orgId],
    queryFn: () => getQuotas(orgId)
  });

  // State for editing quotas
  const [editingQuotaId, setEditingQuotaId] = useState<string | null>(null);
  const [editLimitValue, setEditLimitValue] = useState<number>(0);

  const updateQuotaMutation = useMutation({
    mutationFn: (data: { action_id: string; period: any; limit_value: number }) => updateQuota(orgId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quotas', orgId] });
      toast({
        title: "Success",
        description: "Quota limit updated successfully."
      });
      setEditingQuotaId(null);
    },
    onError: (err: any) => {
      toast({
        variant: "destructive",
        title: "Error",
        description: err.message || "Failed to update quota limit."
      });
    }
  });

  const handleSaveQuota = (action_id: string, period: any) => {
    updateQuotaMutation.mutate({ action_id, period, limit_value: editLimitValue });
  };

  return (
    <div className="w-full space-y-lg pb-10">
      <div className="mb-8 border-b-4 border-border pb-4 inline-block">
        <h1 className="font-display-lg text-headline-lg md:text-display-lg text-foreground dark:!text-[#E4E2E3] uppercase tracking-tight">Billing</h1>
        <p className="font-mono text-body-md text-muted-foreground mt-2 font-bold uppercase tracking-wider">Financial Overview & Spend Limits</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Section 1: Subscription */}
        <div className="bg-card border-4 border-border p-6 !shadow-[8px_8px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] flex flex-col">
          <h2 className="font-title-md text-xl font-bold uppercase tracking-wider mb-4 border-b-2 border-border pb-2">Current Subscription</h2>
          {loadingSub ? (
            <p className="text-muted-foreground font-mono uppercase text-sm">Loading...</p>
          ) : subscription ? (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="font-mono text-xs uppercase font-bold text-muted-foreground">Plan</span>
                <span className="font-bold uppercase text-foreground">{subscription.plan?.name || 'Unknown Plan'}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-mono text-xs uppercase font-bold text-muted-foreground">Monthly Price</span>
                <span className="font-bold text-lg text-foreground">
                  {subscription.plan?.monthly_price !== undefined ? `$${(subscription.plan.monthly_price / 100).toFixed(2)}` : 'N/A'}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-mono text-xs uppercase font-bold text-muted-foreground">Status</span>
                <span className={`px-2 py-1 font-mono text-[10px] uppercase font-bold border-2 border-border ${subscription.status === 'active' ? 'bg-[#9CF1C7] text-[#0A5636]' : 'bg-[#FF857F] text-[#611F1D]'}`}>
                  {subscription.status}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-mono text-xs uppercase font-bold text-muted-foreground">Billing Cycle</span>
                <span className="font-mono text-xs text-foreground font-bold">
                  {new Date(subscription.billing_cycle_start).toLocaleDateString()} - {new Date(subscription.billing_cycle_end).toLocaleDateString()}
                </span>
              </div>
            </div>
          ) : (
             <p className="text-muted-foreground font-mono uppercase text-sm font-bold">No active subscription found.</p>
          )}
        </div>

        {/* Section 2: Usage Summary */}
        <div className="bg-card border-4 border-border p-6 !shadow-[8px_8px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] flex flex-col">
          <h2 className="font-title-md text-xl font-bold uppercase tracking-wider mb-4 border-b-2 border-border pb-2">Usage Summary</h2>
          {loadingUsage ? (
             <p className="text-muted-foreground font-mono uppercase text-sm">Loading...</p>
          ) : usageSummary ? (
            <div className="space-y-6">
              <div className="flex items-end gap-2">
                <span className="font-display-lg text-4xl font-bold text-foreground leading-none">{usageSummary.total_compute_units.toLocaleString()}</span>
                <span className="font-mono text-xs font-bold uppercase text-muted-foreground mb-1">Total CU</span>
              </div>
              
              <div className="space-y-4">
                {usageSummary.by_action?.map((action: any, idx: number) => {
                  const maxVal = Math.max(...usageSummary.by_action.map((a: any) => a.compute_units), 1);
                  const width = `${(action.compute_units / maxVal) * 100}%`;
                  return (
                    <div key={action.action_key || idx} className="space-y-1">
                      <div className="flex justify-between font-mono text-[10px] uppercase font-bold text-foreground">
                        <span>{action.action_key || 'Unknown Action'}</span>
                        <span>{action.compute_units.toLocaleString()} CU</span>
                      </div>
                      <div className="h-4 w-full bg-muted border-2 border-border relative overflow-hidden">
                        <div className="h-full bg-black dark:bg-[#B8C8DE] absolute left-0 top-0 transition-all duration-500" style={{ width }}></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground font-mono uppercase text-sm font-bold">No usage data found.</p>
          )}
        </div>
      </div>

      {/* Section 4: Spend Limits & Quotas */}
      <div className="bg-card border-4 border-border p-6 !shadow-[8px_8px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] mt-8">
        <h2 className="font-title-md text-xl font-bold uppercase tracking-wider mb-4 border-b-2 border-border pb-2">Spend Limits (Quotas)</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-foreground font-mono text-label-md border-b-2 border-border uppercase bg-muted/20">
                <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border w-1/3">Action</th>
                <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border w-1/4">Period</th>
                <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border w-1/4">Limit</th>
                <th className="py-3 px-4 font-bold tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loadingQuotas ? (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-muted-foreground font-mono uppercase font-bold border-t-2 border-border">Loading...</td>
                </tr>
              ) : quotas && quotas.length > 0 ? (
                quotas.map((quota: any) => (
                  <tr key={quota.id} className="border-b-2 border-border hover:bg-muted/50 transition-colors">
                    <td className="py-3 px-4 font-body-sm text-foreground font-bold border-r-2 border-border">
                      {quota.action_key || quota.action_id}
                    </td>
                    <td className="py-3 px-4 font-mono text-xs uppercase font-bold border-r-2 border-border text-muted-foreground">
                      {quota.period}
                    </td>
                    <td className="py-3 px-4 border-r-2 border-border">
                      {editingQuotaId === quota.id ? (
                        <input
                          type="number"
                          value={editLimitValue}
                          onChange={(e) => setEditLimitValue(parseInt(e.target.value) || 0)}
                          className="w-full bg-background border-2 border-border p-1 text-foreground font-mono text-sm focus:outline-none focus:border-slate-900 !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)]"
                        />
                      ) : (
                        <span className="font-mono text-sm font-bold text-foreground">
                          {quota.limit_value.toLocaleString()}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 flex justify-end gap-2">
                      {editingQuotaId === quota.id ? (
                        <>
                          <button
                            onClick={() => handleSaveQuota(quota.action_id, quota.period)}
                            disabled={updateQuotaMutation.isPending}
                            className="bg-[#9CF1C7] text-[#0A5636] border-2 border-border p-1 text-xs font-bold uppercase !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] hover:translate-y-px hover:shadow-none transition-all disabled:opacity-50"
                          >
                            Save
                          </button>
                          <button
                            onClick={() => setEditingQuotaId(null)}
                            className="bg-muted text-muted-foreground border-2 border-border p-1 text-xs font-bold uppercase !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] hover:translate-y-px hover:shadow-none transition-all"
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => {
                            setEditingQuotaId(quota.id);
                            setEditLimitValue(quota.limit_value);
                          }}
                          className="bg-[#E8E6FF] text-[#2F2B66] border-2 border-border px-3 py-1 text-xs font-bold uppercase !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] hover:translate-y-px hover:shadow-none transition-all"
                        >
                          Edit
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-muted-foreground font-mono uppercase font-bold border-t-2 border-border">No quotas set</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Section 3: Invoices */}
      <div className="bg-card border-4 border-border p-6 !shadow-[8px_8px_0px_0px_rgba(15,23,42,1)] dark:!shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] mt-8">
        <h2 className="font-title-md text-xl font-bold uppercase tracking-wider mb-4 border-b-2 border-border pb-2">Invoice History</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-foreground font-mono text-label-md border-b-2 border-border uppercase bg-muted/20">
                <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border">Date Range</th>
                <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border">Amount Due</th>
                <th className="py-3 px-4 font-bold tracking-wider border-r-2 border-border">Status</th>
                <th className="py-3 px-4 font-bold tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loadingInvoices ? (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-muted-foreground font-mono uppercase font-bold border-t-2 border-border">Loading...</td>
                </tr>
              ) : invoices && invoices.length > 0 ? (
                invoices.map((invoice: any) => (
                  <tr key={invoice.id} className="border-b-2 border-border hover:bg-muted/50 transition-colors">
                    <td className="py-3 px-4 font-mono text-xs font-bold border-r-2 border-border text-foreground">
                      {new Date(invoice.billing_period_start).toLocaleDateString()} - {new Date(invoice.billing_period_end).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 font-body-sm font-bold text-foreground border-r-2 border-border">
                      ${(invoice.amount_due / 100).toFixed(2)}
                    </td>
                    <td className="py-3 px-4 border-r-2 border-border">
                      <span className={`px-2 py-1 font-mono text-[10px] uppercase font-bold border-2 border-border ${
                        invoice.status === 'paid' ? 'bg-[#9CF1C7] text-[#0A5636]' :
                        invoice.status === 'overdue' ? 'bg-[#FF857F] text-[#611F1D]' :
                        'bg-[#E8E6FF] text-[#2F2B66]'
                      }`}>
                        {invoice.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 flex justify-end">
                      <button className="flex items-center gap-1 bg-muted text-foreground border-2 border-border px-3 py-1 text-xs font-bold uppercase !shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] hover:translate-y-px hover:shadow-none transition-all">
                        <span className="material-symbols-outlined text-[14px]">visibility</span>
                        View
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-muted-foreground font-mono uppercase font-bold border-t-2 border-border">No invoices found</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
