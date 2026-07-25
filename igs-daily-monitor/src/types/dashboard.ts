// ============================================================
// IGS Daily Monitor — dashboard JSON contract (TypeScript)
// Mirrors the payload produced by dashboard_adapter/build_dashboard_payload.py
// ============================================================

// Algo names come from the live payload and can change between runs.
export type AlgoName = string;
export type DriftAlgoName = string;

// Production sibling-export modes + built-in demo. Legacy csv/json/html kept
// only so old payloads still type-check (never produced in production).
// Mirrors dashboard_adapter/dashboard_contract.py SOURCE_MODES.
export type SourceMode =
  | 'artifact-live'
  | 'direct-live'
  | 'pipeline-live'
  | 'pipeline-dry-run'
  | 'sample'
  | 'json'
  | 'csv'
  | 'html';

// 4.0 schema constants (mirror dashboard_contract.py).
export const SCHEMA_VERSION_4 = '4.0';
export const LIVE_SOURCE_MODES: readonly SourceMode[] = [
  'artifact-live',
  'direct-live',
  'pipeline-live',
];

// dataHealth.pipelineStatus states.
export type PipelineStatus = 'ok' | 'partial' | 'failed' | 'stale';
// Producer-level status. 'unknown' is reserved for the legacy-3.0 adapter.
export type ProducerState = 'success' | 'failed' | 'missing' | 'stale' | 'unknown';
// Overall UI verdict.
export type HealthVerdict = 'healthy' | 'degraded' | 'rejected';

export interface ProducerStatus {
  status: ProducerState;
  rowCount?: number | null;
  capturedAt?: string | null;
  error?: string | null;
}

export interface SlippageSummary {
  algoId: number | null;
  algoName: AlgoName;
  slippageModelIgsPct: number | null;
  slippageClosePricePct: number | null;
  cumulativeDailyClosePct: number | null;
  cumulativeModelClosePct: number | null;
  todayClosePnl: number | null;
  todayModelPnl: number | null;
  cumulativeDailyClosePnl: number | null;
  cumulativeModelPnl: number | null;
}

export interface SlippageStock {
  algoName: AlgoName;
  rankType: 'best' | 'worst';
  symbol: string;
  name: string;
  slippagePnlRs: number | null;
  slippagePct: number | null;
}

export interface SlippageHeadline {
  metric: string;
  slippagePct: number | null;
  pnlRs: number | null;
}

export interface SlippageAlgo {
  algoId: number | null;
  algoName: AlgoName;
  headlines: SlippageHeadline[];
  bestStocks: SlippageStock[];
  worstStocks: SlippageStock[];
  dateSeries?: { date: string; slippagePct: number }[];
}

export type BreachState = 'Yes' | 'No' | '—';
export type AlertSeverity = 'ok' | 'warning' | 'breach' | 'info';

export interface AlertRow {
  alertType: string;
  metric: string;
  currentValue: string;
  threshold: string;
  breach: BreachState;
  actionRequired: string;
  severity: AlertSeverity;
}

export interface ZScores {
  composite?: number;
  alpha?: number;
  combined?: number;
}

export interface StopLossWatch {
  symbol: string;
  name: string;
  resetPrice: number | null;
  lastPrice: number | null;
  chgPct: number | null;
  daysHeld: number | null;
  execWeightPct: number | null;
  pctChangePct: number | null;
  slHit: boolean;
}

export interface PriceCostDriftRow {
  algoName: DriftAlgoName;
  symbol: string;
  name: string;
  resetPrice: number | null;
  avgCost: number | null;
  diffResetPriceAvgPricePct: number;
  execWeightPct: number | null;
  gainLossPct: number | null;
}

export interface ExposureRow {
  algoName: string;
  osid: number | null;
  quantity: number | null;
  avgPrice: number | null;
  marketPrice: number | null;
  isin: string;
  execWeightPct: number | null;
  gainLossPct: number | null;
  marketValue: number | null;
  symbol: string;
  coname: string;
}

export interface DashboardSource {
  mode: SourceMode;
  pipelineEntryPoint?: string;
  inputTimestamp?: string;
  inputFiles: string[];
  notes: string[];
}

export interface DataHealth {
  strictJson?: boolean;
  // 4.0 health fields (mirror dashboard_contract.py empty_data_health()).
  pipelineStatus: PipelineStatus;
  producerStatus: Record<string, ProducerStatus>;
  lastSuccessfulRunAt: string | null;
  sectionsPresent: string[];
  sectionsMissing: string[];
  warnings: string[];
  rowCounts: Record<string, number>;
}

export interface DashboardData {
  schemaVersion?: string;
  runId?: string;
  businessDate: string;
  generatedAt: string;
  source: DashboardSource;
  slippage: {
    summary: SlippageSummary[];
    algos: SlippageAlgo[];
  };
  risk: {
    alerts: AlertRow[];
    zScores: ZScores;
    stopLossWatch: StopLossWatch[];
    priceCostDrift: PriceCostDriftRow[];
    exposure: ExposureRow[];
  };
  dataHealth: DataHealth;
}

export type LoadStatus = 'loading' | 'loaded' | 'missing' | 'failed';

export interface DashboardState {
  data: DashboardData;
  status: LoadStatus;
  origin: 'url' | 'public' | 'sample';
  error: string | null;
  /** Wall-clock time of the last successful (or attempted) fetch. */
  lastFetchedAt: string | null;
  /** Seconds remaining until the next auto-refresh. */
  nextRefreshInSec: number;
  /** True while a (re)fetch is in flight. */
  refreshing: boolean;
  /** Trigger an immediate manual refresh. */
  refresh: () => void;
}
