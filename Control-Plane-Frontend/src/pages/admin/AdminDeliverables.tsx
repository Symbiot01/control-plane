import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getAdminDeliverables,
  createAdminDeliverable,
  updateAdminDeliverable,
  deleteAdminDeliverable
} from '@/services/admin';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { toast } from '@/hooks/use-toast';
import { Skeleton } from '@/components/ui/skeleton';
import { Plus, Trash2, Edit2, Globe } from 'lucide-react';
import type { DeliverableCreate, DeliverableUpdate, DeliverableResponse } from '@/types/api';

function DeliverableEditDialog({
  deliverable,
  onClose,
  open
}: {
  deliverable: DeliverableResponse;
  onClose: () => void;
  open: boolean;
}) {
  const qc = useQueryClient();
  const [formData, setFormData] = useState({
    name: deliverable.name,
    description: deliverable.description || '',
    deliverable_link: deliverable.deliverable_link || '',
  });

  const updateMut = useMutation({
    mutationFn: (data: DeliverableUpdate) => updateAdminDeliverable(deliverable.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'deliverables'] });
      toast({ title: 'Deliverable updated' });
      onClose();
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' })
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      name: formData.name,
      description: formData.description || null,
      deliverable_link: formData.deliverable_link?.trim() || null,
    };
    updateMut.mutate(payload);
  };

  return (
    <Dialog open={open} onOpenChange={(val) => { if (!val) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Deliverable</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          <div className="space-y-2">
            <Label htmlFor="edit_name">Deliverable Name</Label>
            <Input
              id="edit_name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit_description">Description (optional)</Label>
            <Textarea
              id="edit_description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit_link">Application Link (optional)</Label>
            <Input
              id="edit_link"
              value={formData.deliverable_link}
              onChange={(e) => setFormData({ ...formData, deliverable_link: e.target.value })}
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateMut.isPending || !formData.name}>
              Save Changes
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DeliverableCard({ deliverable }: { deliverable: DeliverableResponse }) {
  const qc = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteAdminDeliverable(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'deliverables'] });
      toast({ title: 'Deliverable deleted' });
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const handleDelete = () => {
    if (confirm('Are you sure you want to delete this deliverable?')) {
      deleteMut.mutate(deliverable.id);
    }
  };

  return (
    <>
      <Card className="flex flex-col h-[280px] shadow-sm hover:shadow-md transition-shadow group/card overflow-hidden">
        <CardHeader className="pb-4 border-b border-border/10 bg-muted/5 shrink-0">
          <div className="flex items-start justify-between">
            <div className="flex flex-col gap-1.5">
              <CardTitle className="text-lg font-semibold tracking-tight text-foreground/90">
                {deliverable.name}
              </CardTitle>
              {deliverable.deliverable_link && (
                <a href={deliverable.deliverable_link.startsWith('http') ? deliverable.deliverable_link : `https://${deliverable.deliverable_link}`} target="_blank" rel="noopener noreferrer" className="text-[11px] text-muted-foreground hover:text-primary flex items-center gap-1 w-fit transition-colors group-hover/card:text-primary/70">
                  <Globe className="h-3 w-3" /> {deliverable.deliverable_link.replace(/^https?:\/\//, '')}
                </a>
              )}
            </div>
            <div className="flex items-center gap-1 opacity-0 group-hover/card:opacity-100 transition-opacity">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                onClick={() => setEditOpen(true)}
                title="Edit Deliverable"
              >
                <Edit2 className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                onClick={handleDelete}
                disabled={deleteMut.isPending}
                title="Delete Deliverable"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col gap-4 pt-5 overflow-hidden">
          {deliverable.description && (
            <p className="text-sm text-muted-foreground/80 line-clamp-4 leading-relaxed shrink-0">
              {deliverable.description}
            </p>
          )}
        </CardContent>
      </Card>

      {editOpen && (
        <DeliverableEditDialog
          open={editOpen}
          onClose={() => setEditOpen(false)}
          deliverable={deliverable}
        />
      )}
    </>
  );
}

export default function AdminDeliverables() {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newDeliverable, setNewDeliverable] = useState<DeliverableCreate>({ name: '', description: '', deliverable_link: '' });
  const qc = useQueryClient();

  const { data: deliverables, isLoading, isError, error } = useQuery({
    queryKey: ['admin', 'deliverables'],
    queryFn: getAdminDeliverables,
  });

  const createMut = useMutation({
    mutationFn: (data: DeliverableCreate) => createAdminDeliverable(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'deliverables'] });
      toast({ title: 'Deliverable created' });
      setIsCreateOpen(false);
      setNewDeliverable({ name: '', description: '', deliverable_link: '' });
    },
    onError: (err: Error) => {
      toast({ title: 'Error', description: err.message, variant: 'destructive' });
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDeliverable.name) return;
    
    const payload: DeliverableCreate = {
      ...newDeliverable,
      deliverable_link: newDeliverable.deliverable_link?.trim() || null
    };
    
    createMut.mutate(payload);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Deliverables</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage grouped products and deliverables for organizations.</p>
        </div>
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="mr-2 h-4 w-4" /> Create Deliverable
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Deliverable</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label htmlFor="name">Deliverable Name</Label>
                <Input
                  id="name"
                  placeholder="e.g. Core App Suite"
                  value={newDeliverable.name}
                  onChange={(e) => setNewDeliverable({ ...newDeliverable, name: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description (optional)</Label>
                <Textarea
                  id="description"
                  placeholder="A brief description of this deliverable..."
                  value={newDeliverable.description || ''}
                  onChange={(e) => setNewDeliverable({ ...newDeliverable, description: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="deliverable_link">Application Link (optional)</Label>
                <Input
                  id="deliverable_link"
                  placeholder="e.g. https://my-app.com"
                  value={newDeliverable.deliverable_link || ''}
                  onChange={(e) => setNewDeliverable({ ...newDeliverable, deliverable_link: e.target.value })}
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createMut.isPending || !newDeliverable.name}>
                  Create
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Skeleton className="h-[280px] w-full" />
          <Skeleton className="h-[280px] w-full" />
          <Skeleton className="h-[280px] w-full" />
        </div>
      ) : isError ? (
        <div className="p-4 text-sm text-destructive bg-destructive/10 rounded-md border border-destructive/20">
          Failed to load deliverables: {error?.message}
        </div>
      ) : !deliverables || deliverables.length === 0 ? (
        <div className="p-12 text-sm text-muted-foreground text-center bg-muted/20 border rounded-md border-dashed">
          No deliverables found. Create one to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {deliverables.map((d) => (
            <DeliverableCard key={d.id} deliverable={d} />
          ))}
        </div>
      )}
    </div>
  );
}
