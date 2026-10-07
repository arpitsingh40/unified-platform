import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { TopBar } from '../components/TopBar';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Loader2, Clock, CheckCircle2, Target, ArrowRight, ListChecks } from 'lucide-react';

const MODE_LABEL = { answer: 'Answer', decide: 'Decision', plan: 'Plan' };
// Due-time options for committing a move
const DUE_OPTIONS = [
  { label: 'Today', hours: 8 },
  { label: '24h', hours: 24 },
  { label: '48h', hours: 48 },
  { label: '3 days', hours: 72 },
  { label: '1 week', hours: 168 },
];
// Parse a due date, handling missing timezone
const parseDue = (iso) => {
  if (!iso) return null;
  const hasTz = /[zZ]|[+-]\d{2}:\d{2}$/.test(iso);
  return new Date(hasTz ? iso : `${iso}Z`);
};
// Format time left until an action is due
const fmtLeft = (iso) => {
  const dt = parseDue(iso);
  if (!dt) return '';
  const ms = dt.getTime() - Date.now();
  const overdue = ms < 0;
  const m = Math.abs(Math.round(ms / 60000));
  const d = Math.floor(m / 1440); const h = Math.floor((m % 1440) / 60); const mm = m % 60;
  const txt = d > 0 ? `${d}d ${h}h` : h > 0 ? `${h}h ${mm}m` : `${mm}m`;
  return overdue ? `${txt} overdue` : `${txt} left`;
};

// Render a stat card
const Stat = ({ label, value, accent }) => (
  <div className="rounded-2xl border bg-surface p-4">
    <div className="text-xs text-muted mb-1">{label}</div>
    <div className={`font-display text-2xl leading-none ${accent || ''}`}>{value}</div>
  </div>
);

