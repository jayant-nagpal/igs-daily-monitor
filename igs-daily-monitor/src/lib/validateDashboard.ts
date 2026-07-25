// ============================================================
// IGS Daily Monitor — runtime payload validation (schema 4.0)
// Mirrors dashboard_adapter/dashboard_contract.py:
//   validate_structure / validate_live_health / is_legacy_v3 / adapt_legacy_v3
//
// GOAL (per spec): malformed / failed / incomplete / stale 4.0 data must NOT
// be shown as healthy. Legacy 3.0 payloads may be read TEMPORARILY but are
// never republished/displayed as healthy 4.0 — they surface a stale/legacy
// warning and all producer health becomes 'unknown'.
// ============================================================

import type {
  DashboardData,
  HealthVerdict,
  PipelineStatus,
  ProducerState,
} from '../types/dashboard';
import { SCHEMA_VERSION_4, LIVE_SOURCE_MODES } from '../types/dashboard';

const PIPELINE_STATUSES: PipelineStatus[] = ['ok', 'partial', 'failed', 'stale'];
// Mirrors dashboard_contract.py PRODUCER_STATUSES (a healthy producer is
// 'success', not 'ok'; there is no 'empty' state).
const PRODUCER_STATES: ProducerState[] = ['success', 'failed', 'missing', 'stale', 'unknown'];

