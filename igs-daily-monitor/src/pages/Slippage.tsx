import { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
  Tooltip,
  LineChart,
  Line,
} from 'recharts';
import PageHeader from '../components/PageHeader';
import KpiCard from '../components/KpiCard';
import DataTable, { type Column } from '../components/DataTable';
import EmptyState from '../components/EmptyState';
import { ChartTooltipBox } from '../components/ChartTooltip';
import { useData } from '../DataContext';
import { formatPct, formatRs, colorClassBySign } from '../utils/format';
import { avgModelSlippagePct, avgCloseSlippagePct, totalTodayModelPnl } from '../utils/derive';
import type { SlippageSummary, SlippageStock } from '../types/dashboard';

const POS = '#22c98a';
const NEG = '#f06150';

type PageProps = { onExport?: () => void; exporting?: boolean };

export default function Slippage({ onExport, exporting }: PageProps) {
  const { data } = useData();
  const { summary, algos } = data.slippage;

  const [selected, setSelected] = useState<string>(algos[0]?.algoName ?? '');
  const algo = algos.find((a) => a.algoName === selected) ?? algos[0];

  useEffect(() => {
    if (algos.length && !algos.some((a) => a.algoName === selected)) {
      setSelected(algos[0].algoName);
    }
  }, [algos, selected]);

  const chartData = summary.map((s) => ({
    algo: s.algoName,
    model: s.slippageModelIgsPct ?? 0,
    close: s.slippageClosePricePct ?? 0,
  }));

  const summaryCols: Column<SlippageSummary>[] = [
    { key: 'algo', header: 'Algo', render: (r) => r.algoName, sortValue: (r) => r.algoName },
    { key: 'model', header: 'Model vs IGS %', numeric: true, render: (r) => <span className={colorClassBySign(r.slippageModelIgsPct)}>{formatPct(r.slippageModelIgsPct)}</span>, sortValue: (r) => r.slippageModelIgsPct ?? 0 },
    { key: 'close', header: 'Close price %', numeric: true, render: (r) => <span className={colorClassBySign(r.slippageClosePricePct)}>{formatPct(r.slippageClosePricePct)}</span>, sortValue: (r) => r.slippageClosePricePct ?? 0 },
    { key: 'cumDaily', header: 'Cum. daily close %', numeric: true, render: (r) => <span className={colorClassBySign(r.cumulativeDailyClosePct)}>{formatPct(r.cumulativeDailyClosePct)}</span>, sortValue: (r) => r.cumulativeDailyClosePct ?? 0 },
    { key: 'cumModel', header: 'Cum. model %', numeric: true, render: (r) => <span className={colorClassBySign(r.cumulativeModelClosePct)}>{formatPct(r.cumulativeModelClosePct)}</span>, sortValue: (r) => r.cumulativeModelClosePct ?? 0 },
    { key: 'modelPnl', header: 'Today model P&L', numeric: true, render: (r) => <span className={colorClassBySign(r.todayModelPnl)}>{formatRs(r.todayModelPnl)}</span>, sortValue: (r) => r.todayModelPnl ?? 0 },
  ];

  const stockCols: Column<SlippageStock>[] = [
    { key: 'symbol', header: 'Symbol', render: (r) => r.symbol, sortValue: (r) => r.symbol },
    { key: 'name', header: 'Name', render: (r) => r.name },
    { key: 'pnl', header: 'Slippage P&L', numeric: true, render: (r) => <span className={colorClassBySign(r.slippagePnlRs)}>{formatRs(r.slippagePnlRs)}</span>, sortValue: (r) => r.slippagePnlRs ?? 0 },
    { key: 'pct', header: 'Slippage %', numeric: true, render: (r) => <span className={colorClassBySign(r.slippagePct)}>{formatPct(r.slippagePct)}</span>, sortValue: (r) => r.slippagePct ?? 0 },
  ];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Execution quality"
        title="How did execution differ from reference prices?"
        answer="Compare model and close-price slippage for the algos present in the current live payload."
        onExport={onExport}
        exporting={exporting}
      />

      <div className="kpi-grid">
        <KpiCard label="Avg model vs IGS %" value={<span className={`mono ${colorClassBySign(avgModelSlippagePct(summary))}`}>{formatPct(avgModelSlippagePct(summary))}</span>} />
        <KpiCard label="Avg close price %" value={<span className={`mono ${colorClassBySign(avgCloseSlippagePct(summary))}`}>{formatPct(avgCloseSlippagePct(summary))}</span>} />
        <KpiCard label="Total today model P&L" value={<span className={`mono ${colorClassBySign(totalTodayModelPnl(summary))}`}>{formatRs(totalTodayModelPnl(summary))}</span>} />
        <KpiCard label="Algos" value={<span className="mono">{summary.length}</span>} />
      </div>

      <section className="block">
        <h3 className="block-title">Model vs close slippage (%)</h3>
        {chartData.length ? (
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="algo" stroke="#9aa1ac" fontSize={12} />
                <YAxis stroke="#9aa1ac" fontSize={12} tickFormatter={(v) => `${v}%`} />
                <Tooltip
                  cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                  content={({ active, payload, label }) =>
                    active && payload?.length ? (
                      <ChartTooltipBox
                        title={String(label)}
                        rows={[
                          { label: 'Model vs IGS', value: formatPct(payload.find((p) => p.dataKey === 'model')?.value as number) },
                          { label: 'Close price', value: formatPct(payload.find((p) => p.dataKey === 'close')?.value as number) },
                        ]}
                      />
                    ) : null
                  }
                />
                <Bar dataKey="model" name="Model vs IGS" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                  {chartData.map((d, i) => (
                    <Cell key={i} fill={d.model >= 0 ? POS : NEG} />
                  ))}
                </Bar>
                <Bar dataKey="close" name="Close price" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                  {chartData.map((d, i) => (
                    <Cell key={i} fill={d.close >= 0 ? POS : NEG} fillOpacity={0.55} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState message="No slippage summary in the current payload." />
        )}
      </section>

      <section className="block">
        <h3 className="block-title">Slippage summary</h3>
        <DataTable columns={summaryCols} rows={summary} initialSortKey="modelPnl" emptyMessage="No slippage summary rows." />
      </section>

      <section className="block">
        <div className="block-head-row">
          <h3 className="block-title">Best &amp; worst stocks by algo</h3>
          {algos.length > 0 && (
            <div className="seg-control" role="tablist">
              {algos.map((a) => (
                <button
                  key={a.algoName}
                  className={`seg ${selected === a.algoName ? 'active' : ''}`}
                  onClick={() => setSelected(a.algoName)}
                  data-testid={`select-algo-${a.algoName.replace(/\s+/g, '-')}`}
                >
                  {a.algoName}
                </button>
              ))}
            </div>
          )}
        </div>

        {algo ? (
          <div className="two-col">
            <div>
              <div className="mini-label pos-label">Top best stocks</div>
              <DataTable columns={stockCols} rows={algo.bestStocks} initialSortKey="pnl" emptyMessage="No best stocks." />
            </div>
            <div>
              <div className="mini-label neg-label">Top worst stocks</div>
              <DataTable columns={stockCols} rows={algo.worstStocks} initialSortKey="pnl" initialSortDir="asc" emptyMessage="No worst stocks." />
            </div>
          </div>
        ) : (
          <EmptyState message="No algo detail in the current payload." />
        )}
      </section>

      <section className="block">
        <h3 className="block-title">Slippage date series</h3>
        {algo?.dateSeries && algo.dateSeries.length ? (
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={algo.dateSeries} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="date" stroke="#9aa1ac" fontSize={12} />
                <YAxis stroke="#9aa1ac" fontSize={12} tickFormatter={(v) => `${v}%`} />
                <Line type="monotone" dataKey="slippagePct" stroke="#7c8bff" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState title="No date series" message="Date-series slippage was not included in the current payload." />
        )}
      </section>
    </div>
  );
}