// List committed decisions with status actions
export default function DecisionsPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('open');
  const [busy, setBusy] = useState(null);
  const [resultFor, setResultFor] = useState(null);
  const [resultText, setResultText] = useState('');
  const [dueFor, setDueFor] = useState(null);
  const [dueHours, setDueHours] = useState(48);

  // Load the user's decision list
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/brain/decisions');
      setRows(r.data.decisions || []);
    } catch (_e) { /* noop */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const stats = {
    total: rows.length,
    done: rows.filter((d) => d.status === 'done').length,
    open: rows.filter((d) => d.committed_action && d.status === 'open').length,
  };

  const filtered = rows.filter((d) => {
    if (filter === 'open') return d.committed_action && d.status === 'open';
    if (filter === 'done') return d.status === 'done';
    return true;
  });

  // Commit a next action with a due window
  const commit = async (id, action) => {
    setBusy(id);
    try {
      await api.post(`/brain/decisions/${id}/commit`, { action, due_in_hours: dueHours });
      setDueFor(null);
      window.dispatchEvent(new Event('sdg-actions-changed'));
      toast.success('Committed. The clock is running.');
      load();
    } catch (_e) { toast.error('Could not commit.'); }
    finally { setBusy(null); }
  };

  // Mark a decision done or dropped
  const setStatus = async (id, status, result) => {
    setBusy(id);
    try {
      await api.post(`/brain/decisions/${id}/status`, { status, result: result || null });
      setResultFor(null); setResultText('');
      window.dispatchEvent(new Event('sdg-actions-changed'));
      toast.success(status === 'done' ? 'Logged. Your founder can see it too.' : 'Noted.');
      load();
    } catch (_e) { toast.error('Could not update.'); }
    finally { setBusy(null); }
  };

  // Open the workspace for the next step
  const nextStep = async (id) => {
    setBusy(id);
    try {
      const r = await api.post(`/brain/decisions/${id}/next-step`);
      sessionStorage.setItem('sdg_workspace_seed', JSON.stringify(r.data));
      navigate('/app');
    } catch (e) { toast.error(e?.response?.data?.detail || 'Could not find the next step.'); }
    finally { setBusy(null); }
  };

  return (
    <div className="min-h-screen">
      <TopBar />
      <main data-testid="decisions-page" className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-6">
        <div>
          <h2 className="font-display text-3xl sm:text-4xl tracking-[-0.02em] leading-[1.05]">My decisions</h2>
          <p className="mt-2 text-sm text-muted">Every move you committed to, the clock on it, and what came of it.</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3" data-testid="decisions-stats">
          <Stat label="Open commitments" value={stats.open} accent="text-[hsl(var(--ring))]" />
          <Stat label="Achieved" value={stats.done} accent="text-emerald-600" />
          <Stat label="Total decisions" value={stats.total} />
        </div>

        <div className="flex items-center gap-2">
          {[['open', 'Open'], ['done', 'Achieved'], ['all', 'All']].map(([k, label]) => (
            <button key={k} data-testid={`decisions-filter-${k}`} onClick={() => setFilter(k)}
              className={`text-xs rounded-full px-3 py-1 border transition-colors ${filter === k ? 'bg-primary text-primary-foreground border-primary' : 'border-hairline/70 text-muted hover:text-foreground'}`}>
              {label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="space-y-3 py-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-20 animate-pulse rounded-2xl bg-primary/10" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-2xl border bg-surface p-10 text-center">
            <ListChecks size={22} className="mx-auto text-muted mb-3" />
            <p className="text-sm text-muted">Nothing here yet.</p>
            <Button className="rounded-xl mt-4" onClick={() => navigate('/app')}>Go to your Workspace</Button>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((d) => {
              const committed = d.committed_action && d.status !== 'dropped';
              return (
                <div key={d.id} data-testid="decision-row" className="rounded-2xl border bg-surface p-5 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <button onClick={() => navigate(`/app/brain/${d.id}`)}
                      className="text-sm text-foreground/90 min-w-0 text-left hover:text-[hsl(var(--ring))] transition-colors cursor-pointer" title={d.question}>
                      {d.question}
                    </button>
                    <Badge variant="outline" className="rounded-lg border-hairline/70 shrink-0 text-xs">{MODE_LABEL[d.mode] || 'Answer'}</Badge>
                  </div>

                  {committed ? (
                    <div className="rounded-xl border border-hairline/70 bg-secondary/30 px-4 py-3">
                      <div className="flex items-center justify-between gap-3 flex-wrap">
                        <div className="min-w-0">
                          <div className="text-[11px] uppercase tracking-wide text-muted flex items-center gap-1"><Target size={12} /> Your move</div>
                          <p className={`text-sm ${d.status === 'done' ? 'line-through text-muted' : ''}`}>{d.committed_action}</p>
                        </div>
                        {d.status === 'open' && d.due_at && (
                          <span className="text-xs font-mono-plex inline-flex items-center gap-1 text-[hsl(var(--ring))] shrink-0"><Clock size={12} /> {fmtLeft(d.due_at)}</span>
                        )}
                      </div>

                      {d.status === 'done' ? (
                        <div className="mt-3">
                          {d.result ? (
                            <p className="text-sm"><span className="text-[11px] uppercase tracking-wide text-emerald-600 inline-flex items-center gap-1 mr-1"><CheckCircle2 size={12} /> Result</span> {d.result}</p>
                          ) : <span className="text-xs text-emerald-600 inline-flex items-center gap-1"><CheckCircle2 size={12} /> Done</span>}
                          <Button data-testid="decision-next-step" size="sm" disabled={busy === d.id} onClick={() => nextStep(d.id)} className="rounded-xl mt-3">
                            {busy === d.id ? <Loader2 size={14} className="animate-spin mr-2" /> : <ArrowRight size={14} className="mr-2" />} Find my next step
                          </Button>
                        </div>
                      ) : resultFor === d.id ? (
                        <div className="mt-3 space-y-2">
                          <textarea data-testid="decision-result-input" value={resultText} onChange={(e) => setResultText(e.target.value)}
                            placeholder="What happened? The outcome in a line or two…"
                            className="w-full rounded-lg border border-hairline/70 bg-background px-3 py-2 text-sm min-h-[60px] focus:outline-none focus:ring-1 focus:ring-ring" />
                          <div className="flex gap-2 justify-end">
                            <Button size="sm" variant="ghost" onClick={() => setResultFor(null)} className="rounded-xl text-muted">Cancel</Button>
                            <Button data-testid="decision-result-save" size="sm" disabled={busy === d.id} onClick={() => setStatus(d.id, 'done', resultText)} className="rounded-xl">Log result</Button>
                          </div>
                        </div>
                      ) : (
                        <div className="mt-3 flex gap-2">
                          <Button data-testid="decision-mark-done" size="sm" disabled={busy === d.id} onClick={() => { setResultFor(d.id); setResultText(''); }} className="rounded-xl">I did it</Button>
                          <Button size="sm" variant="ghost" disabled={busy === d.id} onClick={() => setStatus(d.id, 'dropped')} className="rounded-xl text-muted">Dropped it</Button>
                        </div>
                      )}
                    </div>
                  ) : (
                    d.status !== 'dropped' && (
                      <div>
                        {dueFor === d.id ? (
                          <div className="rounded-xl border border-hairline/70 bg-background px-4 py-3 space-y-2">
                            <p className="text-sm">{d.next_action || 'Commit your next move'}</p>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-[11px] uppercase tracking-wide text-muted flex items-center gap-1"><Clock size={12} /> Done by</span>
                              {DUE_OPTIONS.map((o) => (
                                <button key={o.hours} onClick={() => setDueHours(o.hours)}
                                  className={`text-xs rounded-full px-3 py-1 border transition-colors ${dueHours === o.hours ? 'bg-primary text-primary-foreground border-primary' : 'border-hairline/70 text-muted hover:text-foreground'}`}>
                                  {o.label}
                                </button>
                              ))}
                              <Button data-testid="decision-commit-btn" size="sm" disabled={busy === d.id} onClick={() => commit(d.id, d.next_action || d.recommendation || 'My next move')} className="rounded-xl ml-auto">Commit it</Button>
                            </div>
                          </div>
                        ) : (
                          <Button data-testid="decision-commit-open" size="sm" variant="secondary" onClick={() => { setDueFor(d.id); setDueHours(48); }} className="rounded-xl border border-hairline/70">
                            Commit a move
                          </Button>
                        )}
                      </div>
                    )
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
