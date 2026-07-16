import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getAdminInvoice } from '@/services/admin';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft } from 'lucide-react';

export default function AdminInvoiceDetail() {
  const { invoiceId } = useParams<{ invoiceId: string }>();

  const { data: invoice, isLoading } = useQuery({
    queryKey: ['admin', 'invoice', invoiceId],
    queryFn: () => getAdminInvoice(invoiceId!),
    enabled: !!invoiceId,
  });

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-48" /><Skeleton className="h-64" /></div>;
  if (!invoice) return <div className="text-sm text-muted-foreground">Invoice not found.</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" className="h-7 w-7" asChild>
          <Link to="/admin/billing"><ArrowLeft className="h-4 w-4" /></Link>
        </Button>
        <h1 className="text-lg font-semibold">Invoice {invoice.id}</h1>
        <Badge variant={invoice.status === 'paid' ? 'default' : 'secondary'} className="text-[10px]">
          {invoice.status}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Period</CardTitle></CardHeader>
          <CardContent className="text-sm">
            {new Date(invoice.billing_period_start).toLocaleDateString()} – {new Date(invoice.billing_period_end).toLocaleDateString()}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Amount Due</CardTitle></CardHeader>
          <CardContent className="text-sm font-medium">
            ${(invoice.amount_due / 100).toFixed(2)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Created At</CardTitle></CardHeader>
          <CardContent className="text-sm">
            {new Date(invoice.created_at).toLocaleDateString()}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-sm">Line Items</CardTitle></CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">Product</TableHead>
                <TableHead className="text-xs">Action</TableHead>
                <TableHead className="text-xs text-right">Quantity</TableHead>
                <TableHead className="text-xs text-right">Amount</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoice.line_items?.map((item: any, idx: number) => (
                <TableRow key={idx}>
                  <TableCell className="text-xs">{item.product_name || item.product_key}</TableCell>
                  <TableCell className="text-xs font-mono">{item.action_key}</TableCell>
                  <TableCell className="text-xs text-right">{item.quantity}</TableCell>
                  <TableCell className="text-xs text-right font-medium">${(item.amount_cents / 100).toFixed(2)}</TableCell>
                </TableRow>
              ))}
              {(!invoice.line_items || invoice.line_items.length === 0) && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-xs text-muted-foreground py-6">
                    No line items found.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
