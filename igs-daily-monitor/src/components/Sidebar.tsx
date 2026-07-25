import {
  LayoutDashboard,
  TrendingDown,
  ShieldAlert,
  GitCompareArrows,
  PieChart,
  HeartPulse,
} from 'lucide-react';
import StatusPill from './StatusPill';
import { useData } from '../DataContext';
import { formatDate, formatDateTime } from '../utils/format';
import { breachCount } from '../utils/derive';

export type PageKey =
  | 'overview'
  | 'slippage'
  | 'alerts'
  | 'drift'
  | 'exposure'
  | 'health';

const NAV: { key: PageKey; label: string; icon: typeof LayoutDashboard }[] = [
  { key: 'overview', label: 'Overview', icon: LayoutDashboard },
  { key: 'slippage', label: 'Slippage', icon: TrendingDown },
  { key: 'alerts', label: 'Alerts & Risk', icon: ShieldAlert },
  { key: 'drift', label: 'Price / Cost Drift', icon: GitCompareArrows },
  { key: 'exposure', label: 'Exposure', icon: PieChart },
  { key: 'health', label: 'Data Health', icon: HeartPulse },
];

export default function Sidebar({
  active,
  onNavigate,
}: {
  active: PageKey;
  onNavigate: (p: PageKey) => void;
}) {
  const { data, status } = useData();

  const pill =
    status === 'loaded'
      ? { variant: 'green' as const, label: 'Data loaded' }
      : status === 'missing'
        ? { variant: 'amber' as const, label: 'Sample fallback' }
        : status === 'failed'
          ? { variant: 'red' as const, label: 'Load failed' }
          : { variant: 'muted' as const, label: 'Loading…' };

  const missing = data.dataHealth.sectionsMissing.length;
  const snapshotPill =
    status === 'loaded' && missing > 0
      ? { variant: 'amber' as const, label: `${missing} sections missing` }
      : pill;

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <div className="brand">
          <span className="brand-mark" aria-hidden>
            {/* simple geometric monogram */}
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <rect x="2" y="2" width="20" height="20" rx="5" stroke="currentColor" strokeWidth="1.6" />
              <path d="M7 15l3-4 3 3 4-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <div className="brand-text">IGS Daily Monitor</div>
        </div>
        <div className="business-date mono" data-testid="text-business-date">
          {formatDate(data.businessDate)}
        </div>
        <div className="sidebar-status">
          <StatusPill variant={snapshotPill.variant} label={snapshotPill.label} />
        </div>
      </div>

      <nav className="nav">
        {NAV.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            className={`nav-item ${active === key ? 'active' : ''}`}
            onClick={() => onNavigate(key)}
            data-testid={`nav-${key}`}
          >
            <Icon size={16} strokeWidth={1.8} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-foot">
        <div className="snapshot-title">Snapshot</div>
        <SnapshotRow label="Algos" value={String(data.slippage.summary.length)} />
        <SnapshotRow label="Hard breaches" value={String(breachCount(data))} tone={breachCount(data) > 0 ? 'neg' : 'pos'} />
        <SnapshotRow label="Stop-loss watch" value={String(data.risk.stopLossWatch.length)} />
        <SnapshotRow label="Generated" value={formatDateTime(data.generatedAt)} small />
      </div>
    </aside>
  );
}

function SnapshotRow({
  label,
  value,
  tone,
  small,
}: {
  label: string;
  value: string;
  tone?: 'pos' | 'neg';
  small?: boolean;
}) {
  return (
    <div className="snapshot-row">
      <span className="snapshot-label">{label}</span>
      <span className={`snapshot-value mono ${tone ?? ''} ${small ? 'small' : ''}`}>{value}</span>
    </div>
  );
}
