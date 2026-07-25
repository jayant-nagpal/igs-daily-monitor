/* ============================================================
   Formatters — numeric display helpers.
   All numbers render in JetBrains Mono via the .mono class.

   Rules (per spec):
   - null / undefined / NaN  ->  "—"
   - ₹ prefix for rupee P&L
   - tabular numbers (mono font)
   - negative-zero: if abs(value) < 0.00005 display 0.00% UNLESS the source is
     explicitly negative zero (Object.is(value, -0)), in which case keep "-0.00%".
   ============================================================ */

const DASH = '—';

function isNil(v: number | null | undefined): v is null | undefined {
  return v === null || v === undefined || Number.isNaN(v as number);
}

export function formatPct(value: number | null | undefined, decimals = 2): string {
  if (isNil(value)) return DASH;
  const v = value as number;
  // preserve an explicit negative zero coming from the pipeline (-0.00%)
  if (Object.is(v, -0)) return `-${(0).toFixed(decimals)}%`;
  if (Math.abs(v) < 0.00005) return `${(0).toFixed(decimals)}%`;
  return `${v.toFixed(decimals)}%`;
}

export function formatRs(value: number | null | undefined): string {
  if (isNil(value)) return DASH;
  const v = value as number;
  const abs = Math.abs(v);
  const sign = v < 0 && !Object.is(v, -0) ? '-' : '';
  const formatted = abs.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${sign}₹${formatted}`;
}

/** Compact ₹ with Indian Cr / L / K suffixes for KPI cards. */
export function formatRsCompact(value: number | null | undefined): string {
  if (isNil(value)) return DASH;
  const v = value as number;
  const abs = Math.abs(v);
  const sign = v < 0 && !Object.is(v, -0) ? '-' : '';
  if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(2)} Cr`;
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(2)} L`;
  if (abs >= 1e3) return `${sign}₹${(abs / 1e3).toFixed(1)} K`;
  return `${sign}₹${abs.toFixed(2)}`;
}

export function formatNumber(value: number | null | undefined, decimals?: number): string {
  if (isNil(value)) return DASH;
  return (value as number).toLocaleString('en-IN', {
    minimumFractionDigits: decimals ?? 0,
    maximumFractionDigits: decimals ?? 2,
  });
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return DASH;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

/** Format a datetime with time, e.g. "06 Jul 2026, 18:30". */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return DASH;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Prefix a "+" on positive numbers. */
export function formatSigned(
  value: number | null | undefined,
  fmt: (v: number) => string = (v) => v.toFixed(2),
): string {
  if (isNil(value)) return DASH;
  const v = value as number;
  const s = fmt(Math.abs(v));
  if (v > 0) return `+${s}`;
  if (v < 0 && !Object.is(v, -0)) return `-${s}`;
  return s;
}

/** Return a className fragment ('pos' | 'neg' | '') for sign coloring. */
export function colorClassBySign(value: number | null | undefined): string {
  if (isNil(value)) return '';
  const v = value as number;
  if (v > 0) return 'pos';
  if (v < 0 && !Object.is(v, -0)) return 'neg';
  return '';
}

// backward-compatible alias used by some components
export const colorBySign = colorClassBySign;
