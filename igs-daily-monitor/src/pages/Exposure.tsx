import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  Cell,
} from 'recharts';
import PageHeader from '../components/PageHeader';
import KpiCard from '../components/KpiCard';
import DataTable, { type Column } from '../components/DataTable';
import EmptyState from '../components/EmptyState';
import { ChartTooltipBox } from '../components/ChartTooltip';
import { useData } from '../DataContext';
import { formatPct, formatNumber, formatRsCompact, colorClassBySign } from '../utils/format';
import { maxWeight, totalMarketValue, topExposures } from '../utils/derive';
import type { ExposureRow } from '../types/dashboard';

const ACCENT = '#7c8bff';

type PageProps = { onExport?: () => void; exporting?: boolean };

export default function Exposure({ onExport, exporting }: PageProps) {
  const { data } = useData();
  const rows = data.risk.exposure;

  const chartData = topExposures(rows, 10).map((r) => ({
    label: r.symbol || r.coname,
    weight: r.execWeightPct ?? 0,
    coname: r.coname,
  }));

  const cols: Column<ExposureRow>[] = [
    { key: 'symbol', header: 'Symbol', render: (r) => r.symbol, sortValue: (r) => r.symbol },
    { key: 'coname', header: 'Company', render: (r) => r.coname },
    { key: 'algo', header: 'Algo', render: (r) => r.algoName, sortValue: (r) => r.algoName },
    { key: 'qty', header: 'Quantity', numeric: true, render: (r) => formatNumber(r.quantity, 0), sortValue: (r) => r.quantity ?? 0 },
    { key: 'avg', header: 'Avg Price', numeric: true, render: (r) => formatNumber(r.avgPrice, 2), sortValue: (r) => r.avgPrice ?? 0 },
    { key: 'mkt', header: 'Market Price', numeric: true, render: (r) => formatNumber(r.marketPrice, 2), sortValue: (r) => r.marketPrice ?? 0 },
    { key: 'mv', header: 'Market Value', numeric: true, render: (r) => formatRsCompact(r.marketValue), sortValue: (r) => r.marketValue ?? 0 },
    { key: 'weight', header: 'ExecAPI Weight %', numeric: true, render: (r) => formatPct(r.execWeightPct), sortValue: (r) => r.execWeightPct ?? 0 },
    { key: 'gl', header: 'Gain/Loss %', numeric: true, render: (r) => <span className={colorClassBySign(r.gainLossPct)}>{formatPct(r.gainLossPct)}</span>, sortValue: (r) => r.gainLossPct ?? 0 },
  ];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Concentration"
        title="Where is the portfolio most concentrated?"
        answer="Positions are ranked by ExecAPI weight; the largest weights and total market value are summarised below."
        onExport={onExport}
        exporting={exporting}
      />

      <div className="kpi-grid">
        <KpiCard label="Positions" value={<span className="mono">{rows.length}</span>} />
        <KpiCard label="Max ExecAPI weight %" value={<span className="mono">{formatPct(maxWeight(rows))}</span>} />
        <KpiCard label="Total market value" value={<span className="mono">{formatRsCompact(totalMarketValue(rows))}</span>} />
      </div>

      <section className="block">
        <h3 className="block-title">Top positions by ExecAPI weight</h3>
        {chartData.length ? (
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={Math.max(220, chartData.length * 34)}>
              <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 20, left: 8, bottom: 4 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.05)" horizontal={false} />
                <XAxis type="number" stroke="#9aa1ac" fontSize={12} tickFormatter={(v) => `${v}%`} />
                <YAxis type="category" dataKey="label" stroke="#9aa1ac" fontSize={12} width={90} />
                <Tooltip
                  cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                  content={({ active, payload }) =>
                    active && payload?.length ? (
                      <ChartTooltipBox
                        title={payload[0].payload.coname}
                        rows={[{ label: 'ExecAPI Weight', value: formatPct(payload[0].payload.weight) }]}
                      />
                    ) : null
                  }
                />
                <Bar dataKey="weight" radius={[0, 3, 3, 0]} isAnimationActive={false}>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={ACCENT} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState message="No exposure rows in the current payload." />
        )}
      </section>

      <section className="block">
        <h3 className="block-title">Holdings</h3>
        <DataTable columns={cols} rows={rows} initialSortKey="weight" emptyMessage="No exposure rows." />
      </section>
    </div>
  );
}
