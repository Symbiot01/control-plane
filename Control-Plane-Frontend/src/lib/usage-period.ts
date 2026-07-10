import { addDays, format } from 'date-fns';

/** Inclusive end date → exclusive period end at start of next day (UTC) for API half-open [from, to). */
export function customRangeToParams(fromYmd: string, toYmdInclusive: string) {
  const from = `${fromYmd}T00:00:00.000Z`;
  const endExclusive = addDays(new Date(`${toYmdInclusive}T00:00:00.000Z`), 1);
  const to = endExclusive.toISOString();
  return { from, to };
}

export function defaultUsageDateState() {
  return {
    fromYmd: format(addDays(new Date(), -30), 'yyyy-MM-dd'),
    toYmdInclusive: format(new Date(), 'yyyy-MM-dd'),
  };
}
