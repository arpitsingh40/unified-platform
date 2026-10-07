import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { api } from '../lib/api';
import { TopBar } from '../components/TopBar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import {
  Target, TrendingUp, MapPin, ListChecks, ShieldCheck, Loader2, ArrowRight, ArrowLeft,
  Lock, Check, Building2,
} from 'lucide-react';

// Guided goal setup step definitions
const STEPS = [
  {
    key: 'dream', icon: Target, title: 'What is the dream?',
    subtitle: 'In one line, the big thing you are building toward. The brain steers every decision your team makes toward this, silently. They never see it.',
  },
  {
    key: 'number', icon: TrendingUp, title: 'What is the number to hit?',
    subtitle: 'The headline target and when you want to reach it. Give a clean figure so the dashboard can track progress.',
  },
  {
    key: 'current', icon: MapPin, title: 'Where are you today?',
    subtitle: 'Roughly where you stand right now, in the same unit as your target. This sets your starting point on the progress bar.',
  },
  {
    key: 'priorities', icon: ListChecks, title: 'What are your top bets?',
    subtitle: 'The 3 to 5 things that matter most this year. One per line. The brain favours decisions that serve these.',
  },
  {
    key: 'rules', icon: ShieldCheck, title: 'Your non-negotiables',
    subtitle: 'The lines you never cross. The brain will refuse to recommend anything that breaks these.',
  },
];

// Parse a numeric input, ignoring commas
const num = (v) => {
  if (v === '' || v === null || v === undefined) return null;
  const n = Number(String(v).replace(/[, ]/g, ''));
  return Number.isFinite(n) && n >= 0 ? n : null;
};

