import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getAdminProducts,
  createAdminProduct,
  updateAdminProduct,
  deleteAdminProduct,
  getAdminActions,
  createAdminAction,
  updateAdminAction,
  deleteAdminAction,
  getAdminDeliverables
} from '@/services/admin';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { toast } from '@/hooks/use-toast';
import { Skeleton } from '@/components/ui/skeleton';
import { Plus, Trash2, Edit2, Globe } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { ProductCreate, ProductUpdate, ProductResponse, ActionResponse, ActionCreate, ActionUpdate, DeliverableResponse } from '@/types/api';

function ServiceDialog({ 
  product, 
  actionToEdit,
  allActions,
  onClose,
  open
}: { 
  product: ProductResponse; 
  actionToEdit: ActionResponse | null; 
  allActions: ActionResponse[];
  onClose: () => void;
  open: boolean;
}) {
  const qc = useQueryClient();
  const [formData, setFormData] = useState({
    name: actionToEdit?.name || '',
    action_key: actionToEdit?.action_key || '',
    domain: actionToEdit?.domain || '',
    unit_type: actionToEdit?.unit_type || '',
    description: actionToEdit?.description || '',
    rate_cents_per_compute_unit: actionToEdit?.rate_cents_per_compute_unit?.toString() || '0',
    is_active: actionToEdit ? actionToEdit.is_active : true,
  });

  const createMut = useMutation({
    mutationFn: (data: ActionCreate) => createAdminAction(data),
    onSuccess: () => { 
      qc.invalidateQueries({ queryKey: ['admin', 'actions'] }); 
      toast({ title: 'Service created' }); 
      onClose(); 
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' })
  });

  const updateMut = useMutation({
    mutationFn: ({ key, data }: { key: string, data: ActionUpdate }) => updateAdminAction(key, data),
    onSuccess: () => { 
      qc.invalidateQueries({ queryKey: ['admin', 'actions'] }); 
      toast({ title: 'Service updated' }); 
      onClose(); 
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' })
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name || !formData.action_key) return;
    
    if (actionToEdit) {
      updateMut.mutate({
        key: formData.action_key,
        data: {
          description: formData.description || undefined,
          rate_cents_per_compute_unit: parseInt(formData.rate_cents_per_compute_unit, 10) || 0,
          is_active: formData.is_active
        }
      });
    } else {
      createMut.mutate({
        name: formData.name,
        action_key: formData.action_key,
        product_id: product.id,
        domain: formData.domain,
        unit_type: formData.unit_type
      });
    }
  };

  const isPending = createMut.isPending || updateMut.isPending;

  return (
    <Dialog open={open} onOpenChange={(val) => { if (!val) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {actionToEdit ? 'Edit Service' : 'Create New Service'}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          
          {!actionToEdit && (
            <>
              <div className="space-y-2">
                <Label htmlFor="name">Service Name</Label>
                <Input
                  id="name"
                  placeholder="e.g. OCR Processing"
                  value={formData.name}
                  onChange={(e) => {
                    const newName = e.target.value;
                    const newKey = newName.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
                    setFormData({ ...formData, name: newName, action_key: newKey });
                  }}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="key">Service Key</Label>
                <Input
                  id="key"
                  placeholder="auto-generated"
                  value={formData.action_key}
                  readOnly
                  className="bg-muted/50 text-muted-foreground font-mono text-xs"
                />
                <p className="text-[10px] text-muted-foreground">Auto-generated from the service name.</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="domain">Domain</Label>
                <Input
                  id="domain"
                  placeholder="e.g. compute, storage"
                  value={formData.domain}
                  onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="unit_type">Unit Type</Label>
                <Input
                  id="unit_type"
                  placeholder="e.g. gigabytes, requests"
                  value={formData.unit_type}
                  onChange={(e) => setFormData({ ...formData, unit_type: e.target.value })}
                  required
                />
              </div>
            </>
          )}
              
              <div className="space-y-2">
                <Label htmlFor="description">Description (optional)</Label>
                <Textarea
                  id="description"
                  placeholder="Brief description of this service..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-1.5">
                  <Label htmlFor="price">Price Rate</Label>
                  <Badge variant="outline" className="text-[10px] font-mono text-muted-foreground">cents / compute unit</Badge>
                </div>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-muted-foreground text-sm">¢</span>
                  <Input
                    id="price"
                    type="number"
                    min="0"
                    className="pl-7"
                    placeholder="0"
                    value={formData.rate_cents_per_compute_unit}
                    onChange={(e) => setFormData({ ...formData, rate_cents_per_compute_unit: e.target.value })}
                    required
                  />
                </div>
              </div>
              
              {actionToEdit && (
                <div className="flex items-center justify-between p-3 border rounded-lg bg-muted/20">
                  <div className="space-y-0.5">
                    <Label>Active Status</Label>
                    <p className="text-xs text-muted-foreground">Is this service active and available?</p>
                  </div>
                  <Switch
                    checked={formData.is_active}
                    onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                  />
                </div>
              )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending || (!actionToEdit && (!formData.name || !formData.action_key))}>
              {actionToEdit ? 'Save Changes' : 'Create Service'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ProductEditDialog({
  product,
  onClose,
  open,
  deliverables
}: {
  product: ProductResponse;
  onClose: () => void;
  open: boolean;
  deliverables: DeliverableResponse[];
}) {
  const qc = useQueryClient();
  const [formData, setFormData] = useState({
    name: product.name,
    description: product.description || '',
    deliverable_id: product.deliverable_id || 'none',
    is_active: product.is_active !== undefined ? product.is_active : true,
  });

  const updateMut = useMutation({
    mutationFn: (data: ProductUpdate) => updateAdminProduct(product.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'products'] });
      toast({ title: 'Product updated' });
      onClose();
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' })
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      name: formData.name,
      description: formData.description || null,
      deliverable_id: formData.deliverable_id === 'none' ? null : formData.deliverable_id,
      is_active: formData.is_active
    };
    updateMut.mutate(payload);
  };

  return (
    <Dialog open={open} onOpenChange={(val) => { if (!val) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Product</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          <div className="space-y-2">
            <Label htmlFor="edit_name">Product Name</Label>
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
            <Label htmlFor="edit_link">Assigned Deliverable (optional)</Label>
            <Select
              value={formData.deliverable_id}
              onValueChange={(val) => setFormData({ ...formData, deliverable_id: val })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a Deliverable" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">None</SelectItem>
                {deliverables?.map(d => (
                  <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center justify-between p-3 border rounded-lg bg-muted/20">
            <div className="space-y-0.5">
              <Label>Active Status</Label>
              <p className="text-xs text-muted-foreground">Is this product active?</p>
            </div>
            <Switch
              checked={formData.is_active}
              onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
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

function ProductCard({ product, actions, deliverables }: { product: ProductResponse; actions: ActionResponse[]; deliverables: DeliverableResponse[] }) {
  const qc = useQueryClient();
  const [serviceDialogOpen, setServiceDialogOpen] = useState(false);
  const [productEditOpen, setProductEditOpen] = useState(false);
  const [editingAction, setEditingAction] = useState<ActionResponse | null>(null);

  const deliverable = deliverables.find(d => d.id === product.deliverable_id);

  const deleteProductMut = useMutation({
    mutationFn: (id: string) => deleteAdminProduct(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'products'] });
      toast({ title: 'Product deleted' });
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const deleteActionMut = useMutation({
    mutationFn: (actionKey: string) => deleteAdminAction(actionKey),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'actions'] });
      toast({ title: 'Service deleted' });
    },
    onError: (err: Error) => toast({ title: 'Error', description: err.message, variant: 'destructive' }),
  });

  const productActions = actions.filter((a) => a.product_id === product.id || a.product_id === product.product_key);

  const handleDeleteProduct = () => {
    if (confirm('Are you sure you want to delete this product?')) {
      deleteProductMut.mutate(product.id);
    }
  };

  const handleEditService = (action: ActionResponse) => {
    setEditingAction(action);
    setServiceDialogOpen(true);
  };

  const handleAddService = () => {
    setEditingAction(null);
    setServiceDialogOpen(true);
  };

  const handleDeleteService = (actionKey: string) => {
    if (confirm('Are you sure you want to delete this service?')) {
      deleteActionMut.mutate(actionKey);
    }
  };

  return (
    <>
      <Card className="flex flex-col h-[380px] shadow-sm hover:shadow-md transition-shadow group/card overflow-hidden">
        <CardHeader className="pb-4 border-b border-border/10 bg-muted/5 shrink-0">
          <div className="flex items-start justify-between">
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                <CardTitle className="text-lg font-semibold tracking-tight text-foreground/90">
                  {product.name}
                </CardTitle>
                <span className="font-mono text-[10px] text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded-md border border-border/30">
                  {product.product_key}
                </span>
                {product.is_active === false && (
                  <Badge variant="outline" className="text-[9px] uppercase border-destructive/50 text-destructive px-1 py-0 h-4">Inactive</Badge>
                )}
              </div>
              {deliverable && (
                <div className="text-[11px] text-muted-foreground flex items-center gap-1 w-fit transition-colors group-hover/card:text-primary/70">
                  <Globe className="h-3 w-3" /> Part of: {deliverable.name}
                </div>
              )}
            </div>
            <div className="flex items-center gap-1 opacity-0 group-hover/card:opacity-100 transition-opacity">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                onClick={() => setProductEditOpen(true)}
                title="Edit Product"
              >
                <Edit2 className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                onClick={handleDeleteProduct}
                disabled={deleteProductMut.isPending}
                title="Delete Product"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col gap-4 pt-5 overflow-hidden">
          {product.description && (
            <p className="text-sm text-muted-foreground/80 line-clamp-2 leading-relaxed shrink-0">
              {product.description}
            </p>
          )}

          <div className="flex flex-col gap-2 flex-1 overflow-hidden">
            <div className="flex items-center justify-between pb-1 shrink-0">
              <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
                Services ({productActions.length})
              </h4>
              <Button variant="ghost" size="sm" className="h-6 text-[10px] font-medium text-primary hover:text-primary hover:bg-primary/10 px-2 rounded-sm" onClick={handleAddService}>
                <Plus className="h-3 w-3 mr-1" /> Add
              </Button>
            </div>
            
            <div className="space-y-0.5 flex-1 overflow-y-auto no-scrollbar">
              {productActions.length === 0 ? (
                <div className="text-xs text-muted-foreground/50 italic py-2">
                  No services configured.
                </div>
              ) : (
                productActions.map((action) => (
                  <div key={action.id} className="flex items-center justify-between py-1.5 px-2 -mx-2 rounded-md hover:bg-muted/40 transition-colors group/service">
                    <div className="flex items-center gap-2.5">
                      <div className={`w-1.5 h-1.5 rounded-full ${action.is_active ? 'bg-primary/70' : 'bg-muted-foreground/40'}`} title={action.is_active ? 'Active' : 'Inactive'} />
                      <span className="text-[13px] text-foreground/90 font-medium">{action.name || action.action_key}</span>
                      <span className="text-[10px] font-mono text-muted-foreground/50 hidden sm:inline-block">{action.action_key}</span>
                    </div>
                    <div className="flex items-center gap-0.5 opacity-0 group-hover/service:opacity-100 transition-opacity">
                      <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground" onClick={() => handleEditService(action)}>
                        <Edit2 className="h-3 w-3" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-destructive hover:bg-destructive/10" onClick={() => handleDeleteService(action.action_key)} disabled={deleteActionMut.isPending} title="Delete Service">
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {serviceDialogOpen && (
        <ServiceDialog
          open={serviceDialogOpen}
          onClose={() => setServiceDialogOpen(false)}
          product={product}
          actionToEdit={editingAction}
          allActions={actions}
        />
      )}
      {productEditOpen && (
        <ProductEditDialog
          open={productEditOpen}
          onClose={() => setProductEditOpen(false)}
          product={product}
          deliverables={deliverables}
        />
      )}
    </>
  );
}

export default function AdminProducts() {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newProduct, setNewProduct] = useState<ProductCreate>({ name: '', product_key: '', description: '', deliverable_id: 'none' });
  const qc = useQueryClient();

  const { data: products, isLoading: productsLoading, isError, error } = useQuery({
    queryKey: ['admin', 'products'],
    queryFn: getAdminProducts,
  });

  const { data: actions, isLoading: actionsLoading } = useQuery({
    queryKey: ['admin', 'actions'],
    queryFn: getAdminActions,
  });

  const { data: deliverables, isLoading: deliverablesLoading } = useQuery({
    queryKey: ['admin', 'deliverables'],
    queryFn: getAdminDeliverables,
  });

  const createMut = useMutation({
    mutationFn: (data: ProductCreate) => createAdminProduct(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'products'] });
      toast({ title: 'Product created' });
      setIsCreateOpen(false);
      setNewProduct({ name: '', product_key: '', description: '', deliverable_id: 'none' });
    },
    onError: (err: Error) => {
      toast({ title: 'Error', description: err.message, variant: 'destructive' });
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProduct.name || !newProduct.product_key) return;
    
    const payload: ProductCreate = {
      ...newProduct,
      deliverable_id: newProduct.deliverable_id === 'none' ? null : newProduct.deliverable_id
    };
    
    createMut.mutate(payload);
  };

  const isLoading = productsLoading || actionsLoading || deliverablesLoading;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Products & Services</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage platform products and their underlying billing services.</p>
        </div>
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="mr-2 h-4 w-4" /> Create Product
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Product</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label htmlFor="name">Product Name</Label>
                <Input
                  id="name"
                  placeholder="e.g. Premium Analytics"
                  value={newProduct.name}
                  onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="key">Product Key</Label>
                <Input
                  id="key"
                  placeholder="e.g. premium_analytics"
                  value={newProduct.product_key}
                  onChange={(e) => setNewProduct({ ...newProduct, product_key: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description (optional)</Label>
                <Textarea
                  id="description"
                  placeholder="A brief description of this product..."
                  value={newProduct.description || ''}
                  onChange={(e) => setNewProduct({ ...newProduct, description: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="deliverable_id">Assigned Deliverable (optional)</Label>
                <Select
                  value={newProduct.deliverable_id || 'none'}
                  onValueChange={(val) => setNewProduct({ ...newProduct, deliverable_id: val })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a Deliverable" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {deliverables?.map(d => (
                      <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createMut.isPending || !newProduct.name || !newProduct.product_key}>
                  Create
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : isError ? (
        <div className="p-4 text-sm text-destructive bg-destructive/10 rounded-md border border-destructive/20">
          Failed to load products: {error?.message}
        </div>
      ) : !products || products.length === 0 ? (
        <div className="p-12 text-sm text-muted-foreground text-center bg-muted/20 border rounded-md border-dashed">
          No products found. Create one to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {products.map((p) => (
            <ProductCard key={p.id} product={p} actions={actions || []} deliverables={deliverables || []} />
          ))}
        </div>
      )}
    </div>
  );
}
