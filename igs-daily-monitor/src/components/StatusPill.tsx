type Variant = 'green' | 'amber' | 'red' | 'muted';

export default function StatusPill({ variant, label }: { variant: Variant; label: string }) {
  return (
    <span className={`status-pill ${variant}`}>
      <span className="dot" />
      {label}
    </span>
  );
}
