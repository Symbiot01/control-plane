import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getAdminOrganizations, 
  getAdminCredits, 
  getCreditLedger, 
  grantCredits,
  getAdminInvoices,
  generateInvoice,
  updateInvoiceStatus
} from '@/services/admin';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { toast } from '@/hooks/use-toast';
import { Link } from 'react-router-dom';
import type { InvoiceStatus } from '@/types/api';

export default function AdminBilling() {
  const qc = useQueryClient();
  const [selectedOrg, setSelectedOrg] = useState('');
  
  // Credits specific state
  const [grantOpen, setGrantOpen] = useState(false);
  const [grantAmount, setGrantAmount] = useState('');
  const [grantRef, setGrantRef] = useState('');

  // Invoices specific state
  const [genOpen, setGenOpen] = useState(false);
  const [genEnd, setGenEnd] = useState('');

  // Queries
  const { data: orgs } = useQuery({ queryKey: ['admin', 'organizations'], queryFn: getAdminOrganizations });
  
  const { data: credits, isLoading: creditsLoading } = useQuery({
    queryKey: ['admin', 'credits', selectedOrg],
    queryFn: () => getAdminCredits(selectedOrg),
    enabled: !!selectedOrg,
  });
  
  const { data: ledger, isLoading: ledgerLoading } = useQuery({
    queryKey: ['admin', 'credits', 'ledger', selectedOrg],
    queryFn: () => getCreditLedger(selectedOrg),
    enabled: !!selectedOrg,
  });

  const { data: invoices, isLoading: invoicesLoading } = useQuery({
    queryKey: ['admin', 'invoices', selectedOrg],
    queryFn: () => getAdminInvoices(selectedOrg),
    enabled: !!selectedOrg,
  });

  // Mutations
  const grantMut = useMutation({
    mutationFn: () => grantCredits(selectedOrg, {
      amount_cents: Math.round(parseFloat(grantAmount) * 100),
      type: 'grant',
      reference_id: grantRef || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'credits'] });
      qc.invalidateQueries({ queryKey: ['admin', 'org'] });
      qc.invalidateQueries({ queryKey: ['credits'] });
      toast({ title: 'Credits granted' });
      setGrantOpen(false);
      setGrantAmount('');
      setGrantRef('');
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const genMut = useMutation({
    mutationFn: () => generateInvoice(selectedOrg, { billing_period_end: new Date(genEnd).toISOString() }),
    onSuccess: () => { 
      qc.invalidateQueries({ queryKey: ['admin', 'invoices'] }); 
      toast({ title: 'Invoice generated' }); 
      setGenOpen(false); 
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: InvoiceStatus }) => updateInvoiceStatus(id, { status }),
    onSuccess: () => { 
      qc.invalidateQueries({ queryKey: ['admin', 'invoices'] }); 
      toast({ title: 'Status updated' }); 
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const isLoading = creditsLoading || ledgerLoading || invoicesLoading;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between pb-4 border-b border-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Billing Management</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage credits, ledger, and invoices for organizations.</p>
        </div>
      </div>

      <div className="space-y-2">
        <Label className="text-sm font-medium">Select Organization</Label>
        <Select value={selectedOrg} onValueChange={setSelectedOrg}>
          <SelectTrigger className="w-full md:w-[400px]">
            <SelectValue placeholder="Select an organization to view billing data..." />
          </SelectTrigger>
          <SelectContent>
            {orgs?.map((o) => <SelectItem key={o.id} value={o.id}>{o.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {!selectedOrg && (
        <div className="p-12 text-center border border-dashed rounded-lg bg-muted/10 text-muted-foreground text-sm">
          Select an organization to view credits and invoices.
        </div>
      )}

      {isLoading && selectedOrg && (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {selectedOrg && !isLoading && (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-300">
          
          {/* Credits Overview Section */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold tracking-tight border-b border-border pb-2">Credits Overview</h2>
            {credits && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card>
                  <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground font-medium">Balance</CardTitle></CardHeader>
                  <CardContent><p className="text-2xl font-bold">${(credits.balance_cents / 100).toFixed(2)}</p></CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground font-medium">Billing Mode</CardTitle></CardHeader>
                  <CardContent><Badge variant="outline" className="text-xs uppercase">{credits.billing_mode}</Badge></CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground font-medium">Overdraft Limit</CardTitle></CardHeader>
                  <CardContent><p className="text-2xl font-bold">${(credits.overdraft_limit_cents / 100).toFixed(2)}</p></CardContent>
                </Card>
              </div>
            )}
          </div>

          {/* Invoices Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <h2 className="text-lg font-semibold tracking-tight">Invoices</h2>
              <Button size="sm" onClick={() => setGenOpen(true)}>Generate Invoice</Button>
            </div>
            
            {invoices && (
              <Card>
                <CardContent className="p-0">
                  <Table>
                    <TableHeader>
                      <TableRow className="hover:bg-transparent bg-muted/20">
                        <TableHead className="text-xs">Period</TableHead>
                        <TableHead className="text-xs text-right">Amount</TableHead>
                        <TableHead className="text-xs">Status</TableHead>
                        <TableHead className="text-xs w-48">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {invoices.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={4} className="text-center text-sm text-muted-foreground py-8">
                            No invoices found.
                          </TableCell>
                        </TableRow>
                      ) : (
                        invoices.map((inv) => (
                          <TableRow key={inv.id}>
                            <TableCell className="text-xs">
                              <Link to={`/admin/billing/invoices/${inv.id}`} className="text-primary hover:underline font-medium">
                                {new Date(inv.billing_period_start).toLocaleDateString()} – {new Date(inv.billing_period_end).toLocaleDateString()}
                              </Link>
                            </TableCell>
                            <TableCell className="text-xs text-right font-medium">${(inv.amount_due / 100).toFixed(2)}</TableCell>
                            <TableCell><Badge variant="outline" className="text-[10px] uppercase">{inv.status}</Badge></TableCell>
                            <TableCell className="flex gap-1">
                              {inv.status === 'draft' && (
                                <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={() => statusMut.mutate({ id: inv.id, status: 'sent' })}>Send</Button>
                              )}
                              {inv.status === 'sent' && (
                                <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={() => statusMut.mutate({ id: inv.id, status: 'paid' })}>Mark Paid</Button>
                              )}
                              {(inv.status === 'sent' || inv.status === 'overdue') && (
                                <Button variant="ghost" size="sm" className="h-6 text-xs text-destructive hover:text-destructive hover:bg-destructive/10" onClick={() => statusMut.mutate({ id: inv.id, status: 'overdue' })}>Overdue</Button>
                              )}
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Ledger Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <h2 className="text-lg font-semibold tracking-tight">Credit Ledger</h2>
              <Button size="sm" onClick={() => setGrantOpen(true)}>Grant Credits</Button>
            </div>
            
            {ledger && (
              <Card>
                <CardContent className="p-0">
                  <Table>
                    <TableHeader>
                      <TableRow className="hover:bg-transparent bg-muted/20">
                        <TableHead className="text-xs">Date</TableHead>
                        <TableHead className="text-xs">Type</TableHead>
                        <TableHead className="text-xs text-right">Amount</TableHead>
                        <TableHead className="text-xs">Reference</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {ledger.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={4} className="text-center text-sm text-muted-foreground py-8">
                            No ledger entries found.
                          </TableCell>
                        </TableRow>
                      ) : (
                        ledger.map((e) => (
                          <TableRow key={e.id}>
                            <TableCell className="text-xs">{new Date(e.created_at).toLocaleString()}</TableCell>
                            <TableCell><Badge variant={e.type === 'consume' ? 'destructive' : 'default'} className="text-[10px] uppercase">{e.type}</Badge></TableCell>
                            <TableCell className={`text-xs text-right font-medium ${e.type === 'consume' ? 'text-destructive' : 'text-green-600'}`}>
                              {e.type === 'consume' ? '-' : '+'}${(Math.abs(e.amount_cents) / 100).toFixed(2)}
                            </TableCell>
                            <TableCell className="text-xs font-mono text-muted-foreground">{e.reference_id || '—'}</TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* Grant Credits Dialog */}
      <Dialog open={grantOpen} onOpenChange={setGrantOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader><DialogTitle>Grant Credits</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label>Amount ($)</Label>
              <Input type="number" step="0.01" value={grantAmount} onChange={(e) => setGrantAmount(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Reference (optional)</Label>
              <Input value={grantRef} onChange={(e) => setGrantRef(e.target.value)} placeholder="e.g. manual-grant-2024" />
            </div>
          </div>
          <DialogFooter className="pt-2">
            <Button disabled={grantMut.isPending || !grantAmount} onClick={() => grantMut.mutate()}>
              {grantMut.isPending ? 'Granting…' : 'Grant'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Generate Invoice Dialog */}
      <Dialog open={genOpen} onOpenChange={setGenOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader><DialogTitle>Generate Invoice</DialogTitle></DialogHeader>
          <div className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label>Billing Period End</Label>
              <Input type="date" value={genEnd} onChange={(e) => setGenEnd(e.target.value)} />
            </div>
          </div>
          <DialogFooter className="pt-2">
            <Button disabled={genMut.isPending || !genEnd} onClick={() => genMut.mutate()}>
              {genMut.isPending ? 'Generating…' : 'Generate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  );
}
