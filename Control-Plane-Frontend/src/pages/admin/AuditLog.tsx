import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getAuditLog } from '@/services/admin';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';

export default function AuditLog() {
  const [search, setSearch] = useState('');

  const { data: entries, isLoading } = useQuery({
    queryKey: ['admin', 'audit'],
    queryFn: () => getAuditLog(),
  });

  const filtered = entries?.filter((e) =>
    !search ||
    e.action.toLowerCase().includes(search.toLowerCase()) ||
    e.actor_email?.toLowerCase().includes(search.toLowerCase()) ||
    (e.target_type && e.target_type.toLowerCase().includes(search.toLowerCase()))
  );

  if (isLoading) return <div className="space-y-4"><Skeleton className="h-8 w-32" /><Skeleton className="h-64" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Audit Log</h1>
        <Input
          placeholder="Filter by action, actor, resource…"
          className="h-8 text-xs w-64"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">Timestamp</TableHead>
                <TableHead className="text-xs">Actor</TableHead>
                <TableHead className="text-xs">Action</TableHead>
                <TableHead className="text-xs">Resource</TableHead>
                <TableHead className="text-xs">Resource ID</TableHead>
                <TableHead className="text-xs">Details</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(!filtered || filtered.length === 0) ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-xs text-muted-foreground py-8">
                    No audit log entries
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell className="text-xs text-muted-foreground">{new Date(e.created_at).toLocaleString()}</TableCell>
                    <TableCell className="text-xs">{e.actor_email || e.admin_member_id.slice(0, 8)}</TableCell>
                    <TableCell className="text-xs font-mono">{e.action}</TableCell>
                    <TableCell className="text-xs">{e.target_type || '—'}</TableCell>
                    <TableCell className="text-xs font-mono text-muted-foreground">{e.target_id ? `${e.target_id.slice(0, 8)}…` : '—'}</TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate">
                      {e.detail ? e.detail : '—'}
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
