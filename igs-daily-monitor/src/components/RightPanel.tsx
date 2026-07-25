import { FileDown, Database, CheckCircle2, AlertTriangle, FileText, RefreshCw } from 'lucide-react';
import { useData } from '../DataContext';
import { formatDateTime } from '../utils/format';

const MODE_LABEL: Record<string, string> = {
  'artifact-live': 'Pipeline (live)',
  'pipeline-live': 'Pipeline (live)',
  'pipeline-dry-run': 'Pipeline (dry-run)',
  sample: 'Sample data',
  json: 'Pipeline JSON (legacy)',
  csv: 'Pipeline CSV (legacy)',
  html: 'Email HTML (deprecated)',
};

// Render the countdown as "29m 58s" / "45s" instead of a raw "1798s".
function formatCountdown(totalSec: number): string {
  const s = Math.max(0, Math.floor(totalSec));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return m > 0 ? `${m}m ${rem.toString().padStart(2, '0')}s` : `${rem}s`;
}

export default function RightPanel({
  onExport,
  exporting,
}: {
  onExport?: () => void;
  exporting?: boolean;
}) {
  const { data, status, origin, lastFetchedAt, nextRefreshInSec, refreshing, refresh } = useData();
  const { source, dataHealth, generatedAt } = data;

  const originLabel =
    origin === 'url'
      ? 'Env data URL'
      : origin === 'public'
        ? '/data/latest.json'
        : 'Bundled sample';

  const isSampleFallback = origin === 'sample';

  return (
    <aside className="right-panel" data-html2canvas-ignore="true">
      <div className="rp-section">
        <div className="rp-title">
          <Database size={13} /> Data source
        </div>
        {isSampleFallback && (
          <div className="tag warn mono" style={{ marginBottom: 8, display: 'inline-block' }} data-testid="label-sample-fallback">
            Sample fallback
          </div>
        )}
        <div className="rp-kv">
          <span>Mode</span>
          <span className="mono">{MODE_LABEL[source.mode] ?? source.mode}</span>
        </div>
        <div className="rp-kv">
          <span>Origin</span>
          <span className="mono">{originLabel}</span>
        </div>
        <div className="rp-kv">
          <span>Status</span>
          <span className={`mono ${status === 'loaded' ? 'pos' : status === 'missing' ? 'warn' : ''}`} data-testid="status-load">
            {status === 'loaded' ? 'Data loaded' : status}
          </span>
        </div>
        {source.pipelineEntryPoint && (
          <div className="rp-kv">
            <span>Entry point</span>
            <span className="mono small">{source.pipelineEntryPoint}</span>
          </div>
        )}
        <div className="rp-kv">
          <span>Last generated</span>
          <span className="mono small">{formatDateTime(generatedAt)}</span>
        </div>
        <div className="rp-kv">
          <span>Last fetched</span>
          <span className="mono small" data-testid="text-last-fetched">
            {lastFetchedAt ? formatDateTime(lastFetchedAt) : '—'}
          </span>
        </div>
        <div className="rp-kv">
          <span>Next refresh</span>
          <span className="mono small" data-testid="text-next-refresh">
            {refreshing ? 'refreshing…' : formatCountdown(nextRefreshInSec)}
          </span>
        </div>
        <button
          className="export-btn full"
          style={{ marginTop: 10 }}
          onClick={refresh}
          disabled={refreshing}
          data-testid="button-refresh"
        >
          <RefreshCw size={14} className={refreshing ? 'spin' : ''} />
          {refreshing ? 'Refreshing…' : 'Refresh now'}
        </button>
      </div>

      <div className="rp-section">
        <div className="rp-title">
          <FileText size={13} /> Input files
        </div>
        {source.inputFiles.length ? (
          <ul className="rp-list mono">
            {source.inputFiles.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        ) : (
          <div className="rp-empty">None (sample data)</div>
        )}
      </div>

      <div className="rp-section">
        <div className="rp-title">
          <CheckCircle2 size={13} /> Sections present
        </div>
        <div className="rp-tags">
          {dataHealth.sectionsPresent.map((s) => (
            <span key={s} className="tag ok mono">
              {s}
            </span>
          ))}
        </div>
        {dataHealth.sectionsMissing.length > 0 && (
          <>
            <div className="rp-title muted" style={{ marginTop: 10 }}>
              Sections missing
            </div>
            <div className="rp-tags">
              {dataHealth.sectionsMissing.map((s) => (
                <span key={s} className="tag warn mono">
                  {s}
                </span>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="rp-section">
        <div className="rp-title">Row counts</div>
        {Object.entries(dataHealth.rowCounts).map(([k, v]) => (
          <div className="rp-kv" key={k}>
            <span>{k}</span>
            <span className="mono">{v}</span>
          </div>
        ))}
      </div>

      {dataHealth.warnings.length > 0 && (
        <div className="rp-section">
          <div className="rp-title warn">
            <AlertTriangle size={13} /> Warnings
          </div>
          <ul className="rp-list warn-list">
            {dataHealth.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {onExport && (
        <button className="export-btn full" onClick={onExport} disabled={exporting} data-testid="button-export-pdf">
          <FileDown size={15} />
          {exporting ? 'Exporting…' : 'Export current page PDF'}
        </button>
      )}
    </aside>
  );
}
