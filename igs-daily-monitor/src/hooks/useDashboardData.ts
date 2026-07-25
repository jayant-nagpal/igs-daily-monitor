import { useCallback, useEffect, useRef, useState } from 'react';
import type { DashboardData, DashboardState } from '../types/dashboard';
import { sampleData } from '../data/sampleData';

// ------------------------------------------------------------
// Fetch priority (sibling pipeline data — never email HTML):
//   1. VITE_DASHBOARD_DATA_URL  (hosted latest.json)
//   2. /data/latest.json        (local pipeline export copied into public/data)
//   3. bundled sampleData.ts    (amber "Sample fallback" state)
//
// Every fetch is cache-busted (?t=Date.now(), cache:'no-store'). The dashboard
// auto-refreshes every 30 minutes and exposes a manual refresh(). A failed
// fetch is surfaced as an amber warning — never a silent swap to sample.
//
// Refresh cadence is 30 minutes to match the intraday pipeline, which publishes
// a new latest.json every 30 minutes (see scripts/windows/install_scheduler.bat).
// Override at build time with VITE_DASHBOARD_POLL_MS if a different cadence is needed.
// ------------------------------------------------------------

const POLL_MS = Number(import.meta.env.VITE_DASHBOARD_POLL_MS) || 30 * 60 * 1000;
const ENV_URL = import.meta.env.VITE_DASHBOARD_DATA_URL as string | undefined;
const PUBLIC_URL = `${import.meta.env.BASE_URL || '/'}data/latest.json`.replace(/\/\/data/, '/data');

function bust(url: string): string {
  return url + (url.includes('?') ? '&' : '?') + 't=' + Date.now();
}

function normalize(raw: unknown): DashboardData {
  const d = raw as Partial<DashboardData>;
  return {
    schemaVersion: d.schemaVersion,
    runId: d.runId,
    businessDate: d.businessDate ?? sampleData.businessDate,
    generatedAt: d.generatedAt ?? sampleData.generatedAt,
    source: {
      mode: d.source?.mode ?? 'sample',
      pipelineEntryPoint: d.source?.pipelineEntryPoint,
      inputTimestamp: d.source?.inputTimestamp,
      inputFiles: d.source?.inputFiles ?? [],
      notes: d.source?.notes ?? [],
    },
    slippage: {
      summary: d.slippage?.summary ?? [],
      algos: d.slippage?.algos ?? [],
    },
    risk: {
      alerts: d.risk?.alerts ?? [],
      zScores: d.risk?.zScores ?? {},
      stopLossWatch: d.risk?.stopLossWatch ?? [],
      priceCostDrift: d.risk?.priceCostDrift ?? [],
      exposure: d.risk?.exposure ?? [],
    },
    dataHealth: recomputeHealth(d),
  };
}

function recomputeHealth(d: Partial<DashboardData>): DashboardData['dataHealth'] {
  const counts: Record<string, number> = {
    slippageSummary: d.slippage?.summary?.length ?? 0,
    slippageAlgos: d.slippage?.algos?.length ?? 0,
    alerts: d.risk?.alerts?.length ?? 0,
    stopLossWatch: d.risk?.stopLossWatch?.length ?? 0,
    priceCostDrift: d.risk?.priceCostDrift?.length ?? 0,
    exposure: d.risk?.exposure?.length ?? 0,
    zScores: Object.keys(d.risk?.zScores ?? {}).length,
  };
  const sectionMap: Record<string, number> = {
    'slippage.summary': counts.slippageSummary,
    'slippage.algos': counts.slippageAlgos,
    'risk.alerts': counts.alerts,
    'risk.zScores': counts.zScores,
    'risk.stopLossWatch': counts.stopLossWatch,
    'risk.priceCostDrift': counts.priceCostDrift,
    'risk.exposure': counts.exposure,
  };
  const present: string[] = [];
  const missing: string[] = [];
  for (const [name, n] of Object.entries(sectionMap)) {
    (n > 0 ? present : missing).push(name);
  }
  const warnings = d.dataHealth?.warnings ?? [];
  // Preserve the authoritative 4.0 health fields emitted by the finalizer; the
  // frontend must NEVER invent 'ok'. Absent -> fail-closed defaults so a
  // malformed/legacy payload can't display as healthy.
  return {
    strictJson: d.dataHealth?.strictJson,
    pipelineStatus: d.dataHealth?.pipelineStatus ?? 'failed',
    producerStatus: d.dataHealth?.producerStatus ?? {},
    lastSuccessfulRunAt: d.dataHealth?.lastSuccessfulRunAt ?? null,
    sectionsPresent: present,
    sectionsMissing: missing,
    warnings,
    rowCounts: counts,
  };
}

async function fetchJson(url: string): Promise<DashboardData> {
  const res = await fetch(bust(url), { cache: 'no-store' });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  const raw = await res.json();
  return normalize(raw);
}

export function useDashboardData(): DashboardState {
  const [state, setState] = useState<Omit<DashboardState, 'refresh'>>({
    data: normalize(sampleData),
    status: 'loading',
    origin: 'sample',
    error: null,
    lastFetchedAt: null,
    nextRefreshInSec: POLL_MS / 1000,
    refreshing: false,
  });

  const cancelledRef = useRef(false);

  const load = useCallback(async () => {
    setState((s) => ({ ...s, refreshing: true }));
    const now = () => new Date().toISOString();

    // 1. hosted env URL
    if (ENV_URL) {
      try {
        const data = await fetchJson(ENV_URL);
        if (!cancelledRef.current)
          setState((s) => ({ ...s, data, status: 'loaded', origin: 'url', error: null, lastFetchedAt: now(), refreshing: false, nextRefreshInSec: POLL_MS / 1000 }));
        return;
      } catch (e) {
        console.warn('VITE_DASHBOARD_DATA_URL fetch failed:', e);
        // do not silently fall to sample if a URL was explicitly configured —
        // try public next, but keep the error for the status panel.
      }
    }

    // 2. local /data/latest.json
    try {
      const data = await fetchJson(PUBLIC_URL);
      if (!cancelledRef.current)
        setState((s) => ({ ...s, data, status: 'loaded', origin: 'public', error: null, lastFetchedAt: now(), refreshing: false, nextRefreshInSec: POLL_MS / 1000 }));
      return;
    } catch (e) {
      // 3. bundled sample fallback — surfaced as amber warning, NOT silent.
      const msg = e instanceof Error ? e.message : String(e);
      if (!cancelledRef.current)
        setState((s) => {
          const data = normalize(sampleData);
          data.dataHealth = {
            ...data.dataHealth,
            warnings: [
              `Live data fetch failed (${msg}). Showing bundled sample fallback.`,
              ...data.dataHealth.warnings,
            ],
          };
          return { ...s, data, status: 'missing', origin: 'sample', error: msg, lastFetchedAt: now(), refreshing: false, nextRefreshInSec: POLL_MS / 1000 };
        });
    }
  }, []);

  const refresh = useCallback(() => {
    void load();
  }, [load]);

  useEffect(() => {
    cancelledRef.current = false;
    void load();

    const poll = setInterval(() => void load(), POLL_MS);
    const tick = setInterval(() => {
      setState((s) => ({
        ...s,
        nextRefreshInSec: s.nextRefreshInSec > 0 ? s.nextRefreshInSec - 1 : 0,
      }));
    }, 1000);

    return () => {
      cancelledRef.current = true;
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [load]);

  return { ...state, refresh };
}
