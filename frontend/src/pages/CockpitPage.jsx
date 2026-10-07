import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { TopBar } from '../components/TopBar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import {
  Target, Loader2, TrendingUp, CheckCircle2, Users, Activity, AlertTriangle, Lock, Gauge, Clock, Award, Flag, Pencil, ListChecks, RefreshCw, IndianRupee,
  Wifi, WifiOff, Sparkles, Play, StopCircle, ChevronRight, Shield,
} from 'lucide-react';

// Format numbers with Indian locale
const fmtNum = (n) => {
  if (n == null) return '—';
  try { return Number(n).toLocaleString('en-IN'); } catch { return String(n); }
};
// Pick progress color by completion
const statusColor = (pct) => (pct == null ? 'text-muted ' : pct >= 100 ? 'text-emerald-600' : pct >= 60 ? 'text-[hsl(var(--ring))]' : pct >= 25 ? 'text-amber-600' : 'text-muted ');

// Format remaining time until a deadline
const fmtLeft = (iso) => {
  if (!iso) return '';
  const ms = new Date(iso).getTime() - Date.now();
  if (ms < 0) return 'overdue';
  const m = Math.round(ms / 60000);
  const d = Math.floor(m / 1440); const h = Math.floor((m % 1440) / 60);
  return d > 0 ? `${d}d ${h}h left` : `${h || 1}h left`;
};

// Render a stat card with icon and label
const Stat = ({ icon: Icon, label, value, sub }) => (
  <div className="rounded-2xl border bg-surface p-4">
    <div className="flex items-center gap-1.5 text-xs text-muted  mb-1">
      <Icon size={13} strokeWidth={1.75} /> {label}
    </div>
    <div className="font-display text-2xl leading-none">{value}</div>
    {sub ? <div className="text-[11px] text-muted  mt-1">{sub}</div> : null}
  </div>
);

// Pick color by alignment score
const alignColor = (s) => (s == null ? 'text-muted ' : s >= 70 ? 'text-emerald-600' : s >= 40 ? 'text-amber-600' : 'text-red-600');

