import type { UsageSummaryResponse } from '@/types/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

function formatPeriod(start: string, end: string) {
  return `${new Date(start).toLocaleString()} → ${new Date(end).toLocaleString()} (end exclusive)`;
}

export function UsageSummaryPanel({
  data,
  isLoading,
}: {
  data: UsageSummaryResponse | undefined;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">{formatPeriod(data.period_start, data.period_end)}</p>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-muted-foreground font-medium">Total Billable Compute Units</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{data.total_compute_units.toLocaleString()}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-muted-foreground font-medium">Total Raw Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{data.total_units.toLocaleString()}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Compute Units by Action</CardTitle>
        </CardHeader>
        <CardContent className="p-0 sm:p-6 sm:pt-0">
          <div className="h-[300px] w-full pt-4">
            {data.by_action.length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                No metered usage in this period
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.by_action.map(r => ({
                    name: r.action_key || (r.action_id ? `${r.action_id.slice(0, 8)}…` : '—'),
                    computeUnits: r.compute_units,
                  }))}
                  margin={{ top: 20, right: 30, left: 0, bottom: 25 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                  <XAxis 
                    dataKey="name" 
                    tickLine={false} 
                    axisLine={false} 
                    tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} 
                    dy={10}
                    angle={-45}
                    textAnchor="end"
                  />
                  <YAxis 
                    tickLine={false} 
                    axisLine={false} 
                    tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                    tickFormatter={(value) => value.toLocaleString()}
                  />
                  <RechartsTooltip 
                    cursor={{ fill: "hsl(var(--muted))" }}
                    contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "8px", color: "hsl(var(--foreground))" }}
                    formatter={(value: number) => [value.toLocaleString(), 'Compute Units']}
                  />
                  <Bar dataKey="computeUnits" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
