import { useState, useEffect, useRef } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { api } from '../lib/api';
import { useAuth } from '../App';
import { trackPixel } from '../lib/pixel';

const POLL_INTERVAL_MS = 3000;
const MAX_ATTEMPTS = 20; // 20 × 3s = 60s window — Zoho can take 30–45s to settle
const AUTO_REDIRECT_DELAY_MS = 2500;

// Verify payment status after checkout redirect
export default function PaymentResultPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const orderId = params.get('order_id');
  const auth = useAuth();
  const setCredits = auth?.setCredits;
  const isLoggedIn = !!auth?.user;
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [attempts, setAttempts] = useState(0);
  const attemptsRef = useRef(0);
  const missingRef = !orderId;

  useEffect(() => {
    if (!orderId) return undefined;
    let timer;
    const check = async () => {
      try {
        // Public endpoint — works even if the browser lost auth during the Zoho roundtrip.
        const r = await api.get(`/payments/public/status/${orderId}`);
        if (r.data.status === 'paid') {
          setResult(r.data);
          if (isLoggedIn && setCredits) setCredits(r.data.balance);
          // Meta Pixel: Purchase. Fire once per order_id (resilient to refresh / re-poll).
          try {
            const key = `sdg_pixel_purchase_${orderId}`;
            if (sessionStorage.getItem(key) !== '1') {
              sessionStorage.setItem(key, '1');
              trackPixel('Purchase', {
                value: Number(r.data.amount_inr || 0),
                currency: 'INR',
                content_ids: [r.data.pack_id],
                content_type: 'product',
              });
            }
          } catch (_e) { /* noop */ }
        } else if (r.data.status === 'failed') {
          setResult(r.data);
        } else if (attemptsRef.current < MAX_ATTEMPTS) {
          attemptsRef.current += 1;
          setAttempts(attemptsRef.current);
          timer = setTimeout(check, POLL_INTERVAL_MS);
        } else {
          setResult(r.data); // gave up — show pending state with retry option
        }
      } catch {
        setError('Could not verify the payment. Your order history has the latest status.');
      }
    };
    check();
    return () => clearTimeout(timer);
  }, [orderId, isLoggedIn, setCredits]);

  // Auto-redirect on success: take the user back to where they were (last thread) or dashboard.
  useEffect(() => {
    if (result?.status !== 'paid') return undefined;
    const lastThread = localStorage.getItem('sdg_last_thread');
    const dest = lastThread ? `/app/thread/${lastThread}` : '/app';
    const t = setTimeout(() => {
      if (isLoggedIn) {
        navigate(dest, { replace: true });
      } else {
        // session lost during Zoho hop — bounce through /auth so they sign in fresh and find their credits waiting
        navigate('/auth', { replace: true });
      }
    }, AUTO_REDIRECT_DELAY_MS);
    return () => clearTimeout(t);
  }, [result, isLoggedIn, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-white border border-hairline/70 rounded-xl p-8 text-center">
        {missingRef && <p data-testid="payment-error" className="text-sm text-muted">Missing order reference.</p>}
        {!missingRef && error && <p data-testid="payment-error" className="text-sm text-muted">{error}</p>}
        {!missingRef && !error && !result && (
          <div data-testid="payment-verifying">
            <Loader2 size={28} strokeWidth={1.5} className="mx-auto animate-spin text-muted" />
            <p className="text-sm text-muted mt-4">Confirming your payment with the bank…</p>
            <p className="text-[11px] text-muted mt-2 font-mono-plex">This can take up to a minute. Please don&apos;t close this tab.</p>
            {attempts > 3 && (
              <p data-testid="payment-attempt" className="text-[11px] text-muted/70 mt-1">Still checking… ({attempts}/{MAX_ATTEMPTS})</p>
            )}
          </div>
        )}
        {result && result.status === 'paid' && (
          <div data-testid="payment-success">
            <CheckCircle2 size={32} strokeWidth={1.5} className="mx-auto text-[hsl(var(--success))]" />
            <h1 className="font-display text-2xl mt-4">You&apos;re all set</h1>
            <p className="text-sm text-muted mt-2">
              <span className="font-mono-plex text-foreground">+{result.credits_added}</span> credits added to <span className="font-mono-plex text-foreground">{result.user_email_masked || 'your account'}</span>.
            </p>
            <p className="text-sm text-muted mt-1">
              New balance: <span data-testid="payment-new-balance" className="font-mono-plex text-foreground">{result.balance}</span>
            </p>
            <p className="text-[11px] text-muted/70 mt-4">{isLoggedIn ? 'Taking you back to your goal…' : 'Sign in to continue from where you left off.'}</p>
            <Button asChild className="mt-5 rounded-xl w-full">
              <Link to={isLoggedIn ? (localStorage.getItem('sdg_last_thread') ? `/app/thread/${localStorage.getItem('sdg_last_thread')}` : '/app') : '/auth'} data-testid="payment-continue-now">
                {isLoggedIn ? 'Continue now' : 'Sign in'}
              </Link>
            </Button>
          </div>
        )}
        {result && result.status === 'failed' && (
          <div data-testid="payment-failed">
            <XCircle size={32} strokeWidth={1.5} className="mx-auto text-[hsl(var(--destructive))]" />
            <h1 className="font-display text-2xl mt-4">Payment didn&apos;t go through</h1>
            <p className="text-sm text-muted mt-2">You weren&apos;t charged. No credits added.</p>
            <Button asChild variant="outline" className="mt-6 rounded-xl w-full">
              <Link to="/app/billing" data-testid="payment-retry">Try again</Link>
            </Button>
          </div>
        )}
        {result && result.status === 'created' && (
          <div data-testid="payment-pending">
            <Loader2 size={28} strokeWidth={1.5} className="mx-auto text-muted" />
            <h1 className="font-display text-2xl mt-4">Still verifying</h1>
            <p className="text-sm text-muted mt-2">The bank is taking longer than usual. Your credits will appear once it confirms — check the billing page in a minute.</p>
            <Button asChild variant="outline" className="mt-6 rounded-xl w-full">
              <Link to="/app/billing" data-testid="payment-check-history">See order history</Link>
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