export interface ValidationResult {
  /** overall verdict used by the UI */
  verdict: HealthVerdict;
  /** true when the raw payload is a legacy 3.0 document */
  legacy: boolean;
  /** human-readable reasons (shown in the health panel / banners) */
  reasons: string[];
  /** structural errors that make the payload unusable */
  errors: string[];
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

/** Detect a legacy 3.0 payload (schemaVersion missing or 3.x, no 4.0 health). */
export function isLegacyV3(raw: unknown): boolean {
  if (!isObject(raw)) return false;
  const sv = String((raw as Record<string, unknown>).schemaVersion ?? '');
  const health = (raw as Record<string, unknown>).dataHealth;
  const hasV4Health =
    isObject(health) &&
    ('pipelineStatus' in health || 'producerStatus' in health || 'lastSuccessfulRunAt' in health);
  if (sv === SCHEMA_VERSION_4) return false;
  if (sv.startsWith('3.') || sv === '' || sv === '3') return !hasV4Health;
  return false;
}

/**
 * Structural validation for a 4.0 payload. Returns a list of errors; empty ==
 * structurally valid. Does NOT judge health (see validateLiveHealth).
 */
export function validateStructure4(raw: unknown): string[] {
  const errs: string[] = [];
  if (!isObject(raw)) return ['payload is not an object'];
  const p = raw as Record<string, unknown>;

  if (String(p.schemaVersion ?? '') !== SCHEMA_VERSION_4) {
    errs.push(`schemaVersion must be ${SCHEMA_VERSION_4}, got ${String(p.schemaVersion)}`);
  }
  if (typeof p.businessDate !== 'string' || !p.businessDate) errs.push('businessDate missing');
  if (!isObject(p.source)) errs.push('source missing');
  if (!isObject(p.slippage)) errs.push('slippage missing');
  if (!isObject(p.risk)) errs.push('risk missing');

  const health = p.dataHealth;
  if (!isObject(health)) {
    errs.push('dataHealth missing');
    return errs;
  }
  // 4.0 health fields must be PRESENT for a 4.0 payload (not merely optional).
  const ps = health.pipelineStatus;
  if (typeof ps !== 'string' || !PIPELINE_STATUSES.includes(ps as PipelineStatus)) {
    errs.push(`dataHealth.pipelineStatus invalid/missing (${String(ps)})`);
  }
  if (!isObject(health.producerStatus)) {
    errs.push('dataHealth.producerStatus missing');
  } else {
    for (const [k, v] of Object.entries(health.producerStatus)) {
      if (!isObject(v) || !PRODUCER_STATES.includes((v as Record<string, unknown>).status as ProducerState)) {
        errs.push(`producerStatus.${k} invalid`);
      }
    }
  }
  if (!('lastSuccessfulRunAt' in health)) {
    errs.push('dataHealth.lastSuccessfulRunAt missing');
  }
  return errs;
}

/**
 * Decide whether a structurally-valid 4.0 payload may be shown as HEALTHY.
 * Mirrors validate_live_health: 'ok' requires pipelineStatus==='ok', a
 * lastSuccessfulRunAt, and NO producer in a failed/missing/unknown state.
 */
export function validateLiveHealth(raw: Record<string, unknown>): { verdict: HealthVerdict; reasons: string[] } {
  const reasons: string[] = [];
  const health = raw.dataHealth as Record<string, unknown>;
  const mode = (raw.source as Record<string, unknown> | undefined)?.mode;
  const isLive = typeof mode === 'string' && LIVE_SOURCE_MODES.includes(mode as never);
  const ps = health.pipelineStatus as PipelineStatus;

  if (ps === 'failed') {
    reasons.push('pipelineStatus=failed');
    return { verdict: 'rejected', reasons };
  }
  if (ps === 'stale') {
    reasons.push('pipelineStatus=stale');
    return { verdict: 'degraded', reasons };
  }
  if (ps === 'partial') {
    reasons.push('pipelineStatus=partial');
    return { verdict: 'degraded', reasons };
  }
  // ps === 'ok' — enforce the stricter live rules.
  if (!health.lastSuccessfulRunAt) {
    reasons.push("pipelineStatus=ok but lastSuccessfulRunAt is empty");
    return { verdict: 'rejected', reasons };
  }
  const producers = (health.producerStatus ?? {}) as Record<string, { status: ProducerState }>;
  const bad = Object.entries(producers).filter(([, v]) =>
    ['failed', 'missing', 'unknown'].includes(v?.status),
  );
  if (bad.length) {
    reasons.push(`producers not healthy: ${bad.map(([k, v]) => `${k}=${v.status}`).join(', ')}`);
    // 'ok' cannot coexist with failed/missing/unknown producers — reject as live-healthy.
    return { verdict: 'rejected', reasons };
  }
  if (!isLive) {
    // A non-live mode (sample/dry-run) is never "healthy live" — it's a demo.
    reasons.push(`non-live source mode: ${String(mode)}`);
    return { verdict: 'degraded', reasons };
  }
  return { verdict: 'healthy', reasons };
}

/**
 * Full validation entry point. Returns a verdict plus reasons/errors.
 * - Legacy 3.0 -> degraded (readable, but never healthy) + legacy warning.
 * - Structurally invalid 4.0 -> rejected.
 * - Structurally valid 4.0 -> health verdict from validateLiveHealth.
 */
export function validatePayload(raw: unknown): ValidationResult {
  if (isLegacyV3(raw)) {
    return {
      verdict: 'degraded',
      legacy: true,
      reasons: [
        'Legacy 3.0 payload detected. Displayed read-only; producer health is unknown. ' +
          'Not republished as healthy 4.0.',
      ],
      errors: [],
    };
  }
  const errors = validateStructure4(raw);
  if (errors.length) {
    return { verdict: 'rejected', legacy: false, reasons: ['Malformed 4.0 payload.'], errors };
  }
  const { verdict, reasons } = validateLiveHealth(raw as Record<string, unknown>);
  return { verdict, legacy: false, reasons, errors: [] };
}

/**
 * Legacy adapter: shape a 3.0 payload into the 4.0 in-memory type WITHOUT
 * faking health. pipelineStatus becomes 'stale', all producers 'unknown'.
 * Never claims 'ok'.
 */
export function adaptLegacyV3(data: DashboardData): DashboardData {
  const producerStatus: Record<string, { status: ProducerState }> = {};
  for (const k of ['alerts', 'slippage', 'stop_loss', 'price_cost_drift', 'exposure', 'zscores']) {
    producerStatus[k] = { status: 'unknown' };
  }
  return {
    ...data,
    dataHealth: {
      ...data.dataHealth,
      pipelineStatus: 'stale',
      producerStatus,
      lastSuccessfulRunAt: null,
      warnings: [
        'Legacy 3.0 data adapted for display. Health unknown; refresh with a 4.0 pipeline run.',
        ...(data.dataHealth.warnings ?? []),
      ],
    },
  };
}
