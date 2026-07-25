import { CalendarDays, ShieldAlert, IndianRupee, Crosshair, PieChart, GitCompareArrows } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import KpiCard from '../components/KpiCard';
import DataTable, { type Column } from '../components/DataTable';
import StatusPill from '../components/StatusPill';
import EmptyState from '../components/EmptyState';
import { useData } from '../DataContext';
import {
  formatDate,
  formatPct,
  formatRs,
  formatRsCompact,
  colorClassBySign,
} from '../utils/format';
import {
  breachCount,
  totalTodayModelPnl,
  topAbsDrift,
  topExposures,
} from '../utils/derive';
import type { AlertRow, PriceCostDriftRow, ExposureRow, SlippageSummary } from '../types/dashboard';

type PageProps = { onExport?: () => void; exporting?: boolean };

export default function Overview({ onExport, exporting }: PageProps) {
  const { data } = useData();
  const { slippage, risk } = data;
  const breaches = breachCount(data);

  const alertCols: Column<AlertRow>[] = [
    { key: 'alertType', header: 'Alert Type', render: (r) => r.alertType, sortValue: (r) => r.alertType },
    { key: 'metric', header: 'Metric', render: (r) => r.metric, sortValue: (r) => r.metric },
    { key: 'current', header: 'Current', numeric: true, render: (r) => r.currentValue },
    { key: 'threshold', header: 'Threshold', numeric: true, render: (r) => r.threshold },
    {
      key: 'breach',
      header: 'Breach?',
      render: (r) => <BreachPill state={r.breach} />,
      sortValue: (r) => r.breach,
    },
    { key: 'action', header: 'Action Required', render: (r) => r.actionRequired },
  ];

  const driftCols: Column<PriceCostDriftRow>[] = [
    { key: 'symbol', header: 'Symbol', render: (r) => r.symbol, sortValue: (r) => r.symbol },
    { key: 'name', header: 'Name', render: (r) => r.name },
    { key: 'algo', header: 'Algo', render: (r) => r.algoName, sortValue: (r) => r.algoName },
    {
      key: 'diff',
      header: 'Diff %',
      numeric: true,
      render: (r) => <span className={colorClassBySign(r.diffResetPriceAvgPricePct)}>{formatPct(r.diffResetPriceAvgPricePct)}</span>,
      sortValue: (r) => Math.abs(r.diffResetPriceAvgPricePct),
    },
  ];

  const expCols: Column<ExposureRow>[] = [
    { key: 'symbol', header: 'Symbol', render: (r) => r.symbol, sortValue: (r) => r.symbol },
    { key: 'coname', header: 'Company', render: (r) => r.coname },
    { key: 'algo', header: 'Algo', render: (r) => r.algoName, sortValue: (r) => r.algoName },
    {
      key: 'weight',
      header: 'ExecAPI Weight %',
      numeric: true,
      render: (r) => formatPct(r.execWeightPct),
      sortValue: (r) => r.execWeightPct ?? 0,
    },
  ];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Daily production monitor"
        title="What needs attention today?"
        answer="No hard breach is marked; slippage, stop-loss watch, exposure, and price-cost drift are loaded for review."
        onExport={onExport}
        exporting={exporting}
      />

      <div className="kpi-grid">
        <KpiCard label="Business date" value={<span className="mono">{formatDate(data.businessDate)}</span>} icon={<CalendarDays size={14} />} />
        <KpiCard
          label="Hard breaches"
          value={<span className={`mono ${breaches > 0 ? 'neg' : 'pos'}`}>{breaches}</span>}
          sub={breaches > 0 ? 'Review Alerts & Risk' : 'None flagged'}
          icon={<ShieldAlert size={14} />}
        />
        <KpiCard
          label="Total today model P&L"
          value={<span className={`mono ${colorClassBySign(totalTodayModelPnl(slippage.summary))}`}>{formatRsCompact(totalTodayModelPnl(slippage.summary))}</span>}
          icon={<IndianRupee size={14} />}
        />
        <KpiCard label="Stop-loss watch" value={<span className="mono">{risk.stopLossWatch.length}</span>} icon={<Crosshair size={14} />} />
        <KpiCard label="Exposure rows" value={<span className="mono">{risk.exposure.length}</span>} icon={<PieChart size={14} />} />
        <KpiCard label="Drift rows" value={<span className="mono">{risk.priceCostDrift.length}</span>} icon={<GitCompareArrows size={14} />} />
      </div>

      <section className="block">
        <h3 className="block-title">Algo slippage</h3>
        {slippage.summary.length ? (
          <div className="algo-cards">
            {slippage.summary.map((s) => (
              <AlgoSlippageCard key={s.algoName} s={s} />
            ))}
          </div>
        ) : (
          <EmptyState message="Slippage summary was not included in the current payload." />
        )}
      </section>

      <section className="block">
        <h3 className="block-title">Risk alert matrix</h3>
        <DataTable columns={alertCols} rows={risk.alerts} initialSortKey="breach" emptyMessage="No alerts in the current payload." />
      </section>

      <div className="two-col">
        <section className="block">
          <h3 className="block-title">Top 5 by absolute drift</h3>
          <DataTable columns={driftCols} rows={topAbsDrift(risk.priceCostDrift, 5)} initialSortKey="diff" emptyMessage="No price-cost drift rows." />
        </section>
        <section className="block">
          <h3 className="block-title">Top 5 exposures</h3>
          <DataTable columns={expCols} rows={topExposures(risk.exposure, 5)} initialSortKey="weight" emptyMessage="No exposure rows." />
        </section>
      </div>
    </div>
  );
}

function AlgoSlippageCard({ s }: { s: SlippageSummary }) {
  return (
    <div className="algo-card">
      <div className="algo-card-head">
        <span className="algo-name">{s.algoName}</span>
        {s.algoId !== null && <span className="algo-id mono">#{s.algoId}</span>}
      </div>
      <div className="algo-metrics">
        <Metric label="Model vs IGS" value={formatPct(s.slippageModelIgsPct)} tone={colorClassBySign(s.slippageModelIgsPct)} />
        <Metric label="Close price" value={formatPct(s.slippageClosePricePct)} tone={colorClassBySign(s.slippageClosePricePct)} />
        <Metric label="Cum. model" value={formatPct(s.cumulativeModelClosePct)} tone={colorClassBySign(s.cumulativeModelClosePct)} />
        <Metric label="Today model P&L" value={formatRs(s.todayModelPnl)} tone={colorClassBySign(s.todayModelPnl)} />
      </div>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="algo-metric">
      <span className="am-label">{label}</span>
      <span className={`am-value mono ${tone ?? ''}`}>{value}</span>
    </div>
  );
}

export function BreachPill({ state }: { state: AlertRow['breach'] }) {
  if (state === 'Yes') return <StatusPill variant="red" label="Yes" />;
  if (state === 'No') return <StatusPill variant="green" label="No" />;
  return <StatusPill variant="muted" label="—" />;
}
