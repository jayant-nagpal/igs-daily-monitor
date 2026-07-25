import type { ReactNode } from 'react';

type Row = { label: string; value: ReactNode };

export function ChartTooltipBox({ title, rows }: { title: string; rows: Row[] }) {
  return (
    <div className="chart-tooltip">
      <div className="ct-title">{title}</div>
      {rows.map((r, i) => (
        <div className="ct-row" key={i}>
          <span>{r.label}</span>
          <span style={{ color: 'var(--text)' }}>{r.value}</span>
        </div>
      ))}
    </div>
  );
}
