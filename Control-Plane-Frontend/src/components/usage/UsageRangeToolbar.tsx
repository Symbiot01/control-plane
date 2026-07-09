import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export type UsageRangeMode = 'default' | 'custom';

export function UsageRangeToolbar({
  rangeMode,
  setRangeMode,
  fromYmd,
  setFromYmd,
  toYmdInclusive,
  setToYmdInclusive,
}: {
  rangeMode: UsageRangeMode;
  setRangeMode: (m: UsageRangeMode) => void;
  fromYmd: string;
  setFromYmd: (v: string) => void;
  toYmdInclusive: string;
  setToYmdInclusive: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="space-y-1.5">
        <Label className="text-xs">Range</Label>
        <div className="flex gap-2">
          <Button
            type="button"
            variant={rangeMode === 'default' ? 'default' : 'outline'}
            size="sm"
            className="h-8 text-xs"
            onClick={() => setRangeMode('default')}
          >
            Last 30 days (API default)
          </Button>
          <Button
            type="button"
            variant={rangeMode === 'custom' ? 'default' : 'outline'}
            size="sm"
            className="h-8 text-xs"
            onClick={() => setRangeMode('custom')}
          >
            Custom (UTC dates)
          </Button>
        </div>
      </div>
      {rangeMode === 'custom' && (
        <>
          <div className="space-y-1.5">
            <Label className="text-xs">From (inclusive)</Label>
            <Input
              type="date"
              value={fromYmd}
              onChange={(e) => setFromYmd(e.target.value)}
              className="h-8 text-xs w-40"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">To (inclusive)</Label>
            <Input
              type="date"
              value={toYmdInclusive}
              onChange={(e) => setToYmdInclusive(e.target.value)}
              className="h-8 text-xs w-40"
            />
          </div>
        </>
      )}
    </div>
  );
}
