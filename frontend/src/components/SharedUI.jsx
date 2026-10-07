// Shared skeleton loader — standardized across all pages.
// Usage: <PageSkeleton rows={5} /> or <PageSkeleton type="card" count={4} />
export function PageSkeleton({ rows = 4, type = 'rows' }) {
  if (type === 'card') return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3" aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-24 rounded-2xl animate-pulse bg-surface-2" />
      ))}
    </div>
  );
  return (
    <div className="space-y-3" aria-hidden="true" role="status" aria-label="Loading">
      <div className="h-8 w-48 rounded-md animate-pulse bg-surface-2" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-12 rounded-xl animate-pulse bg-surface-2" style={{ animationDelay: `${i * 100}ms` }} />
      ))}
      <span className="sr-only">Loading...</span>
    </div>
  );
}

// Empty state with next-action guidance
export function EmptyState({ icon: Icon, title, description, action, actionLabel, onAction, testid }) {
  return (
    <div data-testid={testid} className="text-center py-16 px-6">
      <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl border border-hairline bg-surface-2 mb-4 text-muted">
        <Icon size={22} strokeWidth={1.5} />
      </div>
      <h3 className="text-sm font-medium text-text">{title}</h3>
      <p className="text-xs text-muted mt-1.5 max-w-xs mx-auto leading-relaxed">{description}</p>
      {action && (
        <button onClick={onAction} className="mt-4 text-xs text-accent hover:underline font-medium">
          {actionLabel || 'Get started'} →
        </button>
      )}
    </div>
  );
}
