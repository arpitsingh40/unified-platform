import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import {
  ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle2, XCircle, Clock,
  Wrench, IndianRupee, Pause, Play, ChevronRight, RotateCcw, Undo2,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { TopBar } from '../components/TopBar';
import { api } from '../lib/api';
import { useAuth } from '../App';

/* Mission Control — the founder's command surface for the executive organization.
   Constitution in UI form:
     §6 Authority Gradient  — nothing high-stakes runs without your approval
     §8 Explainability      — the Approval Brief shows every outcome before you decide
     §10 Human Override     — the kill switch is always one tap away
     §5 Evidence-First      — verification results are shown as they really are */

// Status badge styles per task status
const STATUS_STYLE = {
  proposed: 'text-amber-600 bg-amber-500/10 border-amber-500/30',
  verified: 'text-emerald-600 bg-emerald-500/10 border-emerald-500/30',
  executed: 'text-sky-600 bg-sky-500/10 border-sky-500/30',
  manual: 'text-violet-600 bg-violet-500/10 border-violet-500/30',
  failed: 'text-red-600 bg-red-500/10 border-red-500/30',
  rejected: 'text-muted bg-surface-2 border-hairline',
  approved: 'text-sky-600 bg-sky-500/10 border-sky-500/30',
};

// Render a colored status badge
function StatusChip({ status }) {
  return (
    <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full border ${STATUS_STYLE[status] || 'text-muted border-hairline'}`}>
      {status}
    </span>
  );
}

// Show monthly autonomous spend budget
function BudgetBar({ budget }) {
  if (!budget) return null;
  const pct = budget.cap_inr > 0 ? Math.min(100, Math.round((budget.spent_inr / budget.cap_inr) * 100)) : 0;
  return (
    <div className="rounded-2xl border border-hairline p-4 flex-1 min-w-[220px]" data-testid="mc-budget">
      <div className="flex items-center justify-between text-xs text-muted mb-2">
        <span className="flex items-center gap-1"><IndianRupee size={12} /> Autonomous spend · {budget.month}</span>
        <span className="font-mono-plex">₹{budget.spent_inr.toLocaleString('en-IN')} / ₹{budget.cap_inr.toLocaleString('en-IN')}</span>
      </div>
      <div className="h-2 rounded-full bg-surface-2 overflow-hidden">
        <div className={`h-full rounded-full ${pct > 85 ? 'bg-red-500' : 'bg-accent'}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-[11px] text-muted mt-2">₹{budget.remaining_inr.toLocaleString('en-IN')} remaining this month. Hard cap — nothing exceeds it without you.</p>
    </div>
  );
}

// Show approval brief with actions
function Brief({ brief, onApprove, onReject, busy }) {
  if (!brief) return null;
  const t = brief.task || {};
  return (
    <div className="rounded-2xl border border-accent/30 bg-surface-1 p-5 space-y-4" data-testid="mc-brief">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.15em] text-muted">Approval brief</p>
          <h3 className="font-display text-lg mt-1">{t.description}</h3>
        </div>
        <StatusChip status={t.status} />
      </div>

      <div className="grid sm:grid-cols-2 gap-3 text-sm">
        <div className="rounded-xl bg-surface-2/60 p-3">
          <p className="text-[10px] uppercase tracking-wider text-muted mb-1">Who runs it</p>
          <p>{brief.executive?.role || 'Executive'} · {brief.executive?.department || 'general'}</p>
          <p className="text-xs text-muted mt-1">Spending limit ₹{(brief.executive?.spending_limit_inr ?? 0).toLocaleString('en-IN')}</p>
        </div>
        <div className="rounded-xl bg-surface-2/60 p-3">
          <p className="text-[10px] uppercase tracking-wider text-muted mb-1">Success looks like</p>
          <p>{brief.expected_outcome || '—'}</p>
        </div>
        <div className="rounded-xl bg-surface-2/60 p-3">
          <p className="text-[10px] uppercase tracking-wider text-muted mb-1">Can it be undone?</p>
          <p className={t.reversibility === 'IRREVERSIBLE' ? 'text-red-600' : ''}>
            {t.reversibility === 'IRREVERSIBLE' ? 'No — irreversible' : t.reversibility === 'PARTIALLY_REVERSIBLE' ? 'Partially' : 'Yes — reversible'}
          </p>
        </div>
        <div className="rounded-xl bg-surface-2/60 p-3">
          <p className="text-[10px] uppercase tracking-wider text-muted mb-1">Estimated spend</p>
          <p>{brief.estimated_spend_inr > 0 ? `₹${brief.estimated_spend_inr.toLocaleString('en-IN')}` : 'None'}</p>
        </div>
      </div>

      {(brief.risk_flags || []).length > 0 && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3" data-testid="mc-risk-flags">
          <p className="text-[10px] uppercase tracking-wider text-amber-600 mb-1 flex items-center gap-1"><AlertTriangle size={12} /> Risk flags</p>
          <ul className="text-sm space-y-1">
            {brief.risk_flags.map((f) => <li key={f}>· {f}</li>)}
          </ul>
        </div>
      )}

      <div className="text-sm space-y-2">
        <p><span className="text-muted">Worst case:</span> {brief.worst_case}</p>
        <p><span className="text-muted">If you approve:</span> {brief.what_happens_if_approved}</p>
        {brief.tool_recommendation?.best && (
          <p className="text-xs text-muted flex items-center gap-1">
            <Wrench size={12} /> Recommended tool: {brief.tool_recommendation.best.tool_slug}
          </p>
        )}
      </div>

      <div className="flex gap-2 pt-1">
        <Button onClick={onApprove} disabled={busy} className="rounded-xl" data-testid="mc-approve-btn">
          <CheckCircle2 size={15} className="mr-1.5" /> Approve
        </Button>
        <Button onClick={onReject} disabled={busy} variant="outline" className="rounded-xl" data-testid="mc-reject-btn">
          <XCircle size={15} className="mr-1.5" /> Reject
        </Button>
      </div>
    </div>
  );
}

