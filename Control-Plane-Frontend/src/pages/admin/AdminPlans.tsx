import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getAdminPlans, createPlan, updatePlan } from '@/services/admin';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { toast } from '@/hooks/use-toast';
import { Plus } from 'lucide-react';

export default function AdminPlans() {
  const qc = useQueryClient();
  const { data: plans, isLoading } = useQuery({ queryKey: ['admin', 'plans'], queryFn: getAdminPlans });

  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [price, setPrice] = useState('');
  const [units, setUnits] = useState('');
  const [overage, setOverage] = useState('');

  const createMut = useMutation({
    mutationFn: () => createPlan({
      name,
      monthly_price: Math.round(parseFloat(price) * 100),
      included_compute_units: parseInt(units),
      overage_rate: Math.round(parseFloat(overage) * 100),
      currency: 'USD',
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'plans'] });
      toast({ title: 'Plan created' });
      setOpen(false);
      setName(''); setPrice(''); setUnits(''); setOverage('');
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-32" /><Skeleton className="h-64" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Plans</h1>
        <Button size="sm" className="h-8 text-xs" onClick={() => setOpen(true)}>
          <Plus className="h-3.5 w-3.5 mr-1" /> New Plan
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">Name</TableHead>
                <TableHead className="text-xs text-right">Monthly Price</TableHead>
                <TableHead className="text-xs text-right">Included Units</TableHead>
                <TableHead className="text-xs text-right">Overage Rate</TableHead>
                <TableHead className="text-xs">Currency</TableHead>
                <TableHead className="text-xs">Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {plans?.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="text-xs font-medium">{p.name}</TableCell>
                  <TableCell className="text-xs text-right">${(p.monthly_price / 100).toFixed(2)}</TableCell>
                  <TableCell className="text-xs text-right">{p.included_compute_units.toLocaleString()}</TableCell>
                  <TableCell className="text-xs text-right">${(p.overage_rate / 100).toFixed(2)}</TableCell>
                  <TableCell className="text-xs">{p.currency}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{new Date(p.created_at).toLocaleDateString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader><DialogTitle className="text-sm">Create Plan</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Name</Label>
              <Input className="h-8 text-xs" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Monthly Price ($)</Label>
              <Input type="number" step="0.01" className="h-8 text-xs" value={price} onChange={(e) => setPrice(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Included Compute Units</Label>
              <Input type="number" className="h-8 text-xs" value={units} onChange={(e) => setUnits(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Overage Rate ($/unit)</Label>
              <Input type="number" step="0.01" className="h-8 text-xs" value={overage} onChange={(e) => setOverage(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button size="sm" className="text-xs" disabled={createMut.isPending} onClick={() => createMut.mutate()}>
              {createMut.isPending ? 'Creating…' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
