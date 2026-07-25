/* ============================================================
   Derived metrics — ONLY counts, sums, averages, min/max, top-N,
   and absolute-value ranking. No new financial analytics.
   ============================================================ */
import type {
  DashboardData,
  ExposureRow,
  PriceCostDriftRow,
  SlippageSummary,
} from '../types/dashboard';

// ---- generic reducers ----
export const sum = (nums: (number | null | undefined)[]): number =>
  nums.reduce<number>((a, b) => a + (b ?? 0), 0);

export const avg = (nums: (number | null | undefined)[]): number | null => {
  const vals = nums.filter((n): n is number => n !== null && n !== undefined && !Number.isNaN(n));
  return vals.length ? sum(vals) / vals.length : null;
};

export function topN<T>(rows: T[], key: (r: T) => number | null, n: number, desc = true): T[] {
  return [...rows]
    .filter((r) => key(r) !== null && key(r) !== undefined)
    .sort((a, b) => {
      const av = key(a) ?? 0;
      const bv = key(b) ?? 0;
      return desc ? bv - av : av - bv;
    })
    .slice(0, n);
}

// ---- slippage ----
export const totalTodayModelPnl = (s: SlippageSummary[]): number =>
  sum(s.map((r) => r.todayModelPnl));

export const totalTodayClosePnl = (s: SlippageSummary[]): number =>
  sum(s.map((r) => r.todayClosePnl));

export const avgModelSlippagePct = (s: SlippageSummary[]): number | null =>
  avg(s.map((r) => r.slippageModelIgsPct));

export const avgCloseSlippagePct = (s: SlippageSummary[]): number | null =>
  avg(s.map((r) => r.slippageClosePricePct));

/** Largest cumulative model % by magnitude across algos. */
export const largestCumulativeModelPct = (s: SlippageSummary[]): number | null => {
  const vals = s
    .map((r) => r.cumulativeModelClosePct)
    .filter((v): v is number => v !== null && v !== undefined);
  if (!vals.length) return null;
  return vals.reduce((a, b) => (Math.abs(b) > Math.abs(a) ? b : a));
};

// ---- alerts / risk ----
export const breachCount = (d: DashboardData): number =>
  d.risk.alerts.filter((a) => a.breach === 'Yes').length;

// ---- price / cost drift ----
export const negativeDriftCount = (rows: PriceCostDriftRow[]): number =>
  rows.filter((r) => r.diffResetPriceAvgPricePct < 0).length;

export const positiveDriftCount = (rows: PriceCostDriftRow[]): number =>
  rows.filter((r) => r.diffResetPriceAvgPricePct > 0).length;

export const maxAbsDrift = (rows: PriceCostDriftRow[]): number | null => {
  if (!rows.length) return null;
  return rows.reduce((m, r) => Math.max(m, Math.abs(r.diffResetPriceAvgPricePct)), 0);
};

export const topAbsDrift = (rows: PriceCostDriftRow[], n: number): PriceCostDriftRow[] =>
  topN(rows, (r) => Math.abs(r.diffResetPriceAvgPricePct), n, true);

// ---- exposure ----
export const maxWeight = (rows: ExposureRow[]): number | null => {
  const vals = rows
    .map((r) => r.execWeightPct)
    .filter((v): v is number => v !== null && v !== undefined);
  return vals.length ? Math.max(...vals) : null;
};

export const totalMarketValue = (rows: ExposureRow[]): number =>
  sum(rows.map((r) => r.marketValue));

export const largestGainLossPct = (rows: ExposureRow[]): number | null => {
  const vals = rows
    .map((r) => r.gainLossPct)
    .filter((v): v is number => v !== null && v !== undefined);
  if (!vals.length) return null;
  return vals.reduce((a, b) => (Math.abs(b) > Math.abs(a) ? b : a));
};

export const topExposures = (rows: ExposureRow[], n: number): ExposureRow[] =>
  topN(rows, (r) => r.execWeightPct, n, true);