// Founder approval queue and kill switch page
export default function MissionControlPage() {
  const { user } = useAuth();
  const [pending, setPending] = useState([]);
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState([]);
  const [brief, setBrief] = useState(null);
  const [briefFor, setBriefFor] = useState(null);
  const [busy, setBusy] = useState(false);
  const [denied, setDenied] = useState(false);

  // Load pending tasks, summary, and history
  const load = useCallback(() => {
    api.get('/tasks/pending').then((r) => setPending(r.data.tasks || [])).catch(() => {});
    api.get('/tasks/summary').then((r) => setSummary(r.data)).catch((e) => {
      if (e?.response?.status === 403) setDenied(true);
    });
    api.get('/tasks', { params: {} }).then((r) => setHistory((r.data.tasks || []).filter((t) => t.status !== 'proposed').slice(0, 20))).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, [load]);

  // Fetch the approval brief for a task
  const openBrief = (task) => {
    setBriefFor(task.id);
    api.get(`/tasks/${task.id}/brief`)
      .then((r) => setBrief(r.data))
      .catch((e) => {
        setBriefFor(null);
        toast.error(e?.response?.data?.detail || 'Could not load the brief');
      });
  };

  // Post an approval action and refresh
  const act = (path, body) => {
    setBusy(true);
    api.post(path, body || {})
      .then((r) => {
        const st = r.data?.task?.status || r.data?.status;
        if (st === 'verified') toast.success('Executed and verified — evidence stored.');
        else if (st === 'manual') toast.success('Approved — moved to the manual queue (no tools connected).');
        else if (st === 'rejected') toast.success('Rejected.');
        else toast.success('Done.');
        setBrief(null); setBriefFor(null); load();
      })
      .catch((e) => toast.error(e?.response?.data?.detail || 'Action failed'))
      .finally(() => setBusy(false));
  };

  // Pause or resume autonomous execution
  const toggleKillSwitch = () => {
    const paused = !(summary?.budget?.execution_paused);
    api.post('/tasks/kill-switch', { paused })
      .then(() => { toast.success(paused ? 'All autonomous execution paused.' : 'Execution resumed.'); load(); })
      .catch((e) => toast.error(e?.response?.data?.detail || 'Only the founder can do that'));
  };

  const paused = summary?.budget?.execution_paused;

  return (
    <div className="min-h-screen">
      <TopBar />
      <main className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="mission-control-page">
        <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-muted flex items-center gap-1.5">
              <ShieldCheck size={12} /> Mission control
            </p>
            <h1 className="font-display text-2xl sm:text-3xl mt-1">Your organization, under your authority.</h1>
            <p className="text-sm text-muted mt-1">Nothing high-stakes runs without you. Every outcome is verified, never assumed.</p>
          </div>
          <Button onClick={toggleKillSwitch} variant={paused ? 'default' : 'outline'}
            className={`rounded-xl ${paused ? '' : 'border-red-500/40 text-red-600 hover:bg-red-500/10'}`}
            data-testid="mc-kill-switch">
            {paused ? <><Play size={15} className="mr-1.5" /> Resume execution</> : <><Pause size={15} className="mr-1.5" /> Pause everything</>}
          </Button>
        </div>

        {paused && (
          <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-4 mb-6 flex items-center gap-2 text-sm" data-testid="mc-paused-banner">
            <ShieldAlert size={16} className="text-red-600" />
            Execution is paused. Approvals are blocked until you resume.
          </div>
        )}

        <div className="flex flex-wrap gap-4 mb-8">
          {[
            { label: 'Awaiting your approval', value: summary?.proposed ?? '—', hot: (summary?.proposed || 0) > 0 },
            { label: 'Verified done', value: summary?.verified ?? '—' },
            { label: 'Manual queue', value: summary?.manual ?? '—' },
            { label: 'Failed', value: summary?.failed ?? '—' },
          ].map((s) => (
            <div key={s.label} className={`rounded-2xl border p-4 min-w-[150px] ${s.hot ? 'border-amber-500/40' : 'border-hairline'}`}>
              <div className="font-display text-2xl">{s.value}</div>
              <div className="text-[11px] uppercase tracking-wider text-muted mt-1">{s.label}</div>
            </div>
          ))}
          <BudgetBar budget={summary?.budget} />
        </div>

        <section className="mb-10">
          <h2 className="font-display text-lg mb-3">Approval queue</h2>
          {pending.length === 0 && (
            <p className="text-sm text-muted rounded-2xl border border-dashed border-hairline p-6" data-testid="mc-empty-queue">
              Nothing waiting on you. When your executives propose work, it lands here first — with a full brief.
            </p>
          )}
          <div className="space-y-3">
            {pending.map((t) => (
              <div key={t.id} className="rounded-2xl border border-hairline p-4" data-testid="mc-task-row">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm">{t.description}</p>
                    <p className="text-xs text-muted mt-1">
                      {t.capability} · {t.reversibility === 'IRREVERSIBLE' ? 'irreversible' : 'reversible'} · authority {t.authority_required}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <StatusChip status={t.status} />
                    <Button size="sm" variant="outline" className="rounded-xl" onClick={() => openBrief(t)} data-testid="mc-review-btn">
                      Review <ChevronRight size={14} className="ml-0.5" />
                    </Button>
                  </div>
                </div>
                {briefFor === t.id && (
                  <div className="mt-4">
                    <Brief brief={brief} busy={busy}
                      onApprove={() => act(`/tasks/${t.id}/approve`)}
                      onReject={() => act(`/tasks/${t.id}/reject`, { reason: 'Rejected from Mission Control' })} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="font-display text-lg mb-3">Execution ledger</h2>
          <p className="text-xs text-muted mb-3">What actually happened — verified outcomes, honest failures, manual handoffs.</p>
          <div className="space-y-2">
            {history.length === 0 && <p className="text-sm text-muted">No executions yet.</p>}
            {history.map((t) => (
              <div key={t.id} className="rounded-xl border border-hairline px-4 py-3 flex items-center justify-between gap-3" data-testid="mc-ledger-row">
                <div className="min-w-0">
                  <p className="text-sm truncate">{t.description}</p>
                  <p className="text-[11px] text-muted mt-0.5 truncate">
                    {t.result || t.error || '—'}
                    {t.verification?.outcome ? ` · verified ${t.verification.outcome} (${Math.round((t.verification.confidence || 0) * 100)}%)` : ''}
                  </p>
                </div>
                <StatusChip status={t.status} />
              </div>
            ))}
          </div>
        </section>

        {denied && (
          <p className="text-sm text-muted mt-8" data-testid="mc-denied">
            You can see your organization's tasks, but approvals are the founder's.
          </p>
        )}
      </main>
    </div>
  );
}
