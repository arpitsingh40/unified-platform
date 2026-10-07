import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { TopBar } from '../components/TopBar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import {
  Loader2, Lock, Search, History, Filter, ChevronDown,
  Activity, Brain, Wrench, Users, CreditCard, AlertTriangle,
  CheckCircle2, XCircle, Clock, Zap, Play, ArrowRight, Info
} from 'lucide-react';

// Icons per audit event type
const typeIcons = {
  agent_decision: Brain,
  agent_execution: Zap,
  agent_execution_result: Zap,
  business_cycle: Activity,
  business_process_run: Play,
  tool_connected: Wrench,
  tool_disconnected: Wrench,
  task_proposed: Clock,
  task_approved: CheckCircle2,
  task_executed: Play,
  task_verified: CheckCircle2,
  task_failed: XCircle,
  approval_requested: Clock,
  approval_approved: CheckCircle2,
  approval_denied: XCircle,
  system_scan: Activity,
  thread_turn: Brain,
  credit_spent: CreditCard,
  member_joined: Users,
  warning: AlertTriangle,
  error: XCircle,
};

// Labels per audit event type
const typeLabels = {
  agent_decision: 'Agent Decision',
  agent_execution: 'Agent Execution',
  agent_execution_result: 'Execution Result',
  business_cycle: 'Business Cycle',
  business_process_run: 'Process Run',
  tool_connected: 'Tool Connected',
  tool_disconnected: 'Tool Disconnected',
  task_proposed: 'Task Proposed',
  task_approved: 'Task Approved',
  task_executed: 'Task Executed',
  task_verified: 'Task Verified',
  task_failed: 'Task Failed',
  approval_requested: 'Approval Requested',
  approval_approved: 'Approval Approved',
  approval_denied: 'Approval Denied',
  system_scan: 'System Scan',
  thread_turn: 'Thread Turn',
  credit_spent: 'Credit Spent',
  credit_granted: 'Credit Granted',
  member_joined: 'Member Joined',
  member_removed: 'Member Removed',
  strategy_updated: 'Strategy Updated',
  warning: 'Warning',
  error: 'Error',
};

// Badge color per severity level
const sevBadge = (s) => {
  const m = {
    info: 'bg-slate-50 text-slate-600 border-slate-200',
    warning: 'bg-amber-50 text-amber-600 border-amber-200',
    error: 'bg-red-50 text-red-600 border-red-200',
    critical: 'bg-red-100 text-red-700 border-red-300',
  };
  return m[s] || m.info;
};

