import { useState, useEffect, useCallback } from 'react';
import { ArrowLeft, Users, Activity, Globe, Coins, Star, Rocket, ShieldCheck, Target, Book } from 'lucide-react';
import { TopBar } from '../components/TopBar';
import { api } from '../lib/api';
import { useAuth } from '../App';
import { toast } from 'sonner';
import DataTab from '../components/DataTab';
import { fmt, fmtDate, Stat, Th, Td, Pager } from '../lib/admin-ui';

// Format seconds into a compact duration string
const fmtDur = (s) => {
  if (!s || s < 60) return `${s || 0}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
};

// Render an uppercase section heading with optional icon
const SectionTitle = ({ icon: Icon, children }) => (
  <h2 className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-muted mt-8 mb-3">
    {Icon && <Icon size={13} strokeWidth={1.75} />} {children}
  </h2>
);

// ---------------------------------------------------------------- Overview
function Overview() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get('/admin/overview').then((r) => setD(r.data)).catch(() => {}); }, []);
  if (!d) return <p className="text-sm text-muted mt-8">Loading…</p>;
  return (
    <div data-testid="admin-overview">
      <SectionTitle icon={Users}>Users</SectionTitle>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Stat testId="stat-users-total" label="Total users" value={fmt(d.users.total)} />
        <Stat label="New · 7 days" value={fmt(d.users.new_7d)} />
        <Stat label="Active · 24h" value={fmt(d.users.active_24h)} />
      </div>
      <SectionTitle icon={Activity}>Engine</SectionTitle>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat testId="stat-questions" label="Questions asked" value={fmt(d.engine.questions_total)} sub={`${fmt(d.engine.questions_7d)} this week`} />
        <Stat label="Normal turns" value={fmt(d.engine.turns_normal)} />
        <Stat label="Ultra turns" value={fmt(d.engine.turns_ultra)} />
        <Stat label="Tokens in / out" value={`${fmt(d.tokens.input_total)} / ${fmt(d.tokens.output_total)}`} />
      </div>
      <SectionTitle icon={Coins}>Credits & revenue</SectionTitle>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat testId="stat-credits-issued" label="Credits issued" value={fmt(d.credits.issued_total)} sub={`${fmt(d.credits.issued_free)} free · ${fmt(d.credits.issued_paid)} paid`} />
        <Stat label="Credits spent" value={fmt(d.credits.spent)} />
        <Stat label="Outstanding" value={fmt(d.credits.outstanding)} />
        <Stat testId="stat-revenue" label="Revenue" value={`₹${fmt(d.revenue.total_inr)}`} sub={`${fmt(d.revenue.purchases)} purchases`} />
      </div>
      <SectionTitle icon={Globe}>Traffic</SectionTitle>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat testId="stat-sessions" label="Sessions" value={fmt(d.traffic.sessions_total)} sub={`${fmt(d.traffic.sessions_7d)} this week`} />
        <Stat label="Unique IPs" value={fmt(d.traffic.unique_ips)} />
        <Stat label="Avg session" value={fmtDur(d.traffic.avg_session_s)} />
        <Stat label="Active now" value={fmt(d.traffic.active_now)} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Users + drilldown
function UserDetail({ userId, onBack }) {
  const [d, setD] = useState(null);
  useEffect(() => { api.get(`/admin/users/${userId}/activity`).then((r) => setD(r.data)).catch(() => {}); }, [userId]);
  if (!d) return <p className="text-sm text-muted mt-8">Loading…</p>;
  const u = d.user;
  return (
    <div data-testid="admin-user-detail" className="mt-6">
      <button data-testid="user-detail-back" onClick={onBack} className="flex items-center gap-1.5 text-xs text-muted hover:text-foreground">
        <ArrowLeft size={13} /> All users
      </button>
      <div className="mt-4 bg-white border border-hairline/70 rounded-xl p-5">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="font-display text-xl">{u.name || u.email}</h2>
          <span className="text-xs text-muted">{u.email}</span>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-1.5 mt-3 text-xs text-muted">
          <span>Country: <span className="text-foreground">{u.country || 'Unknown'}{u.city && u.city !== u.country ? ` · ${u.city}` : ''}</span></span>
          <span>Questions: <span className="font-mono-plex text-foreground">{fmt(u.questions_asked)}</span></span>
          <span>Credits: <span className="font-mono-plex text-foreground">{fmt(u.credits)}</span></span>
          <span>Issued free/paid: <span className="font-mono-plex text-foreground">{fmt(u.credits_issued_free)} / {fmt(u.credits_issued_paid)}</span></span>
          <span>Tokens in/out: <span className="font-mono-plex text-foreground">{fmt(u.tokens_in)} / {fmt(u.tokens_out)}</span></span>
          <span>Joined: <span className="text-foreground">{fmtDate(u.created_at)}</span></span>
        </div>
      </div>
      <SectionTitle>Questions & engine replies</SectionTitle>
      {d.threads.length === 0 && <p className="text-sm text-muted">No goals opened yet.</p>}
      {d.threads.map((t) => (
        <div key={t.thread_id} className="bg-white border border-hairline/70 rounded-xl p-4 mb-3">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-sm font-medium">{t.goal}</p>
            <span className="text-[10px] uppercase tracking-wider text-muted shrink-0">{t.status}</span>
          </div>
          <div className="mt-2 space-y-3">
            {t.qa.length === 0 && <p className="text-xs text-muted">No turns yet.</p>}
            {t.qa.map((m, i) => (
              <div key={i} className="border-l-2 border-hairline pl-3">
                <p className="text-[13px]"><span className="text-muted">Q · </span>{m.question}</p>
                <p className="text-[13px] mt-1 text-muted"><span>A · </span>{m.reply}</p>
                <p className="font-mono-plex text-[10px] text-muted/70 mt-1">{m.intent || ''} {m.at ? `· ${fmtDate(m.at)}` : ''}</p>
              </div>
            ))}
          </div>
        </div>
      ))}
      <SectionTitle>Credit ledger</SectionTitle>
      <div className="bg-white border border-hairline/70 rounded-xl overflow-x-auto">
        <table className="w-full">
          <thead className="border-b border-hairline/70"><tr><Th>Type</Th><Th right>Credits</Th><Th>Detail</Th><Th>When</Th></tr></thead>
          <tbody>
            {d.ledger.map((e) => (
              <tr key={e.id} className="border-b border-hairline/40 last:border-0">
                <Td>{e.type.replace('_', ' ')}</Td>
                <Td right mono className={e.credits > 0 ? 'text-[hsl(var(--success))]' : ''}>{e.credits > 0 ? `+${e.credits}` : e.credits}</Td>
                <Td mono>{e.amount_inr ? `₹${e.amount_inr}` : e.mode || e.reason || '—'}</Td>
                <Td mono>{fmtDate(e.at)}</Td>
              </tr>
            ))}
            {d.ledger.length === 0 && <tr><Td className="text-muted" colSpan={4}>No movements yet.</Td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// List users with search, pagination, and activity drill-down
function UsersTab() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [selected, setSelected] = useState(null);
  // Fetch the paginated user list
  const load = useCallback(() => {
    api.get('/admin/users', { params: { page, limit: 25, q } }).then((r) => setData(r.data)).catch(() => {});
  }, [page, q]);
  useEffect(() => { load(); }, [load]);
  if (selected) return <UserDetail userId={selected} onBack={() => setSelected(null)} />;
  return (
    <div data-testid="admin-users" className="mt-6">
      <input data-testid="admin-users-search" value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }}
        placeholder="Search email, name or country…"
        className="w-full sm:w-80 bg-white border border-hairline/70 rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))]" />
      <div className="mt-4 bg-white border border-hairline/70 rounded-xl overflow-x-auto">
        <table className="w-full" data-testid="admin-users-table">
          <thead className="border-b border-hairline/70">
            <tr><Th>User</Th><Th>Country</Th><Th right>Questions</Th><Th right>Credits</Th><Th right>Tokens in/out</Th><Th>Joined</Th></tr>
          </thead>
          <tbody>
            {(data?.items || []).map((u) => (
              <tr key={u.id} data-testid="admin-user-row" onClick={() => setSelected(u.id)}
                className="border-b border-hairline/40 last:border-0 cursor-pointer hover:bg-secondary/60 transition-colors">
                <Td>
                  <span className="font-medium">{u.name || '—'}</span>
                  <span className="block text-[11px] text-muted">{u.email}{u.is_admin ? ' · founder' : ''}</span>
                </Td>
                <Td>{u.country || 'Unknown'}</Td>
                <Td right mono>{fmt(u.questions_asked)}</Td>
                <Td right mono>{fmt(u.credits)}</Td>
                <Td right mono>{fmt(u.tokens_in)} / {fmt(u.tokens_out)}</Td>
                <Td mono>{fmtDate(u.created_at)}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={page} pages={data?.pages || 1} onPage={setPage} />
    </div>
  );
}

// ---------------------------------------------------------------- Traffic
function TrafficTab() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  useEffect(() => { api.get('/admin/traffic', { params: { page, limit: 25 } }).then((r) => setData(r.data)).catch(() => {}); }, [page]);
  if (!data) return <p className="text-sm text-muted mt-8">Loading…</p>;
  const s = data.summary;
  return (
    <div data-testid="admin-traffic" className="mt-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Sessions" value={fmt(s.sessions_total)} />
        <Stat label="Unique IPs" value={fmt(s.unique_ips)} />
        <Stat label="Avg time spent" value={fmtDur(s.avg_session_s)} />
        <Stat label="Active now" value={fmt(s.active_now)} />
      </div>
      <div className="mt-4 bg-white border border-hairline/70 rounded-xl overflow-x-auto">
        <table className="w-full" data-testid="admin-traffic-table">
          <thead className="border-b border-hairline/70">
            <tr><Th>IP</Th><Th>City</Th><Th>Country</Th><Th>User</Th><Th right>Time spent</Th><Th>Started</Th></tr>
          </thead>
          <tbody>
            {data.items.map((t) => (
              <tr key={t.session_id} className="border-b border-hairline/40 last:border-0">
                <Td mono>{t.ip || '—'}</Td>
                <Td>{t.city}</Td>
                <Td>{t.country}</Td>
                <Td className="text-[12px]">{t.user_email || <span className="text-muted">visitor</span>}</Td>
                <Td right mono>{fmtDur(t.duration_s)}</Td>
                <Td mono>{fmtDate(t.started_at)}</Td>
              </tr>
            ))}
            {data.items.length === 0 && <tr><Td className="text-muted" colSpan={6}>No sessions yet.</Td></tr>}
          </tbody>
        </table>
      </div>
      <Pager page={page} pages={data.pages} onPage={setPage} />
    </div>
  );
}

// ---------------------------------------------------------------- Usage
function UsageTab() {
  const [data, setData] = useState(null);
  const [models, setModels] = useState(null);
  const [page, setPage] = useState(1);
  useEffect(() => { api.get('/admin/usage', { params: { page, limit: 25 } }).then((r) => setData(r.data)).catch(() => {}); }, [page]);
  useEffect(() => { api.get('/admin/usage/models').then((r) => setModels(r.data)).catch(() => {}); }, []);
  if (!data) return <p className="text-sm text-muted mt-8">Loading…</p>;
  const s = data.summary;
  const inr = (n) => `₹${fmt(Math.round(n || 0))}`;
  return (
    <div data-testid="admin-usage" className="mt-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat testId="usage-credits-issued" label="Credits issued" value={fmt(s.credits.issued_total)} sub={`${fmt(s.credits.issued_free)} free · ${fmt(s.credits.issued_paid)} paid`} />
        <Stat label="Credits spent / outstanding" value={`${fmt(s.credits.spent)} / ${fmt(s.credits.outstanding)}`} />
        <Stat testId="usage-tokens" label="Input / output tokens" value={`${fmt(s.tokens.input_total)} / ${fmt(s.tokens.output_total)}`} />
        <Stat label="Revenue" value={`₹${fmt(s.revenue.total_inr)}`} sub={`${fmt(s.turns.normal)} normal · ${fmt(s.turns.ultra)} ultra turns`} />
      </div>

      {/* Cost & margin */}
      {models && (
        <div className="mt-6" data-testid="admin-usage-cost">
          <div className="flex items-baseline justify-between mb-2">
            <h3 className="text-sm font-semibold text-foreground">Cost &amp; margin · per model</h3>
            <span className="text-[11px] text-muted">USD→INR @ {models.usd_to_inr} · estimates, not invoiced totals</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label="Revenue earned" value={inr(models.totals.revenue_inr)} />
            <Stat label="Est. API cost" value={inr(models.totals.estimated_api_inr)} sub={`${fmt(models.totals.tokens_in)} in · ${fmt(models.totals.tokens_out)} out`} />
            <Stat label="Margin" value={inr(models.totals.margin_inr)} sub={models.totals.margin_pct == null ? '—' : `${models.totals.margin_pct}% of revenue`} />
            <Stat label="Total LLM calls" value={fmt(models.totals.turns)} sub={`${fmt(models.totals.credits_spent)} credits charged`} />
          </div>
          <div className="mt-3 bg-white border border-hairline/70 rounded-xl overflow-x-auto">
            <table className="w-full" data-testid="admin-usage-models-table">
              <thead className="border-b border-hairline/70">
                <tr>
                  <Th>Model</Th>
                  <Th right>Turns</Th>
                  <Th right>Tokens in</Th>
                  <Th right>Tokens out</Th>
                  <Th right>Credits charged</Th>
                  <Th right>Est. ₹ API cost</Th>
                </tr>
              </thead>
              <tbody>
                {models.items.length === 0 && (
                  <tr><td colSpan={6} className="px-3 py-3 text-[12px] text-muted">No LLM calls yet — once users start chatting, model usage will appear here.</td></tr>
                )}
                {models.items.map((m) => (
                  <tr key={m.model} className="border-b border-hairline/40 last:border-0">
                    <Td>
                      <div className="text-[12px] font-medium">{m.label}</div>
                      <div className="text-[10px] text-muted font-mono">{m.model}</div>
                    </Td>
                    <Td right mono>{fmt(m.turns)}</Td>
                    <Td right mono>{fmt(m.tokens_in)}</Td>
                    <Td right mono>{fmt(m.tokens_out)}</Td>
                    <Td right mono>{fmt(m.credits_spent)}</Td>
                    <Td right mono>{inr(m.estimated_inr)}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-2 text-[11px] text-muted">
            Pricing assumed (USD per 1M tokens):{' '}
            {models.pricing.map((p, i) => (
              <span key={p.model}>
                {i > 0 && ' · '}
                <span className="font-mono">{p.label}</span> ${p.input_usd_per_m}/${p.output_usd_per_m}
              </span>
            ))}
            . Override via env vars <span className="font-mono">PRICE_OPUS_IN/OUT</span>, <span className="font-mono">PRICE_FABLE_IN/OUT</span>, <span className="font-mono">PRICE_HAIKU_IN/OUT</span>, <span className="font-mono">USD_TO_INR</span>.
          </div>
        </div>
      )}

      <div className="mt-6 bg-white border border-hairline/70 rounded-xl overflow-x-auto">
        <table className="w-full" data-testid="admin-usage-table">
          <thead className="border-b border-hairline/70">
            <tr><Th>User</Th><Th right>Questions</Th><Th right>Free issued</Th><Th right>Paid issued</Th><Th right>Balance</Th><Th right>Tokens in/out</Th></tr>
          </thead>
          <tbody>
            {data.items.map((u) => (
              <tr key={u.id} className="border-b border-hairline/40 last:border-0">
                <Td><span className="text-[12px]">{u.email}</span></Td>
                <Td right mono>{fmt(u.questions_asked)}</Td>
                <Td right mono>{fmt(u.credits_issued_free)}</Td>
                <Td right mono>{fmt(u.credits_issued_paid)}</Td>
                <Td right mono>{fmt(u.credits)}</Td>
                <Td right mono>{fmt(u.tokens_in)} / {fmt(u.tokens_out)}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={page} pages={data.pages} onPage={setPage} />
    </div>
  );
}

// ---------------------------------------------------------------- Feedback
// Feedback status filter options for the tab
const STATUS_FILTERS = [
  { id: '', label: 'All' },
  { id: 'new', label: 'New' },
  { id: 'reviewed', label: 'Reviewed' },
  { id: 'resolved', label: 'Resolved' },
];
// Badge color styles per feedback category
const CATEGORY_STYLE = {
  bug: 'bg-red-50 text-red-700 border-red-200',
  idea: 'bg-blue-50 text-blue-700 border-blue-200',
  praise: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  other: 'bg-secondary text-muted border-hairline/70',
};

// Render a five-star rating row
const Stars = ({ n }) => (
  <span className="inline-flex items-center gap-0.5" title={`${n}/5`}>
    {[1, 2, 3, 4, 5].map((i) => (
      <Star key={i} size={12} strokeWidth={1.5}
        className={i <= n ? 'fill-amber-400 text-amber-400' : 'text-border'} />
    ))}
  </span>
);

// Show user feedback with status management
function FeedbackTab() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const load = useCallback(() => {
    const params = { page, limit: 25 };
    if (status) params.status = status;
    api.get('/admin/feedback', { params }).then((r) => setData(r.data)).catch(() => {});
  }, [page, status]);
  useEffect(() => { load(); }, [load]);

  // Update a feedback row's review status
  const setRowStatus = (id, newStatus) => {
    api.patch(`/admin/feedback/${id}`, { status: newStatus }).then(() => load()).catch(() => {});
  };

  if (!data) return <p className="text-sm text-muted mt-8">Loading…</p>;
  const s = data.summary;
  return (
    <div data-testid="admin-feedback" className="mt-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat testId="feedback-stat-total" label="Total feedback" value={fmt(s.total)} />
        <Stat testId="feedback-stat-new" label="Awaiting review" value={fmt(s.by_status.new)}
          sub={`${fmt(s.by_status.reviewed)} reviewed · ${fmt(s.by_status.resolved)} resolved`} />
        <Stat label="Avg rating" value={s.avg_rating ? `${s.avg_rating} / 5` : '—'} />
        <Stat label="By type" value={`${fmt(s.by_category.bug)} bugs · ${fmt(s.by_category.idea)} ideas`}
          sub={`${fmt(s.by_category.praise)} praise · ${fmt(s.by_category.other)} other`} />
      </div>
      <div className="flex items-center gap-1.5 mt-4">
        {STATUS_FILTERS.map((f) => (
          <button key={f.id} data-testid={`feedback-filter-${f.id || 'all'}`}
            onClick={() => { setPage(1); setStatus(f.id); }}
            className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
              status === f.id
                ? 'bg-[hsl(var(--accent))] border-transparent text-foreground'
                : 'bg-white border-hairline/70 text-muted hover:text-foreground'}`}>
            {f.label}
          </button>
        ))}
      </div>
      <div className="mt-4 bg-white border border-hairline/70 rounded-xl overflow-x-auto">
        <table className="w-full" data-testid="admin-feedback-table">
          <thead className="border-b border-hairline/70">
            <tr><Th>User</Th><Th>Rating</Th><Th>Type</Th><Th>Message</Th><Th>When</Th><Th>Status</Th></tr>
          </thead>
          <tbody>
            {data.items.map((f) => (
              <tr key={f.id} data-testid="feedback-row"
                className={`border-b border-hairline/40 last:border-0 align-top ${f.status === 'new' ? 'bg-amber-50/40' : ''}`}>
                <Td>
                  <span className="font-medium text-[12px]">{f.user_name || '—'}</span>
                  <span className="block text-[11px] text-muted">{f.user_email}</span>
                </Td>
                <Td><Stars n={f.rating} /></Td>
                <Td>
                  <span className={`inline-block px-2 py-0.5 rounded-md text-[10px] uppercase tracking-wider border ${CATEGORY_STYLE[f.category] || CATEGORY_STYLE.other}`}>
                    {f.category}
                  </span>
                </Td>
                <Td className="max-w-md"><span className="whitespace-pre-wrap break-words">{f.message}</span></Td>
                <Td mono>{fmtDate(f.created_at)}</Td>
                <Td>
                  <select data-testid="feedback-status-select" value={f.status}
                    onChange={(e) => setRowStatus(f.id, e.target.value)}
                    className="bg-white border border-hairline/70 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-[hsl(var(--ring))] cursor-pointer">
                    <option value="new">New</option>
                    <option value="reviewed">Reviewed</option>
                    <option value="resolved">Resolved</option>
                  </select>
                </Td>
              </tr>
            ))}
            {data.items.length === 0 && <tr><Td className="text-muted" colSpan={6}>No feedback yet.</Td></tr>}
          </tbody>
        </table>
      </div>
      <Pager page={page} pages={data.pages} onPage={setPage} />
    </div>
  );
}

