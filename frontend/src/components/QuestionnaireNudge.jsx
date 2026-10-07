import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Sparkles, ArrowRight, X } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { useAuth } from '../App';

// Storage key — set to '1' once the user dismisses, cleared once they finish the questionnaire.
const DISMISS_KEY = 'sdg_questionnaire_nudge_dismissed';

/**
 * Post-login nudge: "Unlock ₹399 worth of credits — answer 4 quick questions."
 * - Shows only when:
 *    • user is authenticated
 *    • questionnaire_completed !== true
 *    • not currently on /auth or /questionnaire (no nag on those pages)
 *    • the user hasn't dismissed it in this browser
 * - Once the user finishes the questionnaire elsewhere, the dismiss flag is wiped so
 *   future signups on the same browser still see it.
 */
export function QuestionnaireNudge() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);

  const completed = !!user?.questionnaire_completed;
  const onAuthRoute = location.pathname === '/auth' || location.pathname.startsWith('/questionnaire');
  let dismissed = false;
  try { dismissed = typeof window !== 'undefined' && localStorage.getItem(DISMISS_KEY) === '1'; } catch (_e) { /* noop */ }
  const eligible = !!token && !!user && !completed && !onAuthRoute && !dismissed;

  useEffect(() => {
    // wipe the dismiss flag when completed -> next account on same browser still gets nudged
    if (completed) {
      try { localStorage.removeItem(DISMISS_KEY); } catch (_e) { /* noop */ }
    }
  }, [completed]);

  useEffect(() => {
    if (!eligible) return undefined;
    // tiny delay so it appears after the dashboard renders, not on top of route transition
    const t = setTimeout(() => setOpen(true), 450);
    return () => clearTimeout(t);
  }, [eligible]);

  // Mark the nudge dismissed in localStorage and hide it.
  const dismiss = () => {
    try { localStorage.setItem(DISMISS_KEY, '1'); } catch (_e) { /* noop */ }
    setOpen(false);
  };

  // Close the nudge and navigate to the questionnaire.
  const start = () => {
    setOpen(false);
    navigate('/app/questionnaire');
  };

  if (!eligible) return null;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) dismiss(); }}>
      <DialogContent
        data-testid="questionnaire-nudge-modal"
        className="sm:max-w-md rounded-2xl border border-hairline/70 p-0 overflow-hidden"
      >
        {/* a11y: Radix requires a DialogTitle inside DialogContent. Visually hidden — the
            real headline (the H3 below) carries the design weight. */}
        <DialogTitle className="sr-only">Unlock ₹399 worth of credits — free</DialogTitle>
        {/* gold corner glow */}
        <div
          aria-hidden="true"
          className="absolute -top-24 -right-24 w-56 h-56 rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(circle, rgba(184,145,101,0.25) 0%, rgba(184,145,101,0) 70%)' }}
        />
        <button
          data-testid="questionnaire-nudge-close"
          onClick={dismiss}
          className="absolute top-3 right-3 text-muted hover:text-foreground transition-colors z-10"
          aria-label="Close"
        >
          <X size={16} strokeWidth={1.75} />
        </button>
        <div className="relative p-7">
          <div className="flex items-center gap-1.5 mb-3">
            <Sparkles size={12} className="text-[#b89165]" />
            <span className="text-[10px] tracking-[0.22em] font-semibold uppercase text-[#b89165]">
              Free unlock · One-time
            </span>
          </div>
          <h3 className="font-display text-[26px] leading-tight">
            Tell us about <span className="text-[#b89165]">your business</span> — free.
          </h3>
          <p className="text-sm text-muted mt-3 leading-6">
            Answer 4 short questions about your dream, capacity, advantage, and potential.
            We use them to ground every plan we draft for you.
          </p>
          <ul className="mt-5 space-y-2 text-[13px] text-foreground/80">
            <li className="flex items-start gap-2">
              <span className="w-5 h-5 rounded-full bg-foreground/[0.06] text-foreground/70 text-[10px] font-semibold flex items-center justify-center shrink-0 mt-0.5">1</span>
              <span>Takes about ~90 seconds.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-5 h-5 rounded-full bg-foreground/[0.06] text-foreground/70 text-[10px] font-semibold flex items-center justify-center shrink-0 mt-0.5">2</span>
              <span>Your answers shape every plan we create.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="w-5 h-5 rounded-full bg-foreground/[0.06] text-foreground/70 text-[10px] font-semibold flex items-center justify-center shrink-0 mt-0.5">3</span>
              <span>Tailored to your reality, not generic advice.</span>
            </li>
          </ul>
          <div className="mt-7 flex items-center gap-3">
            <Button
              data-testid="questionnaire-nudge-start"
              onClick={start}
              className="rounded-xl flex-1 active:scale-[0.98] transition-transform"
            >
              Get started
              <ArrowRight size={15} strokeWidth={2} className="ml-2" />
            </Button>
            <button
              type="button"
              data-testid="questionnaire-nudge-later"
              onClick={dismiss}
              className="text-xs text-muted hover:text-foreground transition-colors px-3"
            >
              Maybe later
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
