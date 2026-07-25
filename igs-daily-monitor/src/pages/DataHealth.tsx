import { CheckCircle2, XCircle, AlertTriangle, Database, FileText } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import KpiCard from '../components/KpiCard';
import JsonViewer from '../components/JsonViewer';
import StatusPill from '../components/StatusPill';
import EmptyState from '../components/EmptyState';
import { useData } from '../DataContext';
import { formatDateTime } from '../utils/format';

const MODE_LABEL: Record<string, string> = {
  'pipeline-live': 'Pipeline (live)',
  'pipeline-dry-run': 'Pipeline (dry-run)',
  sample: 'Sample data',
  json: 'Pipeline JSON (legacy)',
  csv: 'Pipeline CSV (legacy)',
  html: 'Email HTML (deprecated)',
};

type PageProps = { onExport?: () => void; exporting?: boolean };

export default function DataHealth({ onExport, exporting }: PageProps) {
  const { data, status, origin, error } = useData();
  const { source, dataHealth, generatedAt } = data;

  const statusPill =
    status === 'loaded'
      ? { variant: 'green' as const, label: 'Data loaded' }
      : status === 'missing'
        ? { variant: 'amber' as const, label: 'Sample fallback' }
        : status === 'failed'
          ? { variant: 'red' as const, label: 'Load failed' }
          : { variant: 'muted' as const, label: 'Loading…' };

  const originLabel =
    origin === 'url' ? 'Environment data URL' : origin === 'public' ? '/data/latest.json' : 'Bundled sample';

  return (
    <div className="page">
      <PageHeader
        eyebrow="Pipeline health"
        title="Is the dashboard reading the latest payload?"
        answer="This page reports where the data came from, which sections are present or missing, per-section row counts, and any adapter warnings."
        onExport={onExport}
        exporting={exporting}
      />

      <div className="kpi-grid">
        <KpiCard label="Load status" value={<StatusPill variant={statusPill.variant} label={statusPill.label} />} />
        <KpiCard label="Data source" value={<span className="mono">{MODE_LABEL[source.mode] ?? source.mode}</span>} icon={<Database size={14} />} />
        <KpiCard label="Origin" value={<span className="mono">{originLabel}</span>} />
        <KpiCard label="Generated" value={<span className="mono small">{formatDateTime(generatedAt)}</span>} />
      </div>

      {status === 'missing' && (
        <div className="note-box warn">
          <AlertTriangle size={15} />
          <span>
            Live data could not be loaded{error ? ` (${error})` : ''}; showing bundled sample data. Run the adapter and
            publish <code className="mono">latest.json</code> to see live values.
          </span>
        </div>
      )}

      <div className="two-col">
        <section className="block">
          <h3 className="block-title">Sections present</h3>
          {dataHealth.sectionsPresent.length ? (
            <ul className="health-list">
              {dataHealth.sectionsPresent.map((s) => (
                <li key={s}>
                  <CheckCircle2 size={15} className="ok-icon" />
                  <span className="mono">{s}</span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No sections detected." />
          )}
        </section>

        <section className="block">
          <h3 className="block-title">Sections missing</h3>
          {dataHealth.sectionsMissing.length ? (
            <ul className="health-list">
              {dataHealth.sectionsMissing.map((s) => (
                <li key={s}>
                  <XCircle size={15} className="miss-icon" />
                  <span className="mono">{s}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="all-present mono">All expected sections present.</div>
          )}
        </section>
      </div>

      <section className="block">
        <h3 className="block-title">Input files</h3>
        {source.inputFiles.length ? (
          <ul className="file-list">
            {source.inputFiles.map((f) => (
              <li key={f}>
                <FileText size={14} />
                <span className="mono">{f}</span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState message="No input files (sample data mode)." />
        )}
      </section>

      <section className="block">
        <h3 className="block-title">Row counts</h3>
        <div className="rowcount-grid">
          {Object.entries(dataHealth.rowCounts).map(([k, v]) => (
            <div className="rowcount-card" key={k}>
              <div className="rc-label">{k}</div>
              <div className={`rc-value mono ${v === 0 ? 'warn' : ''}`}>{v}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="block">
        <h3 className="block-title">Warnings</h3>
        {dataHealth.warnings.length ? (
          <ul className="warn-list-block">
            {dataHealth.warnings.map((w, i) => (
              <li key={i}>
                <AlertTriangle size={14} />
                <span>{w}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="all-present mono">No warnings.</div>
        )}
      </section>

      {source.notes.length > 0 && (
        <section className="block">
          <h3 className="block-title">Adapter notes</h3>
          <ul className="note-list">
            {source.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="block">
        <h3 className="block-title">Raw payload</h3>
        <JsonViewer value={data} />
      </section>
    </div>
  );
}