// ---------------------------------------------------------------- Launch readiness (5 KPIs + release gate)
// Format a percentage value or show a dash
const pctOr = (p) => (p == null ? '—' : `${p}%`);
const GATE_LABELS = { truth: 'Truth', reasoning: 'Reasoning', actionability: 'Actionability', impact: 'Impact' };

// Show launch KPIs and the release gate runner
function LaunchTab() {
  const [d, setD] = useState(null);
  const [gate, setGate] = useState(null);
  const [starting, setStarting] = useState(false);

  // Fetch launch readiness and gate status
  const load = useCallback(() => {
    api.get('/admin/launch-readiness').then((r) => setD(r.data)).catch(() => {});
    api.get('/admin/release-gate').then((r) => setGate(r.data)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const latest = gate?.latest || null;
  const runningNow = latest?.status === 'running';
  useEffect(() => {
    if (!runningNow) return undefined;
    const id = setInterval(load, 6000);
    return () => clearInterval(id);
  }, [runningNow, load]);

  // Kick off the release gate scenario run
  const runGate = async () => {
    if (starting || runningNow) return;
    setStarting(true);
    try {
      await api.post('/admin/release-gate/run', {});
      toast.success('Release gate started. 5 scenarios, a few minutes.');
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not start the run.');
    } finally { setStarting(false); }
  };

  if (!d) return <p className="text-sm text-muted mt-8">Loading…</p>;
  const cal = d.kpi4_outcome?.calibration || {};
  return (
    <div data-testid="admin-launch">
      <SectionTitle icon={Target}>The five launch KPIs</SectionTitle>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <Stat testId="kpi1-card" label="1 · Problem detection" value={pctOr(d.kpi1_problem_detection.pct)}
          sub={`${fmt(d.kpi1_problem_detection.yes)} yes · ${fmt(d.kpi1_problem_detection.no)} no`} />
        <Stat testId="kpi2-card" label="2 · Decision improvement" value={pctOr(d.kpi2_decision_improvement.pct)}
          sub={`${fmt(d.kpi2_decision_improvement.yes)} yes · ${fmt(d.kpi2_decision_improvement.no)} no`} />
        <Stat testId="kpi3-card" label="3 · Execution rate" value={pctOr(d.kpi3_execution.completion_pct)}
          sub={`${fmt(d.kpi3_execution.done)} done / ${fmt(d.kpi3_execution.committed)} committed`} />
        <Stat testId="kpi4-card" label="4 · Outcome improvement" value={pctOr(d.kpi4_outcome.positive_pct)}
          sub={`₹${fmt(d.kpi4_outcome.impact_inr_total)} reported impact · n=${fmt(d.kpi4_outcome.n)}`} />
        <Stat testId="kpi5-card" label="5 · Return rate" value={pctOr(d.kpi5_return.return_pct)}
          sub={`${fmt(d.kpi5_return.active_7d)} active this week`} />
      </div>
      <div className="mt-3 text-xs text-muted" data-testid="kpi-calibration">
        Prediction calibration: <span className="text-foreground">{cal.label || '—'}</span>
        {cal.n ? ` · predicted ${cal.avg_predicted_confidence}% vs actual ${cal.actual_win_rate}% (n=${cal.n})` : ''}
      </div>

      <SectionTitle icon={ShieldCheck}>Release gate · Truth / Reasoning / Actionability / Impact</SectionTitle>
      <div className="flex items-center gap-3 flex-wrap">
        <button data-testid="run-gate-btn" onClick={runGate} disabled={starting || runningNow}
          className="inline-flex items-center gap-1.5 rounded-xl bg-foreground text-background px-4 py-2 text-xs font-medium disabled:opacity-50 hover:opacity-90 transition-opacity">
          <Rocket size={13} /> {runningNow ? 'Running…' : 'Run release gate (5 scenarios)'}
        </button>
        {latest && (
          <span data-testid="gate-verdict" className={`text-xs font-medium rounded-full px-3 py-1 ${
            latest.status === 'running' ? 'bg-amber-100 text-amber-800'
            : latest.status === 'failed' ? 'bg-red-100 text-red-700'
            : latest.overall?.pass ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
            {latest.status === 'running' ? `In progress · ${(latest.scenarios || []).length}/${latest.limit} scenarios done`
              : latest.status === 'failed' ? 'Run failed'
              : latest.overall?.pass ? 'PASS — ready to ship' : `FAIL — ${latest.overall?.scenarios_passed ?? 0}/${latest.overall?.scenarios ?? 0} scenarios passed`}
          </span>
        )}
        {latest?.started_at && <span className="text-[11px] text-muted">last run {fmtDate(latest.started_at)}</span>}
      </div>

      {latest?.overall?.gate_avgs && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
          {Object.entries(GATE_LABELS).map(([k, label]) => {
            const v = latest.overall.gate_avgs[k];
            return <Stat key={k} testId={`gate-avg-${k}`} label={label} value={v != null ? `${v}/100` : '—'}
              sub={v != null ? (v >= 70 ? 'passing' : 'below the bar') : ''} />;
          })}
        </div>
      )}

      {(latest?.scenarios || []).length > 0 && (
        <div className="bg-white border border-hairline/70 rounded-xl overflow-x-auto mt-4">
          <table className="w-full" data-testid="gate-scenarios-table">
            <thead className="border-b border-hairline/60">
              <tr><Th>Scenario</Th><Th right>Truth</Th><Th right>Reason</Th><Th right>Action</Th><Th right>Impact</Th><Th>Verdict</Th></tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {latest.scenarios.map((s) => (
                <tr key={s.name} data-testid="gate-scenario-row" title={s.summary || ''}>
                  <Td className="max-w-[220px]"><span className="block truncate">{s.name}</span></Td>
                  {['truth', 'reasoning', 'actionability', 'impact'].map((g) => (
                    <Td key={g} right mono className={s.gates?.[g]?.passed ? 'text-emerald-700' : 'text-red-600'}>
                      {s.gates?.[g]?.score ?? '—'}
                    </Td>
                  ))}
                  <Td className={s.passed ? 'text-emerald-700' : 'text-red-600'}>{s.passed ? 'pass' : 'fail'}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {latest?.scenarios?.length > 0 && (
        <p className="text-[11px] text-muted mt-2">Hover a row for the judge’s one-line verdict. A release ships only when every scenario passes every gate.</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- page
// Admin page navigation tab definitions
const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'users', label: 'Users' },
  { id: 'data', label: 'Data' },
  { id: 'traffic', label: 'Traffic' },
  { id: 'usage', label: 'Usage' },
  { id: 'feedback', label: 'Feedback' },
  { id: 'launch', label: 'Launch' },
];

// Admin dashboard page with tabbed sections
export default function AdminPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState('overview');
  if (user && !user.is_admin) {
    return (
      <div className="min-h-screen">
        <TopBar title="Founder OS" backTo="/" />
        <main className="max-w-2xl mx-auto px-4 pt-16 text-center">
          <p data-testid="admin-denied" className="text-sm text-muted">This area is reserved for the founder.</p>
        </main>
      </div>
    );
  }
  return (
    <div className="min-h-screen pb-16">
      <TopBar title="Founder OS" backTo="/" />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        <div data-testid="admin-tabs" className="inline-flex flex-wrap items-center rounded-xl border border-hairline/70 bg-white p-0.5 gap-0.5">
          {TABS.map((t) => (
            <button key={t.id} data-testid={`admin-tab-${t.id}`} onClick={() => setTab(t.id)}
              className={`px-3.5 py-1.5 rounded-lg text-xs transition-colors ${tab === t.id ? 'bg-[hsl(var(--accent))] text-foreground' : 'text-muted hover:text-foreground'}`}>
              {t.label}
            </button>
          ))}
        </div>
        {tab === 'overview' && <Overview />}
        {tab === 'users' && <UsersTab />}
        {tab === 'data' && <DataTab />}
        {tab === 'traffic' && <TrafficTab />}
        {tab === 'usage' && <UsageTab />}
        {tab === 'feedback' && <FeedbackTab />}
        {tab === 'launch' && <LaunchTab />}
      </main>
    </div>
  );
}