// Founder cockpit dashboard page
export default function CockpitPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [denied, setDenied] = useState(false);
  const [data, setData] = useState(null);
  const [arrInput, setArrInput] = useState('');
  const [savingArr, setSavingArr] = useState(false);
  const [editingArr, setEditingArr] = useState(false);
  const [weeklyDigest, setWeeklyDigest] = useState(null);
  const [digestLoading, setDigestLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [trend, setTrend] = useState(null);
  const [activeTab, setActiveTab] = useState('cockpit'); // cockpit | system | execution | connections
  const [systemHealth, setSystemHealth] = useState(null);
  const [executionStatus, setExecutionStatus] = useState(null);
  const [connections, setConnections] = useState(null);
  const [connectingTool, setConnectingTool] = useState(null);

  // Load cockpit overview data
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/org/cockpit');
      setData(r.data);
    } catch (e) {
      if (e?.response?.status === 403 || e?.response?.status === 404) setDenied(true);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Load the weekly task digest
  const loadDigest = useCallback(async () => {
    setDigestLoading(true);
    try {
      const r = await api.get('/org/tasks/weekly-digest');
      setWeeklyDigest(r.data);
    } catch (_) { /* noop */ }
    finally { setDigestLoading(false); }
  }, []);

  useEffect(() => { loadDigest(); }, [loadDigest]);

  // Load system health data when that tab is active
  useEffect(() => {
    if (activeTab !== 'system' || systemHealth) return;
    (async () => {
      try {
        const [modelR, signalsR] = await Promise.all([
          api.get('/system/model'),
          api.get('/system/signals'),
        ]);
        setSystemHealth({ model: modelR.data?.model, signals: signalsR.data });
      } catch (_) {}
    })();
  }, [activeTab, systemHealth]);

  // Load execution data when that tab is active
  useEffect(() => {
    if (activeTab !== 'execution' || executionStatus) return;
    (async () => {
      try {
        const [statusR, tasksR] = await Promise.all([
          api.get('/execution/connections/status'),
          api.get('/execution/tasks/summary'),
        ]);
        setExecutionStatus({ ...statusR.data, ...tasksR.data });
      } catch (_) {}
    })();
  }, [activeTab, executionStatus]);

  // Load connections when that tab is active
  useEffect(() => {
    if (activeTab !== 'connections' || connections) return;
    (async () => {
      try {
        const r = await api.get('/execution/connections');
        setConnections(r.data);
      } catch (_) {}
    })();
  }, [activeTab, connections]);

  useEffect(() => {
    const loadTrend = async () => {
      try {
        const r = await api.get('/org/cockpit/trend?weeks=8');
        setTrend(r.data);
      } catch (_) { /* noop */ }
    };
    loadTrend();
  }, []);

  // Generate this week's tasks from the plan
  const generateWeek = async () => {
    setGenerating(true);
    try {
      const r = await api.post('/org/tasks/generate-week', {});
      await loadDigest();
    } catch (e) {
      /* owner-gated */
    } finally { setGenerating(false); }
  };

  // Save the current ARR progress figure
  const saveProgress = async () => {
    const n = Number(String(arrInput).replace(/[, ]/g, ''));
    if (!Number.isFinite(n) || n < 0) { return; }
    setSavingArr(true);
    try {
      const r = await api.post('/org/progress', { current_arr: n });
      setData((d) => ({ ...d, goal_progress: r.data.goal_progress }));
      setEditingArr(false);
      setArrInput('');
    } catch (_e) { /* owner-gated; ignore */ } finally { setSavingArr(false); }
  };

  if (loading) {
    return (
      <div className="min-h-screen">
      <TopBar title="Founder Cockpit" backTo="/app/team" />
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 space-y-8">
          <div className="space-y-2">
            <div className="h-4 w-24 animate-pulse rounded-md bg-primary/10" />
            <div className="h-8 w-72 animate-pulse rounded-md bg-primary/10" />
            <div className="h-4 w-48 animate-pulse rounded-md bg-primary/10" />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded-2xl bg-primary/10" />
            ))}
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="h-64 animate-pulse rounded-2xl bg-primary/10" />
            <div className="h-64 animate-pulse rounded-2xl bg-primary/10" />
          </div>
          <div className="h-48 animate-pulse rounded-2xl bg-primary/10" />
        </div>
      </div>
    );
  }

  if (denied || !data) {
    return (
      <div className="min-h-screen">
        <TopBar title="Founder Cockpit" backTo="/app" />
        <div data-testid="cockpit-denied" className="max-w-md mx-auto text-center py-24 px-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl border mb-4 text-muted "><Lock size={20} /></div>
          <h2 className="font-display text-xl">This is the founder&apos;s private view</h2>
          <p className="text-sm text-muted  mt-2">Only the workspace owner can open the cockpit.</p>
          <Button variant="secondary" className="rounded-xl mt-6" onClick={() => navigate('/app/brain')}>Open Brain</Button>
        </div>
      </div>
    );
  }

  const ns = data.north_star || {};
  const gp = data.goal_progress;
  const a = data.alignment || {};
  const ex = data.execution || {};
  const t = data.totals || {};
  const scored = a.scored || 0;
  const pct = (n) => (scored ? Math.round((100 * n) / scored) : 0);

  return (
    <div className="min-h-screen">
      <TopBar title="Founder Cockpit" backTo="/team" />
      {/* Tab Navigation */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-2">
        <div className="flex gap-1 border-b">
          {[
            { id: 'cockpit', label: 'Cockpit', icon: Target },
            { id: 'system', label: 'System Health', icon: Activity },
            { id: 'execution', label: 'Execution', icon: Play },
            { id: 'connections', label: 'Connections', icon: Wifi },
          ].map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 -mb-[1px] transition-colors ${
                activeTab === tab.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted  hover:text-foreground'
              }`}>
              <tab.icon size={13} strokeWidth={1.75} />
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      {activeTab === 'cockpit' && (
      <main data-testid="cockpit-page" className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-24 pt-4 space-y-6">

        {/* North Star */}
        <section className="rounded-2xl border bg-surface p-6">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2"><Target size={16} strokeWidth={1.75} /><h3 className="font-medium text-sm">North Star</h3></div>
            <span className="inline-flex items-center gap-1.5 text-[11px] px-2 py-0.5 rounded-full border bg-background text-muted "><Lock size={11} /> Private</span>
          </div>
          {ns.north_star ? (
            <>
              <p data-testid="cockpit-northstar" className="font-display text-xl sm:text-2xl mt-1">{ns.north_star}</p>
              <p className="text-xs text-muted  mt-1">
                {ns.target ? ns.target : ''}{ns.target && ns.deadline ? ' · ' : ''}{ns.deadline ? `by ${ns.deadline}` : ''}
              </p>
            </>
          ) : (
            <p className="text-sm text-muted  mt-1">
              No North Star set yet. <button className="underline" onClick={() => navigate('/app/goal-setup')}>Set up your goal</button> so every decision is steered toward it.
            </p>
          )}
        </section>

        {/* Goal -> Progress tracker */}
        <section data-testid="cockpit-goal-progress" className="rounded-2xl border bg-surface p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2"><Flag size={16} strokeWidth={1.75} /><h3 className="font-medium text-sm">Goal → Progress</h3></div>
            {gp && !editingArr && (
              <button data-testid="cockpit-progress-edit" onClick={() => { setEditingArr(true); setArrInput(String(gp.current_arr ?? '')); }}
                className="text-xs text-muted  hover:text-foreground inline-flex items-center gap-1">
                <Pencil size={12} /> Update
              </button>
            )}
          </div>

          {!gp ? (
            <div className="text-sm text-muted ">
              Set a target number to track progress.{' '}
              <button data-testid="cockpit-progress-setup" className="underline" onClick={() => navigate('/app/goal-setup')}>
                Set up your goal
              </button>{' '}so this fills with a live progress bar.
            </div>
          ) : (
            <>
              {/* big progress number + status */}
              <div className="flex items-end justify-between gap-3 flex-wrap">
                <div>
                  <div data-testid="cockpit-progress-pct" className={`font-display text-3xl sm:text-4xl leading-none ${statusColor(gp.progress_pct)}`}>
                    {gp.progress_pct}%
                  </div>
                  <div data-testid="cockpit-progress-status" className="text-xs text-muted  mt-1.5">
                    {gp.status}{gp.deadline ? ` · target by ${gp.deadline}` : ''}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-muted ">Now → Target</div>
                  <div className="text-sm tabular-nums font-medium">{fmtNum(gp.current_arr)} <span className="text-muted ">/ {fmtNum(gp.target_arr)}</span></div>
                </div>
              </div>

              {/* progress bar */}
              <div className="mt-4 h-3 rounded-full bg-muted overflow-hidden">
                <div className={`h-full transition-all duration-500 ${gp.progress_pct >= 100 ? 'bg-emerald-500' : 'bg-[hsl(var(--ring))]'}`}
                  style={{ width: `${Math.min(100, Math.max(2, gp.progress_pct))}%` }} />
              </div>
              <div className="flex items-center justify-between mt-2 text-[11px] text-muted ">
                <span>{fmtNum(gp.remaining)} to go</span>
                <span>{gp.note}</span>
              </div>

              {/* inline update */}
              {editingArr && (
                <div data-testid="cockpit-progress-editor" className="mt-4 rounded-xl border bg-background p-3 flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-muted ">Where are you now?</span>
                  <Input data-testid="cockpit-progress-input" inputMode="numeric" value={arrInput}
                    onChange={(e) => setArrInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') saveProgress(); }}
                    placeholder={String(gp.target_arr)} className="rounded-lg h-9 w-full sm:w-40" />
                  <Button data-testid="cockpit-progress-save" size="sm" onClick={saveProgress} disabled={savingArr} className="rounded-lg">
                    {savingArr ? <Loader2 className="animate-spin" size={14} /> : 'Save'}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setEditingArr(false)} className="rounded-lg text-muted ">Cancel</Button>
                </div>
              )}

              {/* mini history */}
              {Array.isArray(gp.history) && gp.history.length > 1 && (
                <div className="mt-4 flex items-end gap-1.5 h-12" data-testid="cockpit-progress-history" title="Progress over time">
                  {gp.history.map((h, i) => {
                    const pct = gp.target_arr ? Math.min(100, Math.max(4, Math.round((100 * (h.arr || 0)) / gp.target_arr))) : 4;
                    const isLast = i === gp.history.length - 1;
                    return <div key={i} className={`flex-1 rounded-t ${isLast ? 'bg-[hsl(var(--ring))]' : 'bg-muted-foreground/30'}`} style={{ height: `${pct}%` }} />;
                  })}
                </div>
              )}
            </>
          )}
        </section>

        {/* top stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat icon={Activity} label="Decisions" value={t.decisions ?? 0} sub={`${t.last_7d ?? 0} in last 7 days`} />
          <div className="rounded-2xl border bg-surface p-4">
            <div className="flex items-center gap-1.5 text-xs text-muted  mb-1"><Gauge size={13} strokeWidth={1.75} /> Avg alignment</div>
            <div className={`font-display text-2xl leading-none ${alignColor(a.avg)}`} data-testid="cockpit-avg-alignment">{a.avg == null ? '—' : a.avg}</div>
            <div className="text-[11px] text-muted  mt-1">{scored} scored</div>
          </div>
          <Stat icon={CheckCircle2} label="Follow-through" value={ex.follow_through_pct == null ? '—' : `${ex.follow_through_pct}%`} sub={`${ex.done ?? 0} done · ${ex.dropped ?? 0} dropped`} />
          <Stat icon={IndianRupee} label="Impact tracked" value={data.impact ? fmtNum(data.impact.total_inr) : '—'} sub={data.impact && data.impact.reviewed ? `${data.impact.reviewed} reviewed` : ''} />
          <Stat icon={Users} label="Team" value={t.members ?? 0} sub="members" />
        </div>

        {/* alignment distribution */}
        <section className="rounded-2xl border bg-surface p-6">
          <div className="flex items-center gap-2 mb-4"><TrendingUp size={16} strokeWidth={1.75} /><h3 className="font-medium text-sm">How on-strategy the team is deciding</h3></div>
          {scored === 0 ? (
            <p className="text-xs text-muted ">No scored decisions yet. As your team uses the brain, this fills in.</p>
          ) : (
            <div className="space-y-3">
              {[['On strategy', a.high, 'bg-emerald-500'], ['Partly', a.medium, 'bg-amber-500'], ['Off strategy', a.low, 'bg-red-500']].map(([label, n, color]) => (
                <div key={label} className="flex items-center gap-3">
                  <span className="w-24 text-xs text-muted  shrink-0">{label}</span>
                  <div className="flex-1 h-2.5 rounded-full bg-muted overflow-hidden">
                    <div className={`h-full ${color}`} style={{ width: `${pct(n || 0)}%` }} />
                  </div>
                  <span className="w-10 text-xs text-right tabular-nums">{n || 0}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* momentum trend */}
        <section data-testid="cockpit-momentum" className="rounded-2xl border bg-surface p-6">
          <div className="flex items-center gap-2 mb-4"><TrendingUp size={16} strokeWidth={1.75} /><h3 className="font-medium text-sm">Momentum — week over week</h3></div>
          {!trend || !trend.weeks || trend.weeks.length < 2 ? (
            <p className="text-xs text-muted ">Not enough history yet — momentum appears as the team makes decisions over weeks.</p>
          ) : (
            <>
              <div className="flex items-end gap-1.5 h-28 mb-3" data-testid="cockpit-trend-bar">
                {trend.weeks.map((w, i) => {
                  const h = w.avg_alignment != null ? Math.max(8, w.avg_alignment) : 4;
                  const isLast = i === trend.weeks.length - 1;
                  return (
                    <div key={w.week_start} className="flex-1 flex flex-col items-center gap-1" title={`${w.week_start}: ${w.decisions} decisions, avg alignment ${w.avg_alignment ?? '—'}`}>
                      <span className="text-[10px] text-muted  tabular-nums">{w.avg_alignment ?? '—'}</span>
                      <div className={`w-full rounded-t-sm ${isLast ? 'bg-[hsl(var(--ring))]' : 'bg-muted-foreground/30'}`} style={{ height: `${h}%` }} />
                      <span className="text-[9px] text-muted  mt-0.5">{w.week_start.slice(5)}</span>
                    </div>
                  );
                })}
              </div>
              <div className="flex items-center gap-3 flex-wrap text-xs">
                {trend.deltas && [
                  ['Alignment', trend.deltas.avg_alignment],
                  ['Follow-through', trend.deltas.follow_through_pct],
                  ['Decisions', trend.deltas.decisions],
                ].map(([label, d]) => (
                  <span key={label} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border ${d == null ? 'text-muted ' : d > 0 ? 'text-emerald-600 border-emerald-200' : d < 0 ? 'text-red-600 border-red-200' : 'text-muted '}`} data-testid={`cockpit-delta-${label.toLowerCase()}`}>
                    {label} {d != null ? (d > 0 ? `+${d}` : d) : '—'}{label === 'Follow-through' && d != null ? '%' : ''} vs last week
                  </span>
                ))}
              </div>
            </>
          )}
        </section>

        {/* needs attention — confidently off OR unsure-but-impactful */}
        {data.needs_attention && data.needs_attention.length > 0 && (
          <section data-testid="cockpit-needs-attention" className="rounded-2xl border bg-surface p-6">
            <div className="flex items-center gap-2 mb-4"><AlertTriangle size={16} strokeWidth={1.75} className="text-amber-600" /><h3 className="font-medium text-sm">Needs your eyes</h3></div>
            <div className="space-y-3">
              {data.needs_attention.map((na) => (
                <div key={na.id} data-testid="cockpit-needs-item" className="rounded-xl border bg-background px-4 py-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-muted  truncate">{na.user_name || 'Member'}</span>
                    <div className="flex items-center gap-1.5">
                      <span className={`text-xs font-medium ${alignColor(na.score)}`}>{na.score ?? '—'}/100</span>
                      {na.confidence && (
                        <span data-testid="cockpit-conf-chip" className={`text-[10px] px-1.5 py-0.5 rounded-full border ${na.confidence === 'high' ? 'text-emerald-600 bg-emerald-50 border-emerald-200' : na.confidence === 'medium' ? 'text-amber-600 bg-amber-50 border-amber-200' : 'text-red-600 bg-red-50 border-red-200'}`}>
                          {na.confidence} conf
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-sm mt-1 truncate" title={na.question}>{na.question}</p>
                  {na.basis ? <p className="text-[11px] text-muted  mt-0.5">{na.basis}</p> : null}
                  {na.action ? <p className="text-[11px] text-muted  mt-0.5">Action: {na.action}</p> : null}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* drift radar */}
        <section className="rounded-2xl border bg-surface p-6">
          <div className="flex items-center gap-2 mb-4"><AlertTriangle size={16} strokeWidth={1.75} className="text-amber-600" /><h3 className="font-medium text-sm">Drift radar — decisions pulling sideways</h3></div>
          {(!data.drift || data.drift.length === 0) ? (
            <p className="text-xs text-muted ">Nothing off-strategy. The team is pulling in your direction.</p>
          ) : (
            <div className="space-y-3">
              {data.drift.map((d) => (
                <div key={d.id} data-testid="cockpit-drift-item" className="rounded-xl border bg-background px-4 py-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-muted  truncate">{d.user_name || 'Member'}</span>
                    <div className="flex items-center gap-1.5">
                      <span className={`text-xs font-medium ${alignColor(d.strategic_alignment?.score)}`}>{d.strategic_alignment?.score ?? '—'}/100</span>
                      {d.strategic_alignment?.confidence && (
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${d.strategic_alignment.confidence === 'high' ? 'text-emerald-600 bg-emerald-50 border-emerald-200' : d.strategic_alignment.confidence === 'medium' ? 'text-amber-600 bg-amber-50 border-amber-200' : 'text-red-600 bg-red-50 border-red-200'}`}>
                          {d.strategic_alignment.confidence}
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-sm mt-1 truncate" title={d.question}>{d.question}</p>
                  {d.strategic_alignment?.reason ? <p className="text-xs text-muted  mt-1">{d.strategic_alignment.reason}</p> : null}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* in-flight actions — live timers */}
        <section className="rounded-2xl border bg-surface p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2"><Clock size={16} strokeWidth={1.75} /><h3 className="font-medium text-sm">In flight — what the team is doing now</h3></div>
            {(ex.overdue ?? 0) > 0 && (
              <span data-testid="cockpit-overdue" className="text-xs text-amber-600 inline-flex items-center gap-1"><AlertTriangle size={12} /> {ex.overdue} overdue</span>
            )}
          </div>
          {(!data.active_actions || data.active_actions.length === 0) ? (
            <p className="text-xs text-muted ">No commitments in flight. When the team commits to a move, the countdown shows here.</p>
          ) : (
            <div className="space-y-2">
              {data.active_actions.map((a) => (
                <div key={a.id} data-testid="cockpit-active-action" className="flex items-center justify-between gap-3 rounded-xl border bg-background px-4 py-2.5">
                  <div className="min-w-0">
                    <div className="text-xs text-muted  truncate">{a.user_name}</div>
                    <p className="text-sm truncate" title={a.action}>{a.action}</p>
                  </div>
                  <span className={`shrink-0 text-xs font-mono-plex inline-flex items-center gap-1 ${a.overdue ? 'text-amber-600' : 'text-[hsl(var(--ring))]'}`}>
                    <Clock size={12} /> {fmtLeft(a.due_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* achieved — results feed */}
        <section className="rounded-2xl border bg-surface p-6">
          <div className="flex items-center gap-2 mb-4"><Award size={16} strokeWidth={1.75} className="text-emerald-600" /><h3 className="font-medium text-sm">Achieved — the dream coming true</h3></div>
          {(!data.results || data.results.length === 0) ? (
            <p className="text-xs text-muted ">No results logged yet. As the team finishes commitments and logs what happened, the wins land here.</p>
          ) : (
            <div className="space-y-3">
              {data.results.map((r) => (
                <div key={r.id} data-testid="cockpit-result-item" className="rounded-xl border bg-background px-4 py-3">
                  <div className="flex items-center gap-2 text-xs text-muted ">
                    <CheckCircle2 size={13} className="text-emerald-600" /> {r.user_name}
                  </div>
                  {r.action ? <p className="text-sm mt-1 truncate" title={r.action}>{r.action}</p> : null}
                  <p className="text-sm text-foreground mt-1">{r.result}</p>
                </div>
              ))}
            </div>
          )}
        </section>

          {/* per-member */}
          <section className="rounded-2xl border bg-surface p-6">
            <div className="flex items-center gap-2 mb-4"><Users size={16} strokeWidth={1.75} /><h3 className="font-medium text-sm">By teammate</h3></div>
            <div className="divide-y">
              <div className="flex items-center text-[11px] uppercase tracking-wide text-muted  pb-2">
                <span className="flex-1">Member</span>
                <span className="hidden sm:inline sm:w-20 text-right">Decisions</span>
                <span className="hidden sm:inline sm:w-20 text-right">Alignment</span>
                <span className="hidden sm:inline sm:w-16 text-right">Done</span>
              </div>
              {(data.per_member || []).map((m) => (
                <div key={m.user_id} data-testid="cockpit-member-row" className="flex items-center py-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{m.name || m.email}{m.role === 'owner' ? ' (you)' : ''}</div>
                    <div className="text-xs text-muted  truncate">{m.email}</div>
                  </div>
                  <span className="hidden sm:inline sm:w-20 text-right text-sm tabular-nums">{m.decisions}</span>
                  <span className={`hidden sm:inline sm:w-20 text-right text-sm tabular-nums ${alignColor(m.avg_alignment)}`}>{m.avg_alignment == null ? '—' : m.avg_alignment}</span>
                  <span className="hidden sm:inline sm:w-16 text-right text-sm tabular-nums">{m.done}</span>
                </div>
              ))}
            </div>
          </section>

          {/* weekly tasks — OKR execution layer */}
          <section className="rounded-2xl border bg-surface p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2"><ListChecks size={16} strokeWidth={1.75} /><h3 className="font-medium text-sm">Weekly Tasks</h3></div>
              <Button size="sm" variant="secondary" onClick={generateWeek} disabled={generating}
                className="rounded-lg h-8 px-3 text-xs border border-hairline/70 active:scale-[0.98]">
                {generating ? <Loader2 className="animate-spin" size={13} /> : <RefreshCw size={13} className="mr-1" />}
                {generating ? 'Generating…' : 'Generate this week'}
              </Button>
            </div>

            {digestLoading ? (
              <div className="flex items-center gap-2 text-xs text-muted  py-4"><Loader2 className="animate-spin" size={13} /> Loading tasks…</div>
            ) : !weeklyDigest || weeklyDigest.total_tasks === 0 ? (
              <p className="text-xs text-muted ">No tasks generated yet. Click "Generate this week" to create weekly tasks from your active plan.</p>
            ) : (
              <div className="space-y-4">
                {/* summary row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                  <div className="rounded-xl bg-[hsl(var(--accent))]/50 px-3 py-2">
                    <div className="text-lg font-display">{weeklyDigest.total_tasks}</div>
                    <div className="text-[10px] text-muted ">Total</div>
                  </div>
                  <div className="rounded-xl bg-emerald-50 px-3 py-2">
                    <div className="text-lg font-display text-emerald-600">{weeklyDigest.done}</div>
                    <div className="text-[10px] text-muted ">Done</div>
                  </div>
                  <div className="rounded-xl bg-amber-50 px-3 py-2">
                    <div className="text-lg font-display text-amber-600">{weeklyDigest.overdue}</div>
                    <div className="text-[10px] text-muted ">Overdue</div>
                  </div>
                  <div className="rounded-xl bg-blue-50 px-3 py-2">
                    <div className="text-lg font-display text-blue-600">{weeklyDigest.in_progress || 0}</div>
                    <div className="text-[10px] text-muted ">In progress</div>
                  </div>
                </div>

                {/* per-department */}
                <div>
                  <p className="text-xs text-muted  mb-2">By department</p>
                  <div className="space-y-2">
                    {(weeklyDigest.by_department || []).map((d) => (
                      <div key={d.function} className="flex items-center gap-3">
                        <span className="w-24 text-xs capitalize shrink-0">{d.function}</span>
                        <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                          <div className="h-full bg-[hsl(var(--ring))] transition-all" style={{ width: `${d.total ? Math.round(100 * d.done / d.total) : 0}%` }} />
                        </div>
                        <span className="w-24 text-[11px] text-right text-muted  tabular-nums">{d.done}/{d.total}{d.overdue > 0 ? ` · ${d.overdue} overdue` : ''}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* per-member workload */}
                <div>
                  <p className="text-xs text-muted  mb-2">Member workload</p>
                  <div className="divide-y">
                    <div className="flex items-center text-[10px] uppercase tracking-wide text-muted  pb-1.5">
                      <span className="flex-1">Member</span>
                      <span className="hidden sm:inline sm:w-12 text-right">Tasks</span>
                      <span className="hidden sm:inline sm:w-12 text-right">Done</span>
                      <span className="hidden sm:inline sm:w-12 text-right">Overdue</span>
                    </div>
                    {(weeklyDigest.by_member || []).map((m) => (
                      <div key={m.user_id} className="flex items-center py-2 text-sm">
                        <span className="flex-1 truncate text-xs">{m.name}</span>
                        <span className="hidden sm:inline sm:w-12 text-right tabular-nums text-xs">{m.total}</span>
                        <span className="hidden sm:inline sm:w-12 text-right tabular-nums text-xs text-emerald-600">{m.done}</span>
                        <span className={`hidden sm:inline sm:w-12 text-right tabular-nums text-xs ${m.overdue > 0 ? 'text-amber-600' : 'text-muted '}`}>{m.overdue || 0}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* flagged tasks */}
                {weeklyDigest.flagged && weeklyDigest.flagged.length > 0 && (
                  <div>
                    <p className="text-xs text-amber-600 mb-2 flex items-center gap-1"><AlertTriangle size={12} /> Flagged — needs your attention</p>
                    <div className="space-y-2">
                      {weeklyDigest.flagged.map((t) => (
                        <div key={t.id} className="rounded-xl border bg-background px-3 py-2">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-medium truncate">{t.title}</span>
                            <span className="text-[10px] text-muted  shrink-0">{t.assigned_to_name}</span>
                          </div>
                          <p className="text-[11px] text-muted  mt-0.5">{t.ai_review?.notes || t.status}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>
        </main>
      )}
      {/* System Health Tab */}
      {activeTab === 'system' && (
        <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-24 pt-4 space-y-6">
          {systemHealth ? (
            <>
              <SystemHealthTab health={systemHealth} />
            </>
          ) : (
            <div className="flex items-center justify-center py-20"><Loader2 size={20} className="animate-spin text-muted " /></div>
          )}
        </main>
      )}
      {/* Execution Tab */}
      {activeTab === 'execution' && (
        <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-24 pt-4 space-y-6">
          {executionStatus ? (
            <ExecutionTab status={executionStatus} setConnectingTool={setConnectingTool} connectingTool={connectingTool} />
          ) : (
            <div className="flex items-center justify-center py-20"><Loader2 size={20} className="animate-spin text-muted " /></div>
          )}
        </main>
      )}
      {/* Connections Tab */}
      {activeTab === 'connections' && (
        <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-24 pt-4 space-y-6">
          {connections ? (
            <ConnectionsTab connections={connections} setConnectingTool={setConnectingTool} connectingTool={connectingTool} setConnections={setConnections} />
          ) : (
            <div className="flex items-center justify-center py-20"><Loader2 size={20} className="animate-spin text-muted " /></div>
          )}
        </main>
      )}
    </div>
  );
}

// ── System Health Tab Content ──
function SystemHealthTab({ health }) {
  const model = health?.model;
  const signals = health?.signals;
  const functions = model?.functions || {};
  const atRisk = Object.entries(functions).filter(([, s]) => s.status === 'at_risk');
  const warnings = Object.entries(functions).filter(([, s]) => s.status === 'warning');

  return (
    <>
      <section className="rounded-2xl border bg-surface p-6">
        <div className="flex items-center gap-2 mb-4"><Activity size={16} strokeWidth={1.75} /><h3 className="font-medium text-sm">System Health</h3></div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
          <Stat icon={AlertTriangle} label="At Risk" value={signals?.at_risk_count || atRisk.length} />
          <Stat icon={Activity} label="Warnings" value={signals?.warning_count || warnings.length} />
          <Stat icon={CheckCircle2} label="Healthy" value={signals?.healthy_count || Object.keys(functions).length - atRisk.length - warnings.length} />
        </div>
        {signals?.brief && (
          <pre className="text-xs text-muted  whitespace-pre-wrap font-mono leading-relaxed bg-muted/50 rounded-lg p-3 max-h-64 overflow-auto">
            {signals.brief}
          </pre>
        )}
      </section>

      <section className="rounded-2xl border bg-surface p-6">
        <div className="flex items-center gap-2 mb-3"><Target size={16} strokeWidth={1.75} /><h3 className="font-medium text-sm">16 Functions</h3></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {Object.entries(functions).map(([func, state]) => {
            const color = state.status === 'at_risk' ? 'bg-red-50 border-red-200' : state.status === 'warning' ? 'bg-amber-50 border-amber-200' : 'bg-emerald-50 border-emerald-200';
            const textColor = state.status === 'at_risk' ? 'text-red-700' : state.status === 'warning' ? 'text-amber-700' : 'text-emerald-700';
            return (
              <div key={func} className={`rounded-lg border px-3 py-2 ${color}`}>
                <div className="text-[11px] capitalize text-muted ">{func.replace(/_/g, ' ')}</div>
                <div className={`font-mono text-sm font-medium ${textColor}`}>{state.health}/100</div>
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}

// ── Execution Tab Content ──
function ExecutionTab({ status, setConnectingTool, connectingTool }) {
  // Connect a tool and complete the OAuth
  const connect = async (toolkit) => {
    setConnectingTool(toolkit);
    try {
      const r = await api.post('/execution/connections/connect', { toolkit });
      if (r.data.auth_url) window.open(r.data.auth_url, '_blank');
      setTimeout(async () => {
        try { await api.post('/execution/connections/complete', { toolkit }); } catch (_) {}
        setConnectingTool(null);
      }, 5000);
    } catch (_) { setConnectingTool(null); }
  };

  const atRiskSuggestions = status?.at_risk_suggestions || {};
  const totalTasks = (status?.total || 0);

  return (
    <>
      <section className="rounded-2xl border bg-surface p-6">
        <div className="flex items-center gap-2 mb-4"><Play size={16} strokeWidth={1.75} /><h3 className="font-medium text-sm">Execution Status</h3></div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 sm:gap-4 mb-4">
          <Stat icon={ListChecks} label="Proposed" value={status?.proposed || 0} />
          <Stat icon={CheckCircle2} label="Approved" value={status?.approved || 0} />
          <Stat icon={Play} label="Executed" value={status?.executed || 0} />
          <Stat icon={Shield} label="Verified" value={status?.verified || 0} />
          <Stat icon={StopCircle} label="Failed" value={status?.failed || 0} />
        </div>
        <div className="grid grid-cols-3 gap-4">
          <Stat icon={Wifi} label="Connected Tools" value={status?.active_connections || 0} />
          <Stat icon={IndianRupee} label="Total" value={totalTasks} />
          {status?.connected_tools?.length > 0 && (
            <div className="rounded-2xl border bg-surface p-4">
              <div className="text-xs text-muted  mb-1">Tools</div>
              <div className="flex flex-wrap gap-1">
                {status.connected_tools.slice(0, 6).map(t => (
                  <span key={t} className="text-[10px] bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded">{t}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      {Object.keys(atRiskSuggestions).length > 0 && (
        <section className="rounded-2xl border border-amber-200 bg-amber-50/50 p-6">
          <div className="flex items-center gap-2 mb-3"><AlertTriangle size={16} className="text-amber-600" /><h3 className="font-medium text-sm text-amber-900">Tool Suggestions for At-Risk Functions</h3></div>
          <div className="space-y-3">
            {Object.entries(atRiskSuggestions).map(([func, info]) => (
              <div key={func} className="rounded-xl bg-white border p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">{func}</span>
                  <span className="font-mono text-xs text-red-600">{info.health}/100</span>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {info.suggested_tools?.map(t => (
                    <button key={t.toolkit} onClick={() => connect(t.toolkit)} disabled={!!connectingTool}
                      className="rounded-lg bg-blue-50 border border-blue-200 px-2 py-1 text-[11px] font-medium text-blue-700 hover:bg-blue-100 flex items-center gap-1">
                      {connectingTool === t.toolkit ? <Sparkles size={11} className="animate-spin" /> : <Wifi size={11} />}
                      {t.toolkit}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

// ── Connections Tab Content ──
function ConnectionsTab({ connections, setConnectingTool, connectingTool, setConnections }) {
  const connected = connections?.connected_list || [];
  const available = connections?.top_available || [];

  // Connect a tool via OAuth flow
  const connect = async (toolkit) => {
    setConnectingTool(toolkit);
    try {
      const r = await api.post('/execution/connections/connect', { toolkit });
      if (r.data.auth_url) window.open(r.data.auth_url, '_blank');
      setTimeout(async () => {
        try { await api.post('/execution/connections/complete', { toolkit }); } catch (_) {}
        try { const r2 = await api.get('/execution/connections'); setConnections(r2.data); } catch (_) {}
        setConnectingTool(null);
      }, 5000);
    } catch (_) { setConnectingTool(null); }
  };

  // Disconnect a connected tool
  const disconnect = async (toolkit) => {
    try {
      await api.post('/execution/connections/disconnect', { toolkit });
      const r = await api.get('/execution/connections');
      setConnections(r.data);
    } catch (_) {}
  };

  return (
    <>
      <section className="rounded-2xl border bg-surface p-6">
        <div className="flex items-center gap-2 mb-1"><Wifi size={16} strokeWidth={1.75} /><h3 className="font-medium text-sm">Connected Tools</h3></div>
        <p className="text-xs text-muted  mb-4">{connections?.connected || 0} connected · {connections?.available || 0} available · {connections?.total || 0} total</p>
        {connected.length === 0 ? (
          <p className="text-sm text-muted ">No tools connected yet. Connect your first tool below.</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {connected.map(t => (
              <div key={t.toolkit} className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 flex items-center justify-between">
                <span className="text-sm font-medium capitalize">{t.toolkit}</span>
                <button onClick={() => disconnect(t.toolkit)} className="text-[10px] text-red-500 hover:text-red-700">Disconnect</button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-2xl border bg-surface p-6">
        <div className="flex items-center gap-2 mb-3"><WifiOff size={16} strokeWidth={1.75} /><h3 className="font-medium text-sm">Available Tools</h3></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {available.slice(0, 24).map(t => (
            <button key={t.toolkit} onClick={() => connect(t.toolkit)} disabled={!!connectingTool}
              className="rounded-lg border bg-white px-3 py-2 text-left hover:bg-muted/50">
              <div className="text-sm font-medium capitalize">{t.toolkit}</div>
              <div className="text-[10px] text-muted  mt-0.5">{t.tool_count} tools</div>
              {connectingTool === t.toolkit && <Sparkles size={12} className="animate-spin text-primary mt-1" />}
            </button>
          ))}
        </div>
      </section>
    </>
  );
}
