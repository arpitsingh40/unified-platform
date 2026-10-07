import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Sparkles, Check, Gift, Copy, Zap, ArrowRight } from 'lucide-react';
import { Button } from '../components/ui/button';
import { TopBar } from '../components/TopBar';
import { api } from '../lib/api';
import { useAuth } from '../App';

// Show token usage progress bar
function UsageBar({ used, budget }) {
  const pct = budget > 0 ? Math.min(100, Math.round((used / budget) * 100)) : 0;
  return (
    <div className="mt-2">
      <div className="flex items-center justify-between text-xs text-muted mb-1">
        <span>{used.toLocaleString()} / {budget.toLocaleString()} tokens used</span>
        <span className="font-mono-plex">{pct}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${pct > 80 ? 'bg-amber-500' : pct > 50 ? 'bg-primary/70' : 'bg-emerald-500'}`}
          style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// Plans, subscription, and token billing page
export default function BillingPage() {
  const { user, setCredits } = useAuth();
  const navigate = useNavigate();
  const [plans, setPlans] = useState([]);
  const [subscription, setSubscription] = useState(null);
  const [tokenUsage, setTokenUsage] = useState(null);
  const [busy, setBusy] = useState(null);
  const [referral, setReferral] = useState(null);

  // Load plans, subscription, and referral data
  const load = useCallback(async () => {
    try {
      const [p, s, r] = await Promise.all([
        api.get('/subscriptions/plans'),
        api.get('/subscriptions/my'),
        api.get('/referral'),
      ]);
      setPlans(p.data.plans || []);
      const subData = s.data;
      setSubscription(subData.subscription);
      setTokenUsage(subData.token_usage);
      setReferral(r.data);
    } catch (_e) { /* noop */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  const activePlanId = subscription?.plan_id;

  // Start the paid trial via UPI mandate
  const startTrial = async () => {
    setBusy('trial');
    try {
      const r = await api.post('/subscriptions/trial');
      window.location.assign(r.data.mandate_enrollment_url);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not start trial.');
    } finally { setBusy(null); }
  };

  // Create a subscription for a plan
  const subscribe = async (planId) => {
    setBusy(planId);
    try {
      const r = await api.post('/subscriptions/create', { plan_id: planId });
      const url = r.data.mandate_enrollment_url;
      if (url) {
        window.location.assign(url);
      } else {
        toast.success('Subscription created!');
        load();
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not start subscription.');
    } finally { setBusy(null); }
  };

  // Cancel the active subscription
  const cancelSub = async () => {
    if (!window.confirm('Cancel your subscription? You will lose access at the end of the current period.')) return;
    setBusy('cancel');
    try {
      await api.post('/subscriptions/cancel');
      toast.success('Subscription cancelled.');
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not cancel.');
    } finally { setBusy(null); }
  };

  // Buy extra tokens via checkout
  const topup = async () => {
    setBusy('topup');
    try {
      const r = await api.post('/subscriptions/topup');
      window.location.assign(r.data.checkout_url);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not start top-up.');
    } finally { setBusy(null); }
  };

  // Check whether the user is on a plan
  const isOnPlan = (planId) => {
    if (!subscription) return false;
    return subscription.plan_id === planId && ['active', 'trial'].includes(subscription.status);
  };

  // Copy the referral invite link
  const copyReferral = async () => {
    if (!referral) return;
    const url = `${window.location.origin}${referral.path}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success('Invite link copied.');
    } catch (_e) { toast.message(url); }
  };

  // Hard-coded trial plan details
  const trialPlan = {
    id: 'trial', label: 'Trial', price_inr: 99, tokens_per_month: 1_000_000,
    ultra_enabled: true, model: 'deepseek-flash',
    features: ['1M tokens (enough for ~150 turns)', 'DeepSeek Flash reasoning',
               'Ultra thinking mode', '3-day access', 'UPI mandate setup'],
  };

  return (
    <div className="relative z-10 min-h-screen">
      <TopBar title="Plans & tokens" backTo="/" />
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
        <div className="max-w-2xl">
          <p className="text-xs uppercase tracking-[0.18em] text-muted mb-3">Pricing</p>
          <h1 data-testid="billing-title" className="font-display text-3xl sm:text-4xl leading-tight">
            Pick the plan that matches how seriously you&apos;re pursuing this.
          </h1>
          <p className="mt-4 text-sm md:text-base text-muted leading-6">
            Monthly subscription via UPI autopay. Each plan includes <strong>10 million tokens</strong> per month. Unused tokens expire at the end of each billing period.
          </p>
        </div>

        {subscription && tokenUsage && (
          <div className="mt-8 rounded-2xl border border-hairline/70 bg-surface p-5 max-w-xl">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[11px] uppercase tracking-[0.16em] text-muted">Current plan</span>
                <p className="font-display text-lg mt-0.5">{subscription.label || subscription.plan_id}
                  <span className={`ml-2 text-[10px] uppercase tracking-[0.14em] px-2 py-0.5 rounded-full border ${
                    subscription.status === 'active' ? 'border-emerald-400/40 text-emerald-700 bg-emerald-50'
                    : subscription.status === 'trial' ? 'border-amber-400/40 text-amber-700 bg-amber-50'
                    : 'border-hairline/70 text-muted'
                  }`}>{subscription.status}</span>
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={cancelSub} disabled={busy === 'cancel'}
                className="rounded-lg text-xs h-8">
                Cancel
              </Button>
            </div>
            <UsageBar used={tokenUsage.used || 0} budget={tokenUsage.budget || 0} />
            <Button onClick={topup} disabled={busy === 'topup'} variant="outline" size="sm"
              className="mt-3 rounded-lg text-xs h-8">
              <Zap size={12} className="mr-1.5" /> Buy 10M extra tokens — ₹4,999
            </Button>
          </div>
        )}

        {!subscription && (
          <div className="mt-8">
            <Button onClick={startTrial} disabled={busy === 'trial'}
              className="rounded-full h-12 px-8 text-sm font-medium mb-2 active:scale-[0.98]">
              <Sparkles size={16} className="mr-2" />
              {busy === 'trial' ? 'Starting\u2026' : `Start with ₹99 trial for 3 days`}
            </Button>
            <p className="text-xs text-muted">Pay ₹99, set up UPI autopay, get 1M tokens for 3 days. After trial, choose Standard or Pro.</p>
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-5 md:gap-6 mt-10">
          {plans.map((p) => {
            const active = isOnPlan(p.id);
            const best = p.id === 'pro';
            return (
              <div key={p.id} data-testid={`plan-card-${p.id}`}
                className={`relative bg-white border rounded-2xl p-7 flex flex-col transition-all ${
                  best ? 'border-foreground/40 shadow-[0_10px_40px_-12px_rgba(0,0,0,0.25)] md:scale-[1.03]'
                  : 'border-hairline/70'
                } ${active ? 'ring-2 ring-primary/40' : ''}`}>
                {best && !active && (
                  <span data-testid={`plan-tag-${p.id}`}
                    className="absolute -top-3 left-7 inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.16em] bg-foreground text-background border border-foreground rounded-full px-3 py-1">
                    <Sparkles size={11} /> Best Value
                  </span>
                )}
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted">{p.label}</p>
                <div className="mt-5 flex items-baseline gap-1.5">
                  <span className="font-display text-4xl">₹{p.price_inr}</span>
                  <span className="text-xs text-muted">/month</span>
                </div>
                <p className="font-mono-plex text-sm mt-1 text-foreground/80">
                  {(p.tokens_per_month / 1_000_000).toLocaleString()}M tokens / mo
                </p>
                <p className="mt-1.5 text-[11px] font-mono-plex text-muted">
                  {p.id === 'pro' ? 'deepseek-v4' : 'deepseek-flash'}
                </p>

                <ul className="mt-5 space-y-2.5 text-sm leading-5 text-foreground/85 flex-1">
                  {(p.features || []).map((f, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <Check size={14} strokeWidth={2}
                        className={`mt-0.5 shrink-0 ${best ? 'text-foreground' : 'text-muted'}`} />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>

                <Button onClick={() => subscribe(p.id)} disabled={busy === p.id || active}
                  data-testid={`plan-subscribe-${p.id}`}
                  className={`mt-6 rounded-xl w-full active:scale-[0.98] ${
                    active ? 'bg-muted text-muted cursor-default'
                    : best ? '' : 'bg-white text-foreground border border-hairline/70 hover:bg-[hsl(var(--accent))]'
                  }`}>
                  {busy === p.id ? 'Redirecting\u2026' : active ? 'Current plan' : `Subscribe — ₹${p.price_inr}/mo`}
                </Button>
              </div>
            );
          })}
        </div>

        <p className="mt-6 text-[11px] text-muted/80 max-w-3xl">
          All plans include <strong>UPI autopay</strong> billing. Your mandate is set up once and charges recur monthly. Cancel anytime from your UPI app or here.
        </p>

        {referral ? (
          <div className="mt-12 rounded-2xl border border-emerald-300/50 bg-emerald-50/50 p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4" data-testid="referral-block">
            <div className="flex items-start gap-3">
              <span className="inline-flex items-center justify-center w-9 h-9 rounded-xl bg-emerald-600 text-white shrink-0">
                <Gift size={17} />
              </span>
              <div>
                <div className="font-display text-lg">Give {referral.bonus}, get {referral.bonus}.</div>
                <p className="text-sm text-muted mt-0.5">
                  Invite a founder. When they sign up with your link, you both get {referral.bonus} credits.
                  {referral.invited_count > 0 ? ` You've invited ${referral.invited_count} and earned ${referral.credits_earned} credits.` : ''}
                </p>
              </div>
            </div>
            <Button onClick={copyReferral} variant="outline" className="rounded-full shrink-0" data-testid="referral-copy-btn">
              <Copy size={14} className="mr-2" /> Copy invite link
            </Button>
          </div>
        ) : null}

        <div className="mt-12 rounded-xl border border-hairline/60 bg-surface/50 p-5 text-sm text-muted leading-6">
          <p className="font-medium text-foreground mb-1">How token billing works</p>
          <p>Every AI response consumes tokens based on the length of the conversation context and the generated reply. A typical turn uses <strong>2,000–6,000 tokens</strong> (normal mode) or <strong>8,000–15,000 tokens</strong> (ultra mode with extended thinking). At 10M tokens per month, you can have roughly <strong>1,500–3,000 normal turns</strong> or <strong>600–1,000 ultra turns</strong>. Additional tokens can be purchased any time.</p>
        </div>
      </main>
    </div>
  );
}
