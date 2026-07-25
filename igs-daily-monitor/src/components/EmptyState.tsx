import { Inbox } from 'lucide-react';
import type { ReactNode } from 'react';

export default function EmptyState({
  title = 'Nothing to show',
  message,
  icon,
}: {
  title?: string;
  message: string;
  icon?: ReactNode;
}) {
  return (
    <div className="empty-state" data-testid="empty-state">
      <div className="es-icon">{icon ?? <Inbox size={20} strokeWidth={1.6} />}</div>
      <div className="es-title">{title}</div>
      <div className="es-sub">{message}</div>
    </div>
  );
}
