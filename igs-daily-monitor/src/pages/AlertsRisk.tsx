import { Info } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import DataTable, { type Column } from '../components/DataTable';
import StatusPill from '../components/StatusPill';
import EmptyState from '../components/EmptyState';
import { BreachPill } from './Overview';
import { useData } from '../DataContext';
import { formatPct, formatNumber, colorClassBySign } from '../utils/format';
import type { AlertRow, StopLossWatch } from '../types/dashboard';

type PageProps = { onExport?: () => void; exporting?: boolean };

const MONITORING_NOTE =
  'By 8:45 AM the next day, confirm respective orders are placed in SQL tables. If not placed, report to Dev & Quant teams.';

export default function AlertsRisk({ onExport, exporting }: PageProps) {
  const { data } = useData();
  const { alerts, zScores, stopLossWatch } = data.risk;

  const alertCols: Column<AlertRow>[] = [
    { key: 'alertType', header: 'Alert Type', render: (r) => r.alertType, sortValue: (r) => r.alertType },
    { key: 'metric', header: 'Metric', render: (r) => r.metric, sortValue: (r) => r.metric },
    { key: 'current', header: 'Current Value', numeric: true, render: (r) => r.currentValue },
    { key: 'threshold', header: 'Threshold', numeric: true, render: (r) => r.threshold },
    { key: 'breach', header: 'Breach?', render: (r) => <BreachPill state={r.breach} />, sortValue: (r) => r.breach },
    { key: 'action', header: 'Action Required', render: (r) => r.actionRequired },
  ];

  const slCols: Column<StopLossWatch>[] = [
    { key: 'symbol', header: 'Symbol', render: (r) => r.symbol, sortValue: (r) => r.symbol },
    { key: 'name', header: 'Name', render: (r) => r.name },
    { key: 'reset', header: 'Reset Price', numeric: true, render: (r) => formatNumber(r.resetPrice, 2), sortValue: (r) => r.resetPrice ?? 0 },
    { key: 'last', header: 'Last Price', numeric: true, render: (r) => formatNumber(r.lastPrice, 2), sortValue: (r) => r.lastPrice ?? 0 },
    { key: 'chg', header: 'Chg %', numeric: true, render: (r) => <span className={colorClassBySign(r.chgPct)}>{formatPct(r.chgPct)}</span>, sortValue: (r) => r.chgPct ?? 0 },
    { key: 'days', header: 'Days Held', numeric: true, render: (r) => formatNumber(r.daysHeld, 0), sortValue: (r) => r.daysHeld ?? 0 },
    { key: 'weight', header: 'ExecAPI Weight %', numeric: true, render: (r) => formatPct(r.execWeightPct), sortValue: (r) => r.execWeightPct ?? 0 },
    { key: 'pctChg', header: 'Pct Change %', numeric: true, render: (r) => <span className={colorClassBySign(r.pctChangePct)}>{formatPct(r.pctChangePct)}</span>, sortValue: (r) => r.pctChangePct ?? 0 },
    {
      key: 'slHit',
      header: 'SL Hit',
      render: (r) => (r.slHit ? <StatusPill variant="red" label="Hit" /> : <StatusPill variant="muted" label="No" />),
      sortValue: (r) => (r.slHit ? 1 : 0),
    },
  ];

  const zEntries = Object.entries(zScores);

  return (
    <div className="page">
      <PageHeader
        eyebrow="Risk thresholds"
        title="Are any risk thresholds breached?"
        answer="No hard breach is flagged; z-score, stop-loss watch, and alert rows are shown below for review."
        onExport={onExport}
        exporting={exporting}
      />

      <section className="block">
        <h3 className="block-title">Alert matrix</h3>
        <DataTable columns={alertCols} rows={alerts} initialSortKey="breach" emptyMessage="No alerts in the current payload." />
      </section>

      <section className="block">
        <h3 className="block-title">Z-scores</h3>
        {zEntries.length ? (
          <div className="zscore-grid">
            {zEntries.map(([k, v]) => (
              <div className="zscore-card" key={k}>
                <div className="zs-label">{k}</div>
                <div className="zs-value mono">{formatNumber(v, 2)}</div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState message="No z-scores in the current payload." />
        )}
      </section>

      <section className="block">
        <h3 className="block-title">Stop-loss watch</h3>
        <DataTable columns={slCols} rows={stopLossWatch} initialSortKey="pctChg" initialSortDir="asc" emptyMessage="No stop-loss watch rows." />
      </section>

      <div className="note-box">
        <Info size={15} />
        <span>{MONITORING_NOTE}</span>
      </div>
    </div>
  );
}
