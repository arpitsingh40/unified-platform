import { useState, useEffect, useCallback } from 'react';
import {
  Book, ChevronDown, ChevronRight, MessageSquare, Search,
  User, RefreshCw, BrainCircuit, FileText, ArrowLeft,
  Target, Activity
} from 'lucide-react';
import { api } from '../lib/api';
import { toast } from 'sonner';
import { fmt, fmtDate, Stat, Th, Td, Pager } from '../lib/admin-ui';

// ---------------------------------------------------------------- Chapter (user) component
function Chapter({ user, threads, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen);

  const activeThreads = threads.filter((t) => t.status === 'active').length;
  const totalTurns = threads.reduce((s, t) => s + t.turn_count, 0);

  return (
    <div className="bg-white border border-hairline/70 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-secondary/40 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          {open ? <ChevronDown size={15} className="shrink-0 text-muted" /> : <ChevronRight size={15} className="shrink-0 text-muted" />}
          <div className="w-7 h-7 rounded-full bg-[hsl(var(--accent))] flex items-center justify-center shrink-0">
            <User size={13} />
          </div>
          <div className="min-w-0">
            <span className="text-sm font-medium">{user.name || user.email || 'Unknown'}</span>
            <span className="block text-[11px] text-muted truncate">{user.email}{user.country ? ` · ${user.country}` : ''}</span>
          </div>
        </div>
        <div className="flex items-center gap-4 shrink-0 ml-4">
          <span className="text-xs text-muted whitespace-nowrap">{threads.length} threads</span>
          <span className="text-xs text-muted whitespace-nowrap hidden sm:inline">{fmt(totalTurns)} turns</span>
          {activeThreads > 0 && (
            <span className="text-[10px] uppercase tracking-wider bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full px-2 py-0.5">
              {activeThreads} active
            </span>
          )}
        </div>
      </button>

      {open && (
        <div className="divide-y divide-border/40 border-t border-hairline/40">
          {threads.length === 0 && (
            <p className="px-4 py-6 text-xs text-muted text-center">No conversations yet.</p>
          )}
          {threads.map((t) => (
            <ThreadRow key={t.thread_id} thread={t} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Thread row
function ThreadRow({ thread }) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadDetail = useCallback(() => {
    if (detail || loading) return;
    setLoading(true);
    api.get(`/admin/conversations/${thread.thread_id}`)
      .then((r) => { setDetail(r.data); setLoading(false); })
      .catch(() => { setLoading(false); toast.error('Failed to load thread'); });
  }, [thread.thread_id, detail, loading]);

  useEffect(() => {
    if (expanded && !detail && !loading) loadDetail();
  }, [expanded, detail, loading, loadDetail]);

  const STATUS_STYLE = {
    active: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    paused: 'bg-amber-50 text-amber-700 border-amber-200',
    graduated: 'bg-blue-50 text-blue-700 border-blue-200',
    released: 'bg-secondary text-muted border-hairline/70',
  };

  return (
    <div>
      <button
        onClick={() => { setExpanded(!expanded); if (!expanded) loadDetail(); }}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-secondary/40 transition-colors text-left gap-3"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          {expanded ? <ChevronDown size={13} className="shrink-0 text-muted" /> : <ChevronRight size={13} className="shrink-0 text-muted" />}
          <MessageSquare size={13} className="shrink-0 text-muted" />
          <span className="text-sm truncate">{thread.goal || 'Untitled'}</span>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className={`inline-block px-2 py-0.5 rounded-md text-[10px] uppercase tracking-wider border ${STATUS_STYLE[thread.status] || 'bg-secondary text-muted border-hairline/70'}`}>
            {thread.status}
          </span>
          <span className="text-[11px] text-muted hidden sm:inline">{fmt(thread.turn_count)} turns</span>
          <span className="text-[11px] text-muted hidden md:inline">{fmtDate(thread.last_turn_at)}</span>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-hairline/40 bg-secondary/30 px-4 py-3">
          {loading && <p className="text-xs text-muted">Loading…</p>}
          {detail && (
            <div className="space-y-2 text-xs">
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted">
                {detail.thread.why_now && <span><span className="text-foreground">Why now:</span> {detail.thread.why_now}</span>}
                <span><span className="text-foreground">Phase:</span> {detail.thread.phase || '—'}</span>
                <span><span className="text-foreground">Messages:</span> {detail.thread.messages.length}</span>
                <span><span className="text-foreground">Opened:</span> {fmtDate(detail.thread.opened_at)}</span>
              </div>

              <div className="mt-3 max-h-[400px] overflow-y-auto space-y-2 border border-hairline/40 rounded-lg bg-white p-2">
                {detail.thread.messages.length === 0 && (
                  <p className="text-xs text-muted text-center py-4">No messages in this thread.</p>
                )}
                {detail.thread.messages.map((m, i) => (
                  <div key={i} className={`border-l-2 pl-3 py-1 ${m.role === 'user' ? 'border-blue-300' : 'border-emerald-300'}`}>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] uppercase tracking-wider font-medium text-muted">
                        {m.role === 'user' ? '🧑 You' : '🤖 Assistant'}
                      </span>
                      <span className="text-[10px] text-muted/70">{fmtDate(m.at)}</span>
                      {m.intent && <span className="text-[10px] bg-secondary px-1.5 py-0.5 rounded text-muted">{m.intent}</span>}
                    </div>
                    <p className="text-[12px] mt-0.5 whitespace-pre-wrap break-words">{m.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Memory card sections
function UnderstandingCard({ understanding }) {
  if (!understanding?.current) return null;
  const u = understanding.current;
  const fields = [
    { label: 'Focus', key: 'focus' },
    { label: 'Fears', key: 'fears', warn: true },
    { label: 'Blockers', key: 'blockers', warn: true },
    { label: 'Constraints', key: 'constraints' },
    { label: 'Tried', key: 'tried' },
    { label: 'Motivators', key: 'motivators' },
    { label: 'Stage', key: 'stage' },
    { label: 'Gap to goal', key: 'gap_to_goal' },
    { label: 'Emotional read', key: 'emotional_read' },
    { label: 'Needs now', key: 'needs_now' },
  ];
  const filled = fields.filter((f) => u[f.key]?.trim());
  if (filled.length === 0) return null;
  return (
    <div className="bg-white border border-hairline/70 rounded-xl p-4">
      <div className="flex items-center gap-1.5 mb-2.5">
        <BrainCircuit size={14} className="text-muted" />
        <p className="text-[10px] uppercase tracking-[0.12em] text-muted">Living memory</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5">
        {filled.map((f) => (
          <div key={f.key}>
            <span className="text-[11px] text-muted">{f.label}: </span>
            <span className={`text-[12px] ${f.warn && u[f.key] !== 'empty' ? 'text-amber-700' : ''}`}>{u[f.key] || '—'}</span>
          </div>
        ))}
      </div>
      {understanding.fear_evolution?.length > 1 && (
        <details className="mt-2.5">
          <summary className="text-[11px] text-muted cursor-pointer hover:text-foreground">Fear evolution ({understanding.fear_evolution.length} snapshots)</summary>
          <div className="mt-1.5 max-h-32 overflow-y-auto space-y-1">
            {understanding.fear_evolution.map((f, i) => (
              <p key={i} className="text-[11px] text-muted border-l-2 border-hairline pl-2">{f}</p>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

// Card showing the dominant behavioral pattern for a user.
function PatternsCard({ patterns }) {
  if (!patterns) return null;
  const p = patterns.current || {};
  if (!p.pattern_type) return null;
  return (
    <div className="bg-white border border-hairline/70 rounded-xl p-4">
      <div className="flex items-center gap-1.5 mb-2">
        <Activity size={14} className="text-muted" />
        <p className="text-[10px] uppercase tracking-[0.12em] text-muted">Behavioral pattern</p>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-sm font-medium capitalize">{p.pattern_type.replace('_', ' ')}</span>
        <span className="text-[11px] text-muted">confidence {Math.round((p.confidence || 0) * 100)}%</span>
        {p.evidence_count > 0 && <span className="text-[11px] text-muted">· {p.evidence_count} clues</span>}
      </div>
      {p.observation && <p className="text-[12px] text-muted mt-1">{p.observation}</p>}
      <div className="flex gap-3 mt-2 text-[11px] text-muted">
        <span>{fmt(patterns.total_turns || 0)} total turns</span>
        <span>{fmt(patterns.vulnerability_count || 0)} vulnerabilities</span>
      </div>
    </div>
  );
}

// Card summarizing decisions committed and their outcomes.
function DecisionsCard({ decisions }) {
  if (!decisions) return null;
  if (decisions.total === 0) return null;
  const oc = decisions.outcomes || {};
  return (
    <div className="bg-white border border-hairline/70 rounded-xl p-4">
      <div className="flex items-center gap-1.5 mb-2">
        <Target size={14} className="text-muted" />
        <p className="text-[10px] uppercase tracking-[0.12em] text-muted">Decisions & outcomes</p>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        <span>{fmt(decisions.total)} total</span>
        <span>{fmt(decisions.committed)} committed</span>
        <span className="text-emerald-700">{fmt(decisions.done)} done</span>
        <span className="text-red-600">{fmt(decisions.dropped)} dropped</span>
      </div>
      {Object.keys(oc).length > 0 && (
        <div className="flex gap-2 mt-1.5">
          {oc.success > 0 && <span className="text-[11px] bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full px-2 py-0.5">{oc.success} success</span>}
          {oc.partial > 0 && <span className="text-[11px] bg-amber-50 text-amber-700 border border-amber-200 rounded-full px-2 py-0.5">{oc.partial} partial</span>}
          {oc.failed > 0 && <span className="text-[11px] bg-red-50 text-red-700 border border-red-200 rounded-full px-2 py-0.5">{oc.failed} failed</span>}
        </div>
      )}
      {decisions.recent?.length > 0 && (
        <details className="mt-2">
          <summary className="text-[11px] text-muted cursor-pointer hover:text-foreground">Recent decisions</summary>
          <div className="mt-1.5 space-y-1.5 max-h-48 overflow-y-auto">
            {decisions.recent.map((d, i) => (
              <div key={i} className="border-l-2 border-hairline pl-2 py-0.5">
                <p className="text-[11px] font-medium">{d.question?.slice(0, 120)}</p>
                <div className="flex gap-2 text-[10px] text-muted">
                  <span>{d.mode || '—'}</span>
                  {d.status && <span>· {d.status}</span>}
                  {d.outcome?.status && <span>· outcome: {d.outcome.status}</span>}
                  {d.impact_inr && <span>· ₹{fmt(d.impact_inr)}</span>}
                </div>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

// Card displaying emotional temperature and consistency metrics.
function EngagementCard({ engagement, threads }) {
  if (!engagement) return null;
  const { emotional_temperature_avg: temp, execution_consistency_avg: consistency, pace_trend } = engagement;
  if (temp == null && consistency == null) return null;
  const paceColor = pace_trend === 'improving' ? 'text-emerald-700' : pace_trend === 'declining' ? 'text-red-600' : 'text-muted';
  return (
    <div className="bg-white border border-hairline/70 rounded-xl p-4">
      <div className="flex items-center gap-1.5 mb-2">
        <Activity size={14} className="text-muted" />
        <p className="text-[10px] uppercase tracking-[0.12em] text-muted">Engagement</p>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {temp != null && (
          <div>
            <p className="text-[10px] text-muted">Emotional temp</p>
            <p className="text-sm font-mono-plex">{temp.toFixed(2)}</p>
          </div>
        )}
        {consistency != null && (
          <div>
            <p className="text-[10px] text-muted">Consistency</p>
            <p className="text-sm font-mono-plex">{consistency.toFixed(2)}</p>
          </div>
        )}
        <div>
          <p className="text-[10px] text-muted">Pace trend</p>
          <p className={`text-sm font-medium capitalize ${paceColor}`}>{pace_trend || 'stable'}</p>
        </div>
        {threads && (
          <div>
            <p className="text-[10px] text-muted">Active threads</p>
            <p className="text-sm font-mono-plex">{threads.active} / {threads.total}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Memory view
function MemoryView({ onBack }) {
  const [data, setData] = useState(null);
  const [q, setQ] = useState('');

  const load = useCallback(() => {
    api.get('/admin/conversations/memory', { params: { q } }).then((r) => setData(r.data)).catch(() => {});
  }, [q]);

  useEffect(() => { load(); }, [load]);

  const refresh = () => {
    api.post('/admin/conversations/memory/refresh').then((r) => {
      toast.success(r.data.message);
      load();
    }).catch(() => toast.error('Failed to refresh memory'));
  };

  return (
    <div className="mt-6">
      <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-muted hover:text-foreground mb-4">
        <ArrowLeft size={13} /> Back to conversations
      </button>

      <div className="flex items-center gap-3 flex-wrap justify-between">
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Search by user name…"
          className="w-full sm:w-72 bg-white border border-hairline/70 rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))]" />
        <button onClick={refresh}
          className="inline-flex items-center gap-1.5 rounded-xl bg-foreground text-background px-4 py-2 text-xs font-medium hover:opacity-90 transition-opacity">
          <RefreshCw size={13} /> Refresh memory
        </button>
      </div>

      {!data && <p className="text-sm text-muted mt-8">Loading…</p>}

      {data && data.total === 0 && (
        <div className="mt-8 text-center">
          <BrainCircuit size={32} className="mx-auto text-muted/50" />
          <p className="text-sm text-muted mt-2">No memory extracted yet.</p>
          <p className="text-xs text-muted mt-1">Click "Refresh memory" to aggregate understanding, patterns, decisions, and engagement.</p>
        </div>
      )}

      <div className="space-y-3 mt-4">
        {data && data.items.map((m) => (
          <div key={m.user_id} className="bg-secondary/30 border border-hairline/70 rounded-xl p-4">
            {/* User header */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-full bg-[hsl(var(--accent))] flex items-center justify-center">
                  <User size={13} />
                </div>
                <div>
                  <h3 className="text-sm font-medium">{m.user_name}</h3>
                  <p className="text-[11px] text-muted">{m.email} · last extracted {fmtDate(m.extracted_at)}</p>
                </div>
              </div>
            </div>

            {/* Cards grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <UnderstandingCard understanding={m.understanding} />
              <PatternsCard patterns={m.patterns} />
              <DecisionsCard decisions={m.decisions} />
              <EngagementCard engagement={m.engagement} threads={m.threads} />
            </div>

            {/* Goals */}
            {m.threads?.goals?.length > 0 && (
              <div className="mt-3">
                <p className="text-[10px] uppercase tracking-[0.12em] text-muted mb-1.5">Goals ({m.threads.total} threads)</p>
                <div className="flex flex-wrap gap-1.5">
                  {m.threads.goals.map((g, i) => (
                    <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-white text-[11px] text-muted border border-hairline/70">
                      <FileText size={10} />
                      {g.goal.slice(0, 60)}{g.goal.length > 60 ? '…' : ''}
                      <span className={`ml-1 text-[9px] uppercase ${g.status === 'active' ? 'text-emerald-600' : 'text-muted/60'}`}>{g.status}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Insights */}
            {m.insights?.length > 0 && (
              <details className="mt-3">
                <summary className="text-[11px] text-muted cursor-pointer hover:text-foreground">
                  Engine insights ({m.insights.length})
                </summary>
                <div className="mt-1.5 max-h-40 overflow-y-auto space-y-1">
                  {m.insights.map((ins, i) => (
                    <p key={i} className="text-[11px] text-muted border-l-2 border-hairline pl-2 py-0.5">{ins.slice(0, 200)}{ins.length > 200 ? '…' : ''}</p>
                  ))}
                </div>
              </details>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- DataTab — main export
export default function DataTab() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [view, setView] = useState('conversations'); // 'conversations' | 'memory'
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(() => {
    api.get('/admin/conversations', { params: { page, limit: 25, q } }).then((r) => setData(r.data)).catch(() => {});
  }, [page, q]);

  useEffect(() => { load(); }, [load]);

  const refreshMemory = async () => {
    setRefreshing(true);
    try {
      const r = await api.post('/admin/conversations/memory/refresh');
      toast.success(r.data.message);
    } catch (e) {
      toast.error('Failed to refresh memory');
    } finally { setRefreshing(false); }
  };

  if (view === 'memory') {
    return (
      <div className="mt-6" data-testid="admin-data">
        <MemoryView onBack={() => setView('conversations')} />
      </div>
    );
  }

  return (
    <div className="mt-6" data-testid="admin-data">
      {/* Stats bar */}
      {data && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <Stat label="Total users" value={fmt(data.total_users)} />
          <Stat label="Total threads" value={fmt(data.total_threads)} />
          <Stat label="Active users" value={fmt(data.chapters.filter(c => c.threads.some(t => t.status === 'active')).length)} />
          <Stat label="Active threads" value={fmt(data.chapters.reduce((s, c) => s + c.threads.filter(t => t.status === 'active').length, 0))} />
        </div>
      )}

      {/* Search + actions */}
      <div className="flex items-center gap-3 flex-wrap justify-between mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }}
            placeholder="Search by user name or email…"
            className="w-full bg-white border border-hairline/70 rounded-xl pl-9 pr-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))]" />
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setView('memory')}
            className="inline-flex items-center gap-1.5 rounded-xl border border-hairline/70 bg-white px-3.5 py-2 text-xs text-muted hover:text-foreground transition-colors">
            <BrainCircuit size={13} /> Memory
          </button>
          <button onClick={refreshMemory} disabled={refreshing}
            className="inline-flex items-center gap-1.5 rounded-xl bg-foreground text-background px-3.5 py-2 text-xs font-medium disabled:opacity-50 hover:opacity-90 transition-opacity">
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} /> {refreshing ? 'Refreshing…' : 'Refresh memory'}
          </button>
        </div>
      </div>

      {/* Book-like structure: chapters = users */}
      {!data && <p className="text-sm text-muted mt-8">Loading…</p>}

      {data && data.chapters.length === 0 && (
        <div className="mt-12 text-center">
          <Book size={40} className="mx-auto text-muted/40" />
          <p className="text-sm text-muted mt-3">No conversations found.</p>
          <p className="text-xs text-muted mt-1">Users will appear here once they start threads.</p>
        </div>
      )}

      {data && (
        <div className="space-y-2">
          {data.chapters.map((ch, i) => (
            <Chapter key={ch.user.id} user={ch.user} threads={ch.threads} defaultOpen={i === 0} />
          ))}
        </div>
      )}

      <Pager page={page} pages={data?.pages || 1} onPage={setPage} />
    </div>
  );
}
