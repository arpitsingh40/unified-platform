import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../App';
import { api } from '../lib/api';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import {
  Brain, Gauge, Scale, Lightbulb, Rocket, Loader2, ArrowRight, AlertTriangle,
  MessageSquarePlus, Eye,
} from 'lucide-react';

// Public shareable decision card page
export default function DecisionCardPage() {
  const { shareId } = useParams();
  const { user } = useAuth();
  const [card, setCard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);
  const [opinion, setOpinion] = useState('');
  const [posting, setPosting] = useState(false);

  useEffect(() => {
    api.get(`/share/${shareId}`)
      .then((r) => setCard(r.data))
      .catch(() => setMissing(true))
      .finally(() => setLoading(false));
  }, [shareId]);

  // Post a second opinion on the card
  const postOpinion = useCallback(async () => {
    const text = opinion.trim();
    if (!text || posting) return;
    setPosting(true);
    try {
      const r = await api.post(`/share/${shareId}/opinion`, { text });
      setCard((c) => (c ? { ...c, opinions: r.data.opinions } : c));
      setOpinion('');
      toast.success('Your take is on the card.');
    } catch (e) {
      const msg = e?.response?.status === 400
        ? 'You cannot leave a second opinion on your own decision.'
        : 'Could not post your take, try again.';
      toast.error(msg);
    } finally { setPosting(false); }
  }, [opinion, posting, shareId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin text-muted" size={22} />
      </div>
    );
  }

  if (missing || !card) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-4 text-center" data-testid="card-missing">
        <Brain size={28} className="text-muted mb-3" />
        <h1 className="font-display text-2xl">This decision card is gone</h1>
        <p className="text-sm text-muted mt-2">The founder may have removed it.</p>
        <Link to="/" className="mt-6">
          <Button className="rounded-full">Think through your own decision <ArrowRight size={15} className="ml-2" /></Button>
        </Link>
      </div>
    );
  }

  const c = card.card || {};

  return (
    <div className="min-h-screen flex flex-col">
      {/* public brand bar */}
      <header className="w-full border-b border-hairline/60">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 font-display text-base">
            <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-primary text-primary-foreground">
              <Brain size={15} strokeWidth={1.75} />
            </span>
            SmartDecigen
          </Link>
          <span className="text-[11px] text-muted hidden sm:inline">Your company. Running on autopilot.</span>
        </div>
      </header>

      <main className="flex-1 w-full max-w-3xl mx-auto px-4 sm:px-6 py-10" data-testid="decision-card-page">
        <div className="text-center mb-6">
          <div className="inline-flex items-center gap-2 text-xs text-muted rounded-full border border-hairline/70 px-3 py-1">
            <Eye size={12} /> {card.views} views
          </div>
          <h1 className="font-display text-2xl sm:text-3xl mt-4 tracking-[-0.02em]" data-testid="card-founder-line">
            {card.founder_name} made this call
          </h1>
          <p className="text-xs text-muted mt-1.5">
            Shaped with a decision intelligence engine, uncertainty mapped, trade-offs priced.
          </p>
        </div>

        <div className="rounded-2xl border border-hairline/70 bg-surface p-6 space-y-5 shadow-sm" data-testid="public-decision-card">
          {c.decision ? (
            <div className="rounded-xl bg-primary/5 border border-primary/20 px-4 py-3">
              <span className="text-[11px] uppercase tracking-wide text-muted block">The call</span>
              <div className="font-display text-lg leading-snug mt-0.5" data-testid="card-decision">{c.decision}</div>
            </div>
          ) : null}

          {c.goal ? <div className="text-sm text-foreground/90" data-testid="card-goal">{c.goal}</div> : null}

          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 text-xs rounded-full bg-secondary px-2.5 py-1" data-testid="card-odds">
              <Gauge size={12} /> ~{c.success_probability}% odds
            </span>
            {typeof c.confidence === 'number' ? (
              <span className="inline-flex items-center gap-1 text-xs rounded-full bg-secondary px-2.5 py-1" data-testid="card-confidence">
                <Brain size={12} /> {c.confidence}% decision confidence
              </span>
            ) : null}
          </div>
          {c.probability_rationale ? (
            <div className="text-xs text-muted -mt-2">{c.probability_rationale}</div>
          ) : null}

          {c.highest_leverage ? (
            <div className="flex items-start gap-2 rounded-xl bg-secondary/60 px-3 py-2.5 text-sm">
              <Lightbulb size={15} className="mt-0.5 shrink-0 text-primary" />
              <div>
                <span className="text-[11px] uppercase tracking-wide text-muted block">Highest leverage</span>
                {c.highest_leverage}
              </div>
            </div>
          ) : null}

          {c.trade_offs?.length ? (
            <div data-testid="card-tradeoffs">
              <div className="text-[11px] uppercase tracking-wide text-muted flex items-center gap-1 mb-1.5">
                <Scale size={12} /> Trade-offs accepted
              </div>
              <ul className="space-y-1">
                {c.trade_offs.map((t, i) => (
                  <li key={i} className="text-sm leading-snug text-foreground/90">{t}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {c.first_moves?.length ? (
            <div data-testid="card-first-moves">
              <div className="text-[11px] uppercase tracking-wide text-muted flex items-center gap-1 mb-1.5">
                <Rocket size={12} /> First moves
              </div>
              <ol className="space-y-1">
                {c.first_moves.map((t, i) => (
                  <li key={i} className="text-sm leading-snug text-foreground/90">{i + 1}. {t}</li>
                ))}
              </ol>
            </div>
          ) : null}

          {c.risks?.length ? (
            <div data-testid="card-risks">
              <div className="text-[11px] uppercase tracking-wide text-muted flex items-center gap-1 mb-1.5">
                <AlertTriangle size={12} /> Eyes open on
              </div>
              <ul className="space-y-1">
                {c.risks.map((t, i) => (
                  <li key={i} className="text-sm leading-snug text-foreground/90">{t}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        {/* second opinions */}
        <div className="mt-8" data-testid="card-opinions">
          <div className="text-xs font-medium uppercase tracking-wide text-muted flex items-center gap-1.5 mb-3">
            <MessageSquarePlus size={13} /> Second opinions ({(card.opinions || []).length})
          </div>
          {(card.opinions || []).length ? (
            <div className="space-y-3">
              {card.opinions.map((o, i) => (
                <div key={i} className="rounded-xl border border-hairline/60 bg-surface/60 px-4 py-3" data-testid="opinion-row">
                  <div className="text-xs font-medium">{o.name}</div>
                  <div className="text-sm text-foreground/90 mt-0.5 whitespace-pre-wrap">{o.text}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-muted">No takes yet. Be the first founder to weigh in.</div>
          )}

          {user ? (
            <div className="mt-4 space-y-2">
              <Textarea
                data-testid="opinion-input"
                value={opinion}
                onChange={(e) => setOpinion(e.target.value)}
                rows={2}
                maxLength={1000}
                placeholder="Your take as a founder, what would you do differently?"
                className="resize-none rounded-xl text-sm"
              />
              <Button data-testid="opinion-submit" onClick={postOpinion} disabled={!opinion.trim() || posting} className="rounded-full" size="sm">
                {posting ? <Loader2 className="animate-spin mr-2" size={14} /> : null}
                {posting ? 'Posting' : 'Add your take'}
              </Button>
              {user?.email ? <p className="text-[11px] text-muted">Posting as {user.email}</p> : null}
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-hairline/70 px-4 py-3 flex items-center justify-between gap-3" data-testid="opinion-signup-cta">
              <span className="text-sm text-muted">Sign up to add your take, it takes 30 seconds.</span>
              <Link to="/auth">
                <Button size="sm" variant="outline" className="rounded-full shrink-0">Sign up</Button>
              </Link>
            </div>
          )}
        </div>

        {/* conversion CTA */}
        <div className="mt-10 rounded-2xl border border-primary/25 bg-secondary/40 p-6 text-center" data-testid="card-cta">
          <h2 className="font-display text-xl">Facing a call like this in your business?</h2>
          <p className="text-sm text-muted mt-1.5">
            SmartDecigen maps your uncertainty, asks only the questions that matter, and hands you the decision, trade-offs and first moves.
          </p>
          <Link to="/auth" className="inline-block mt-4">
            <Button className="rounded-full px-6" data-testid="card-cta-btn">
              Think through my decision <ArrowRight size={15} className="ml-2" />
            </Button>
          </Link>
        </div>
      </main>
    </div>
  );
}
