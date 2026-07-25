import type { ReactNode } from 'react';

type Props = {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  valueClass?: string;
  icon?: ReactNode;
};

export default function KpiCard({ label, value, sub, valueClass, icon }: Props) {
  return (
    <div className="kpi-card">
      <div className="kpi-label">
        {icon}
        {label}
      </div>
      <div className={`kpi-value ${valueClass ?? ''}`}>{value}</div>
      {sub !== undefined && sub !== null && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}
