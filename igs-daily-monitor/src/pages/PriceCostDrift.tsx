import { useMemo, useState } from 'react';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
  Tooltip,
} from 'recharts';
import PageHeader from '../components/PageHeader';
import KpiCard from '../components/KpiCard';
import DataTable, { type Column } from '../components/DataTable';
import EmptyState from '../components/EmptyState';
import { ChartTooltipBox } from '../components/ChartTooltip';
import { useData } from '../DataContext';
import { formatPct, formatNumber, colorClassBySign } from '../utils/format';
import { negativeDriftCount, positiveDriftCount, maxAbsDrift } from '../utils/derive';
import type { PriceCostDriftRow, DriftAlgoName } from '../types/dashboard';

const POS = '#22c98a';
const NEG = '#f06150';

type PageProps = { onExport?: () => void; exporting?: boolean };
type AlgoFilter = 'All' | DriftAlgoName;
type SignFilter = 'All' | 'Negative' | 'Positive';

export default function PriceCostDrift({ onExport, exporting }: PageProps) {
  const { data } = useData();
  const rows = data.risk.priceCostDrift;

  const [algo, setAlgo] = useState<AlgoFilter>('All');
  const [sign, setSign] = useState<SignFilter>('All');
  const [search, setSearch] = useState('');

  const algoOptions = useMemo(
    () => ['All', ...Array.from(new Set(rows.map((r) => r.algoName).filter(Boolean)))],
    [rows],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (algo !== 'All' && r.algoName !== algo) return false;
      if (sign === 'Negative' && !(r.diffResetPriceAvgPricePct < 0)) return false;
      if (sign === 'Positive' && !(r.diffResetPriceAvgPricePct > 0)) return false;
      if (q && !(r.symbol.toLowerCase().includes(q) || r.name.toLowerCase().includes(q))) return false;
      return true;
    });
  }, [rows, algo, sign, search]);

  const scatterData = filtered
    .filter((r) => r.execWeightPct !== null && r.execWeightPct !== undefined)
    .map((r) => ({
      x: r.diffResetPriceAvgPricePct,
      y: r.execWeightPct as number,
      symbol: r.symbol,
      name: r.name,
    }));

  const cols: Column<PriceCostDriftRow>[] = [
    { key: 'symbol', header: 'Symbol', render: (r) => r.symbol, sortValue: (r) => r.symbol },
    { key: 'name', header: 'Name', render: (r) => r.name },
    { key: 'algo', header: 'Algo', render: (r) => r.algoName, sortValue: (r) => r.algoName },
    { key: 'reset', header: 'Reset Price', numeric: true, render: (r) => formatNumber(r.resetPrice, 2), sortValue: (r) => r.resetPrice ?? 0 },
    { key: 'avg', header: 'Avg Cost', numeric: true, render: (r) => formatNumber(r.avgCost, 2), sortValue: (r) => r.avgCost ?? 0 },
    { key: 'diff', header: 'Diff %', numeric: true, render: (r) => <span className={colorClassBySign(r.diffResetPriceAvgPricePct)}>{formatPct(r.diffResetPriceAvgPricePct)}</span>, sortValue: (r) => r.diffResetPriceAvgPricePct },
    { key: 'weight', header: 'ExecAPI Weight %', numeric: true, render: (r) => formatPct(r.execWeightPct), sortValue: (r) => r.execWeightPct ?? 0 },
    { key: 'gl', header: 'Gain/Loss %', numeric: true, render: (r) => <span className={colorClassBySign(r.gainLossPct)}>{formatPct(r.gainLossPct)}</span>, sortValue: (r) => r.gainLossPct ?? 0 },
  ];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Reset-price tracking"
        title="Which holdings are farthest from reset price?"
        answer="Holdings are ranked by the absolute difference between reset price and average cost; use the filters to narrow by algo or direction."
        onExport={onExport}
        exporting={exporting}
      />

      <div className="filter-bar" data-html2canvas-ignore="true">
        <SegGroup label="Algo" options={algoOptions} value={algo} onChange={(v) => setAlgo(v as AlgoFilter)} testid="filter-algo" />
        <SegGroup label="Direction" options={['All', 'Negative', 'Positive']} value={sign} onChange={(v) => setSign(v as SignFilter)} testid="filter-sign" />
        <div className="search-wrap">
          <input
            className="search-input mono"
            placeholder="Search symbol / name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            data-testid="input-drift-search"
          />
        </div>
      </div>

      <div className="kpi-grid">
        <KpiCard label="Rows (filtered)" value={<span className="mono">{filtered.length}</span>} sub={`${rows.length} total`} />
        <KpiCard label="Negative drift" value={<span className="mono neg">{negativeDriftCount(filtered)}</span>} />
        <KpiCard label="Positive drift" value={<span className="mono pos">{positiveDriftCount(filtered)}</span>} />
        <KpiCard label="Max abs drift %" value={<span className="mono">{formatPct(maxAbsDrift(filtered))}</span>} />
      </div>

      <section className="block">
        <h3 className="block-title">Drift % vs ExecAPI weight %</h3>
        {scatterData.length ? (
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" dataKey="x" name="Diff %" stroke="#9aa1ac" fontSize={12} tickFormatter={(v) => `${v}%`} />
                <YAxis type="number" dataKey="y" name="ExecAPI Weight %" stroke="#9aa1ac" fontSize={12} tickFormatter={(v) => `${v}%`} />
                <ZAxis range={[60, 60]} />
                <Tooltip
                  cursor={{ strokeDasharray: '3 3' }}
                  content={({ active, payload }) =>
                    active && payload?.length ? (
                      <ChartTooltipBox
                        title={`${payload[0].payload.symbol} — ${payload[0].payload.name}`}
                        rows={[
                          { label: 'Diff %', value: formatPct(payload[0].payload.x) },
                          { label: 'ExecAPI Weight %', value: formatPct(payload[0].payload.y) },
                        ]}
                      />
                    ) : null
                  }
                />
                <Scatter data={scatterData} isAnimationActive={false}>
                  {scatterData.map((d, i) => (
                    <Cell key={i} fill={d.x >= 0 ? POS : NEG} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState message="No rows with ExecAPI weight to plot for the current filter." />
        )}
      </section>

      <section className="block">
        <h3 className="block-title">Holdings</h3>
        <DataTable columns={cols} rows={filtered} initialSortKey="diff" emptyMessage="No price-cost drift rows match the current filter." />
      </section>
    </div>
  );
}

function SegGroup({
  label,
  options,
  value,
  onChange,
  testid,
}: {
  label: string;
  options: string[];
  value: string;
  onChange: (v: string) => void;
  testid: string;
}) {
  return (
    <div className="filter-group">
      <span className="filter-label">{label}</span>
      <div className="seg-control">
        {options.map((o) => (
          <button
            key={o}
            className={`seg ${value === o ? 'active' : ''}`}
            onClick={() => onChange(o)}
            data-testid={`${testid}-${o}`}
          >
            {o}
          </button>
        ))}
      </div>
    </div>
  );
}
