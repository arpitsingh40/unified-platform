// Formats numbers with Indian locale grouping
export const fmt = (n) => (n ?? 0).toLocaleString('en-IN');

// Formats ISO dates for admin tables
export const fmtDate = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z');
  return d.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
};

// Metric card used in admin views
export const Stat = ({ label, value, sub, testId }) => (
  <div data-testid={testId} className="bg-white border border-hairline rounded-xl px-4 py-3.5">
    <p className="text-[10px] uppercase tracking-[0.12em] text-muted">{label}</p>
    <p className="font-mono-plex text-xl mt-1">{value}</p>
    {sub && <p className="text-[11px] text-muted mt-0.5">{sub}</p>}
  </div>
);

// Table header cell with alignment
export const Th = ({ children, right }) => (
  <th className={`px-3 py-2 text-[10px] uppercase tracking-[0.1em] font-medium text-muted ${right ? 'text-right' : 'text-left'}`}>{children}</th>
);

// Table body cell with alignment
export const Td = ({ children, right, mono, className = '' }) => (
  <td className={`px-3 py-2.5 text-[13px] ${right ? 'text-right' : ''} ${mono ? 'font-mono-plex text-xs' : ''} ${className}`}>{children}</td>
);

// Pagination controls for admin tables
export const Pager = ({ page, pages, onPage }) => pages > 1 ? (
  <div className="flex items-center justify-end gap-3 mt-3 text-xs text-muted">
    <button disabled={page <= 1} onClick={() => onPage(page - 1)} className="disabled:opacity-30 hover:text-foreground">← Prev</button>
    <span className="font-mono-plex">{page} / {pages}</span>
    <button disabled={page >= pages} onClick={() => onPage(page + 1)} className="disabled:opacity-30 hover:text-foreground">Next →</button>
  </div>
) : null;