// Organization audit trail page
export default function RecordRoomPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [denied, setDenied] = useState(false);
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState(null);
  const [types, setTypes] = useState([]);
  const [filter, setFilter] = useState({ type: '', search: '', severity: '' });
  const [showFilters, setShowFilters] = useState(false);
  const [limit, setLimit] = useState(50);

  // Load audit events with filters
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit };
      if (filter.type) params.event_type = filter.type;
      if (filter.search) params.search = filter.search;
      if (filter.severity) params.severity = filter.severity;

      const [auditR, summR, typesR] = await Promise.all([
        api.get('/audit', { params }),
        api.get('/audit/summary', { params: { hours: 24 } }),
        api.get('/audit/types'),
      ]);
      setEvents(auditR.data?.events || []);
      setTotal(auditR.data?.total || 0);
      setSummary(summR.data);
      setTypes(typesR.data?.types || []);
    } catch (e) {
      if (e?.response?.status === 403) setDenied(true);
    } finally {
      setLoading(false);
    }
  }, [filter, limit]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="min-h-screen">
        <TopBar title="Record Room" backTo="/app" />
        <div className="max-w-4xl mx-auto px-4 py-10 space-y-4">
          <div className="h-8 w-48 animate-pulse rounded-md bg-primary/10" />
          <div className="space-y-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-14 animate-pulse rounded-xl bg-primary/10" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (denied) {
    return (
      <div className="min-h-screen">
        <TopBar title="Record Room" backTo="/app" />
        <div data-testid="record-room-denied" className="max-w-md mx-auto text-center py-24 px-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl border mb-4 text-muted">
            <Lock size={20} />
          </div>
          <h2 className="font-display text-xl">Workspace required</h2>
          <p className="text-sm text-muted mt-2">Record Room requires an organization workspace.</p>
          <Button variant="secondary" className="rounded-xl mt-6" onClick={() => navigate('/app/team')}>
            Go to workspace
          </Button>
        </div>
      </div>
    );
  }

  // Pick the icon for an event type
  const IconFor = (type) => {
    const I = typeIcons[type] || Info;
    return <I size={14} strokeWidth={1.75} />;
  };

  return (
    <div className="min-h-screen">
      <TopBar title="Record Room" backTo="/app/business-os" />
      <main data-testid="record-room-page" className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-5">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl flex items-center gap-2">
              <History size={22} strokeWidth={1.5} /> Record Room
            </h1>
            <p className="text-sm text-muted mt-1">
              Every decision, execution, and event — audit trail for your organization.
            </p>
          </div>
        </div>

        {/* Summary chips */}
        {summary && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] text-muted">
              Last 24h: <span className="font-medium text-foreground">{summary.total || 0} events</span>
            </span>
            {summary.by_severity?.error > 0 && (
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-red-50 text-red-700 border border-red-200">
                {summary.by_severity.error} errors
              </span>
            )}
            {summary.by_severity?.warning > 0 && (
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                {summary.by_severity.warning} warnings
              </span>
            )}
          </div>
        )}

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-0 sm:min-w-[200px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <Input
              data-testid="record-room-search"
              placeholder="Search events..."
              value={filter.search}
              onChange={(e) => setFilter(f => ({ ...f, search: e.target.value }))}
              className="pl-9 rounded-xl text-sm"
            />
          </div>
          <Button
            variant="secondary"
            size="sm"
            className="rounded-xl"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter size={13} className="mr-1" /> Filter {showFilters ? <ChevronDown size={12} className="ml-1 rotate-180" /> : <ChevronDown size={12} className="ml-1" />}
          </Button>
        </div>

        {showFilters && (
          <div className="flex flex-wrap gap-2">
            <select
              data-testid="record-room-type-filter"
              value={filter.type}
              onChange={(e) => setFilter(f => ({ ...f, type: e.target.value }))}
              className="rounded-xl border bg-surface px-3 py-1.5 text-xs"
            >
              <option value="">All event types</option>
              {types.map(t => (
                <option key={t} value={t}>{typeLabels[t] || t}</option>
              ))}
            </select>
            <select
              data-testid="record-room-severity-filter"
              value={filter.severity}
              onChange={(e) => setFilter(f => ({ ...f, severity: e.target.value }))}
              className="rounded-xl border bg-surface px-3 py-1.5 text-xs"
            >
              <option value="">All severities</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
            </select>
            <Button variant="ghost" size="sm" className="rounded-xl text-xs" onClick={() => setFilter({ type: '', search: '', severity: '' })}>
              Clear filters
            </Button>
          </div>
        )}

        {/* Event list */}
        <div className="rounded-2xl border divide-y">
          {events.length === 0 && (
            <div className="py-16 text-center text-sm text-muted">
              <History size={24} className="mx-auto mb-2 opacity-30" />
              No events found. Events will appear here as your organization operates.
            </div>
          )}
          {events.map((ev) => {
            const ts = ev.created_at ? new Date(ev.created_at).toLocaleString() : '';
            return (
              <div key={ev.id} data-testid="audit-event-row"
                className="flex items-start gap-3 px-4 py-3 hover:bg-surface-2/50 transition-colors">
                <div className={`mt-0.5 shrink-0 ${ev.severity === 'error' ? 'text-red-500' : ev.severity === 'warning' ? 'text-amber-500' : 'text-muted'}`}>
                  {IconFor(ev.event_type)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full border text-muted">
                      {typeLabels[ev.event_type] || ev.event_type}
                    </span>
                    {ev.severity !== 'info' && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${sevBadge(ev.severity)}`}>
                        {ev.severity}
                      </span>
                    )}
                    <span className="text-[10px] text-muted/70">{ts}</span>
                  </div>
                  <p className="text-sm mt-1 leading-relaxed">{ev.summary}</p>
                  {ev.actor_id && (
                    <p className="text-[11px] text-muted mt-0.5">
                      by {ev.actor_type}:{ev.actor_id}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Pagination */}
        {total > limit && (
          <div className="text-center">
            <Button
              variant="secondary"
              size="sm"
              className="rounded-xl"
              onClick={() => setLimit(l => l + 50)}
            >
              Load more ({total - events.length} remaining)
            </Button>
          </div>
        )}

      </main>
    </div>
  );
}
