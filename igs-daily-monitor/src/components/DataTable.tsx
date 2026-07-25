import { useMemo, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronUp, ChevronsUpDown } from 'lucide-react';

export type Column<T> = {
  key: string;
  header: string;
  /** Render cell content. */
  render: (row: T) => ReactNode;
  /** Right-align (numeric). */
  numeric?: boolean;
  /** Value used for sorting; enables sorting when provided. */
  sortValue?: (row: T) => number | string;
};

type Props<T> = {
  columns: Column<T>[];
  rows: T[];
  /** Initial sort column key. */
  initialSortKey?: string;
  initialSortDir?: 'asc' | 'desc';
  emptyMessage?: string;
  maxHeight?: number;
  stickyHeader?: boolean;
};

export default function DataTable<T>({
  columns,
  rows,
  initialSortKey,
  initialSortDir = 'desc',
  emptyMessage = 'No data available.',
  maxHeight,
}: Props<T>) {
  const [sortKey, setSortKey] = useState<string | undefined>(initialSortKey);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>(initialSortDir);

  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    const col = columns.find((c) => c.key === sortKey);
    if (!col?.sortValue) return rows;
    const copy = [...rows];
    copy.sort((a, b) => {
      const va = col.sortValue!(a);
      const vb = col.sortValue!(b);
      let cmp = 0;
      if (typeof va === 'number' && typeof vb === 'number') cmp = va - vb;
      else cmp = String(va).localeCompare(String(vb));
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return copy;
  }, [rows, columns, sortKey, sortDir]);

  const toggleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  if (rows.length === 0) {
    return (
      <div className="table-wrap">
        <div className="empty-state">
          <div className="es-title">No rows to show</div>
          <div className="es-sub">{emptyMessage}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="table-wrap" style={maxHeight ? { maxHeight } : undefined}>
      <table>
        <thead>
          <tr>
            {columns.map((c) => {
              const sortable = !!c.sortValue;
              const active = sortKey === c.key;
              return (
                <th
                  key={c.key}
                  className={`${c.numeric ? 'right' : ''} ${sortable ? 'sortable' : ''}`}
                  onClick={sortable ? () => toggleSort(c.key) : undefined}
                >
                  <span className="th-inner">
                    {c.header}
                    {sortable &&
                      (active ? (
                        sortDir === 'asc' ? (
                          <ChevronUp size={13} />
                        ) : (
                          <ChevronDown size={13} />
                        )
                      ) : (
                        <ChevronsUpDown size={13} style={{ opacity: 0.4 }} />
                      ))}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.key} className={c.numeric ? 'right cell-mono' : ''}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
