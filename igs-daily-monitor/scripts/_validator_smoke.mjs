// Cross-check the JS validator against representative payloads.
// Run with: node scripts/_validator_smoke.mjs  (uses tsx-free plain JS re-impl import via esbuild transform)
import { readFileSync } from 'node:fs';
import { execSync } from 'node:child_process';

// Transpile the TS validator to a temp mjs using esbuild (bundled with vite).
const out = execSync(
  'npx esbuild src/lib/validateDashboard.ts --bundle --format=esm --platform=node --external:react',
  { cwd: new URL('..', import.meta.url).pathname, encoding: 'utf8' },
);
const mod = await import('data:text/javascript,' + encodeURIComponent(out));
const { validatePayload } = mod;

function base(extra) {
  return {
    schemaVersion: '4.0',
    businessDate: '2026-07-14',
    generatedAt: '2026-07-14T18:00:00Z',
    source: { mode: 'artifact-live', inputFiles: [], notes: [] },
    slippage: { summary: [], algos: [] },
    risk: { alerts: [], zScores: {}, stopLossWatch: [], priceCostDrift: [], exposure: [] },
    dataHealth: {
      pipelineStatus: 'ok',
      producerStatus: {
        alerts: { status: 'success' }, slippage: { status: 'success' }, stop_loss: { status: 'success' },
        price_cost_drift: { status: 'success' }, exposure: { status: 'success' },
      },
      lastSuccessfulRunAt: '2026-07-14T18:00:00Z',
      sectionsPresent: [], sectionsMissing: [], warnings: [], rowCounts: {},
      ...extra,
    },
  };
}

const cases = [
  ['healthy artifact-live ok', base(), 'healthy'],
  ['failed pipeline', base({ pipelineStatus: 'failed' }), 'rejected'],
  ['partial pipeline', base({ pipelineStatus: 'partial' }), 'degraded'],
  ['stale pipeline', base({ pipelineStatus: 'stale' }), 'degraded'],
  ['ok but a producer failed', base({ producerStatus: { alerts: { status: 'failed' } } }), 'rejected'],
  ['ok but no lastSuccessfulRunAt', base({ lastSuccessfulRunAt: null }), 'rejected'],
  ['missing pipelineStatus (malformed 4.0)', base({ pipelineStatus: undefined }), 'rejected'],
];

let ok = 0;
for (const [name, payload, expect] of cases) {
  const v = validatePayload(payload);
  const pass = v.verdict === expect;
  ok += pass ? 1 : 0;
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}  -> ${v.verdict} (expected ${expect})`);
  if (!pass) console.log('   reasons:', v.reasons, 'errors:', v.errors);
}

// legacy 3.0
const legacy = { schemaVersion: '3.0', businessDate: '2026-07-01', source: { mode: 'sample' }, dataHealth: { sectionsPresent: [], sectionsMissing: [], warnings: [], rowCounts: {} } };
const lv = validatePayload(legacy);
const lpass = lv.verdict === 'degraded' && lv.legacy === true;
ok += lpass ? 1 : 0;
console.log(`${lpass ? 'PASS' : 'FAIL'}  legacy 3.0 -> ${lv.verdict} legacy=${lv.legacy}`);

console.log(`\n${ok}/${cases.length + 1} cases passed`);
process.exit(ok === cases.length + 1 ? 0 : 1);
