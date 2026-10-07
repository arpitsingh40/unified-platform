import { useNavigate } from 'react-router-dom';
import { Check, Sparkles, Zap } from 'lucide-react';
import { Button } from '../ui/button';

// Pricing tiers with credits, features, and popular flag.
const PLANS = [
  {
    id: 'starter',
    label: 'Starter',
    price: '₹49',
    period: 'one-time',
    credits: '10 credits',
    popular: false,
    features: ['10 decision turns', 'DeepSeek Flash reasoning', 'Never expires', 'One-time payment'],
  },
  {
    id: 'pro',
    label: 'Pro',
    price: '₹399',
    period: 'one-time',
    credits: '50 credits',
    popular: false,
    features: ['50 decision turns', 'DeepSeek Flash reasoning', 'Ultra thinking mode', 'Document upload', 'Never expires'],
  },
  {
    id: 'elite',
    label: 'Elite',
    price: '₹999',
    period: 'one-time',
    credits: '500 credits',
    popular: true,
    features: ['500 decision turns', 'DeepSeek V4 — best model', 'Ultra thinking mode', 'Document upload', 'Priority support', 'Never expires'],
  },
];

// Pricing grid with the three one-time credit plans.
export default function PricingSection() {
  const navigate = useNavigate();
  return (
    <section id="pricing" className="relative py-24 sm:py-32 bg-surface-2">
      <div className="max-w-6xl mx-auto px-6 sm:px-10 lg:px-14">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <span className="inline-flex items-center gap-2 text-[11px] tracking-[0.26em] uppercase text-accent font-semibold mb-5">
            <span className="h-px w-8 bg-accent" />
            Pricing
          </span>
          <h2 className="font-display text-4xl sm:text-5xl text-text tracking-tight leading-[1.1]">
            Pay for what you use.<br />
            <span className="text-accent">Credits never expire.</span>
          </h2>
          <p className="mt-4 text-sm text-muted max-w-md mx-auto">
            2 credits per 1,000 tokens. One-time purchase. No subscription required.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-5 md:gap-6 items-start">
          {PLANS.map((p) => (
            <div key={p.id}
              className={`relative rounded-2xl p-7 flex flex-col transition-all ${
                p.popular
                  ? 'bg-surface border-2 border-accent shadow-elevation-2 md:scale-[1.03]'
                  : 'bg-surface border border-hairline'
              }`}>
              {p.popular && (
                <span className="absolute -top-3 left-7 inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.16em] bg-accent text-white rounded-full px-3 py-1">
                  <Sparkles size={11} /> Best Value
                </span>
              )}
              <p className="text-[11px] uppercase tracking-[0.18em] text-muted">{p.label}</p>
              <div className="mt-5 flex items-baseline gap-1.5">
                <span className="font-display text-4xl text-text">{p.price}</span>
                <span className="text-xs text-muted">{p.period}</span>
              </div>
              <p className="font-mono-plex text-sm mt-1 text-muted">{p.credits}</p>
              <ul className="mt-5 space-y-2.5 text-sm leading-5 flex-1">
                {p.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <Check size={14} strokeWidth={2} className="mt-0.5 shrink-0 text-accent" />
                    <span className="text-muted">{f}</span>
                  </li>
                ))}
              </ul>
              <Button onClick={() => navigate('/auth')}
                className={`mt-6 rounded-xl w-full active:scale-[0.98] ${
                  p.popular
                    ? 'bg-accent hover:bg-accent/90 text-white'
                    : 'border border-hairline bg-surface hover:bg-surface-2 text-text'
                }`}>
                {p.id === 'starter' ? (
                  <><Zap size={14} className="mr-2" /> Start your company</>
                ) : (
                  `Buy — ${p.price}`
                )}
              </Button>
            </div>
          ))}
        </div>

        <p className="mt-6 text-[11px] text-muted text-center max-w-xl mx-auto">
          All plans include <strong>full platform access</strong>. Credits are used per decision turn. 100 free credits on signup.
        </p>
      </div>
    </section>
  );
}