// Guided wizard for setting the org goal
export default function GoalSetupPage() {
  const navigate = useNavigate();
  const { user, setUser } = useAuth();
  const [loading, setLoading] = useState(true);
  const [denied, setDenied] = useState(false);
  const [noOrg, setNoOrg] = useState(false);
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [hasGoal, setHasGoal] = useState(false);

  const [f, setF] = useState({
    north_star: '', target: '', deadline: '', target_arr: '', current_arr: '',
    priorities: '', decision_rules: '',
  });
  // Update one form field by key
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }));

  // Load current strategy and org ownership
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const org = await api.get('/org');
      if (!org.data.is_owner) { setDenied(true); return; }
      const s = await api.get('/org/strategy');
      setF({
        north_star: s.data.north_star || '', target: s.data.target || '', deadline: s.data.deadline || '',
        target_arr: s.data.target_arr ?? '', current_arr: s.data.current_arr ?? '',
        priorities: (s.data.priorities || []).join('\n'), decision_rules: s.data.decision_rules || '',
      });
      setHasGoal(!!s.data.north_star);
    } catch (e) {
      if (e?.response?.status === 404) setNoOrg(true);
      else setDenied(true);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Save the strategy and finish setup
  const save = async () => {
    if (saving) return;
    if (!f.north_star.trim()) { setStep(0); toast.error('Add your dream first.'); return; }
    setSaving(true);
    try {
      const priorities = f.priorities.split('\n').map((s) => s.trim()).filter(Boolean);
      const r = await api.put('/org/strategy', {
        north_star: f.north_star.trim(), target: f.target.trim(), deadline: f.deadline.trim(),
        priorities, decision_rules: f.decision_rules.trim(),
        target_arr: num(f.target_arr), current_arr: num(f.current_arr),
      });
      setUser((u) => (u ? { ...u } : u));
      toast.success(r.data.strategy_set
        ? 'Goal locked in. Every decision your team makes now bends toward it.'
        : 'Saved.');
      navigate('/app/cockpit');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not save your goal.');
    } finally { setSaving(false); }
  };

  // Advance a step or save on the last one
  const next = () => {
    if (step === 0 && !f.north_star.trim()) { toast.error('Add your dream to continue.'); return; }
    if (step < STEPS.length - 1) setStep((s) => s + 1); else save();
  };
  // Go back one step
  const back = () => { if (step > 0) setStep((s) => s - 1); };

  if (loading) {
    return (
      <div className="min-h-screen">
        <TopBar />
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10 space-y-6">
          <div className="h-4 w-20 animate-pulse rounded-md bg-primary/10" />
          <div className="h-8 w-64 animate-pulse rounded-md bg-primary/10" />
          <div className="h-4 w-48 animate-pulse rounded-md bg-primary/10" />
          <div className="h-4 w-36 animate-pulse rounded-md bg-primary/10" />
          <div className="h-px bg-border/50" />
          <div className="space-y-3">
            <div className="h-12 animate-pulse rounded-xl bg-primary/10" />
            <div className="h-12 animate-pulse rounded-xl bg-primary/10" />
            <div className="h-12 animate-pulse rounded-xl bg-primary/10" />
          </div>
        </div>
      </div>
    );
  }

  if (noOrg || denied) {
    return (
      <div className="min-h-screen">
        <TopBar />
        <div data-testid="goal-setup-blocked" className="max-w-md mx-auto text-center py-24 px-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl border mb-4 text-muted">
            {noOrg ? <Building2 size={20} /> : <Lock size={20} />}
          </div>
          <h2 className="font-display text-xl">{noOrg ? 'Create your workspace first' : 'Only the founder sets the goal'}</h2>
          <p className="text-sm text-muted mt-2">
            {noOrg
              ? 'A goal lives on your company workspace. Create one, then come back to set the goal.'
              : 'This guided setup is for the workspace owner. Your decisions are already steered by it.'}
          </p>
          <Button className="rounded-xl mt-6" onClick={() => navigate(noOrg ? '/app/team' : '/app')}>
            {noOrg ? 'Go to Team' : 'Open Brain'}
          </Button>
        </div>
      </div>
    );
  }

  const Cur = STEPS[step];
  const Icon = Cur.icon;
  const progressPct = Math.round(((step + 1) / STEPS.length) * 100);
  const lastStep = step === STEPS.length - 1;

  return (
    <div className="min-h-screen">
      <TopBar />
      <main data-testid="goal-setup-page" className="max-w-xl mx-auto px-4 sm:px-6 lg:px-8 pb-24 pt-4">
        {/* header + private badge */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] uppercase tracking-[0.14em] text-muted">
            {hasGoal ? 'Edit your goal' : 'Set up your goal'} · Step {step + 1} of {STEPS.length}
          </span>
          <span className="inline-flex items-center gap-1.5 text-[11px] px-2 py-0.5 rounded-full border bg-surface text-muted">
            <Lock size={11} /> Private to you
          </span>
        </div>

        {/* progress bar */}
        <div data-testid="goal-setup-progress" className="h-1.5 rounded-full bg-muted overflow-hidden mb-8">
          <div className="h-full bg-primary transition-all duration-300" style={{ width: `${progressPct}%` }} />
        </div>

        <section className="rounded-2xl border bg-surface p-6 sm:p-8">
          <div className="w-11 h-11 rounded-2xl bg-[hsl(var(--accent))] flex items-center justify-center mb-4 text-[hsl(var(--ring))]">
            <Icon size={20} strokeWidth={1.75} />
          </div>
          <h1 data-testid="goal-setup-step-title" className="font-display text-2xl sm:text-3xl tracking-[-0.01em]">{Cur.title}</h1>
          <p className="text-sm text-muted mt-2 leading-6">{Cur.subtitle}</p>

          <div className="mt-6 space-y-4">
            {Cur.key === 'dream' && (
              <Textarea data-testid="goal-setup-input-dream" autoFocus value={f.north_star}
                onChange={(e) => set('north_star', e.target.value)}
                placeholder="e.g. Reach 100 crore annual revenue and become the top C&I solar EPC in North India."
                className="rounded-xl min-h-[110px] text-[15px]" />
            )}

            {Cur.key === 'number' && (
              <>
                <div>
                  <label className="text-xs text-muted">Headline target (what you say out loud)</label>
                  <Input data-testid="goal-setup-input-target" value={f.target}
                    onChange={(e) => set('target', e.target.value)}
                    placeholder="100 Cr ARR" className="rounded-xl mt-1" />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-muted">Target figure (number only)</label>
                    <Input data-testid="goal-setup-input-targetarr" inputMode="numeric" value={f.target_arr}
                      onChange={(e) => set('target_arr', e.target.value)}
                      placeholder="1000000000" className="rounded-xl mt-1" />
                    <p className="text-[11px] text-muted mt-1">Used for the progress bar. Pick any unit, just be consistent.</p>
                  </div>
                  <div>
                    <label className="text-xs text-muted">By when</label>
                    <Input data-testid="goal-setup-input-deadline" value={f.deadline}
                      onChange={(e) => set('deadline', e.target.value)}
                      placeholder="Mar 2027" className="rounded-xl mt-1" />
                  </div>
                </div>
              </>
            )}

            {Cur.key === 'current' && (
              <div>
                <label className="text-xs text-muted">Where you are now (same unit as the target)</label>
                <Input data-testid="goal-setup-input-current" inputMode="numeric" value={f.current_arr}
                  onChange={(e) => set('current_arr', e.target.value)}
                  placeholder="120000000" className="rounded-xl mt-1" />
                <p className="text-[11px] text-muted mt-1">You can update this anytime from the Cockpit as you make progress.</p>
              </div>
            )}

            {Cur.key === 'priorities' && (
              <Textarea data-testid="goal-setup-input-priorities" autoFocus value={f.priorities}
                onChange={(e) => set('priorities', e.target.value)}
                placeholder={'Win commercial & industrial rooftop deals\nPush EPC ticket sizes above 50L\nProtect 18% margins'}
                className="rounded-xl min-h-[120px] text-[15px]" />
            )}

            {Cur.key === 'rules' && (
              <Textarea data-testid="goal-setup-input-rules" autoFocus value={f.decision_rules}
                onChange={(e) => set('decision_rules', e.target.value)}
                placeholder="Never quote below 18% margin. Prefer C&I over residential. Always confirm warranty terms in writing."
                className="rounded-xl min-h-[110px] text-[15px]" />
            )}
          </div>

          <div className="flex items-center justify-between mt-8">
            <Button data-testid="goal-setup-back" variant="ghost" onClick={back} disabled={step === 0}
              className="rounded-xl text-muted">
              <ArrowLeft size={15} className="mr-1.5" /> Back
            </Button>
            {lastStep ? (
              <Button data-testid="goal-setup-save" onClick={save} disabled={saving} className="rounded-xl">
                {saving ? <Loader2 className="animate-spin" size={15} /> : <><Check size={15} className="mr-1.5" /> Save & see progress</>}
              </Button>
            ) : (
              <Button data-testid="goal-setup-next" onClick={next} className="rounded-xl">
                Continue <ArrowRight size={15} className="ml-1.5" />
              </Button>
            )}
          </div>
        </section>

        {!lastStep && (
          <div className="text-center mt-4">
            <button data-testid="goal-setup-skip" onClick={save} disabled={saving}
              className="text-xs text-muted underline underline-offset-2 hover:text-foreground">
              Save what I have so far
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
