import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight, Target, CheckCircle2, RefreshCw,
  Sparkles, Lock, Mail, User, ArrowLeft,
} from 'lucide-react';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { api, setStoredToken } from '../lib/api';
import { supabase as sb } from '../lib/supabase';
import { useAuth } from '../App';

// Render the app logo mark SVG
const BrandMark = ({ size = 28 }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
    <path d="M22 8.5 A7 7 0 0 0 10 8.5 Q10 13 16 15.5 Q22 18 22 22.5 A7 7 0 0 1 10 22.5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" fill="none" />
    <path d="M9 21 L11 22.7 L9 24.4" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
  </svg>
);

// Marketing pillars shown beside the auth form
const PILLARS = [
  { num: '01', icon: Target, label: 'One goal', sub: 'The thing you keep avoiding.' },
  { num: '02', icon: CheckCircle2, label: 'One action', sub: 'Easiest move for the next 48h.' },
  { num: '03', icon: RefreshCw, label: 'Real progress', sub: 'Kept promises. Not vibes.' },
];

// Sign up and login page for the app
export default function AuthPage() {
  const { login } = useAuth();
  const refCode = new URLSearchParams(window.location.search).get('ref') || '';
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [emailMode, setEmailMode] = useState('signup');
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState({ signup_credits: 100 });
  useEffect(() => { api.get('/config').then(r => setConfig(r.data)).catch(() => {}); }, []);

  const isWeb = import.meta.env.VITE_TARGET === 'web';
  // Submit the signup or login form — web uses Supabase directly (free on GH Pages), desktop/dev uses business-os
  const submitEmail = async (e) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      if (isWeb && sb) {
        if (emailMode === 'signup') {
          const { data, error } = await sb.auth.signUp({ email, password, options: { data: { name } } });
          if (error) throw new Error(error.message);
          if (!data.user) throw new Error('No user returned.');
          // Supabase email confirmation may be on — if session null, ask to check email
          if (!data.session) {
            toast.success('Check your email to confirm your account, then sign in.');
            setEmailMode('login');
            return;
          }
          login({ id: data.user.id, email: data.user.email, name: name || data.user.email, credits: 0, is_admin: false, questionnaire_completed: false });
          toast.success('Welcome to FORGE.');
        } else {
          const { data, error } = await sb.auth.signInWithPassword({ email, password });
          if (error) throw new Error(error.message);
          const u = data.user;
          login({ id: u.id, email: u.email, name: (u.user_metadata?.name || u.email), credits: 0, is_admin: false, questionnaire_completed: false });
        }
      } else if (isWeb && !sb) {
        toast.error('Web auth is not configured yet. Add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY and redeploy, or download the Windows app.');
        return;
      } else {
        const path = emailMode === 'login' ? '/auth/login' : '/auth/signup';
        const payload = emailMode === 'login'
          ? { email, password }
          : { email, password, name, ...(refCode ? { ref: refCode } : {}) };
        const r = await api.post(path, payload);
        if (r.data?.token) setStoredToken(r.data.token);
        login(r.data.user);
        if (r.data.user?.questionnaire_completed === false) {
          try { window.trackPixel?.('Lead', {}); } catch (_) {}
        }
      }
    } catch (err) {
      const msg = err?.message || err?.response?.data?.detail || 'Something went wrong.';
      toast.error(msg);
    } finally { setBusy(false); }
  };

  return (
    <div className="paper min-h-screen bg-background flex flex-col">
      <header className="relative z-10 max-w-5xl mx-auto w-full px-4 sm:px-6 lg:px-8 pt-6">
        <button onClick={() => navigate('/')} className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-text transition-colors">
          <ArrowLeft size={14} /> Back to home
        </button>
      </header>

      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-4xl grid md:grid-cols-2 gap-8 md:gap-16 items-center">
          {/* Left */}
          <div className="hidden md:block">
            <div className="flex items-center gap-2 mb-6">
              <BrandMark size={32} />
              <span className="font-display text-xl text-text">SmartDecigen</span>
            </div>
              <h1 className="font-display text-3xl lg:text-4xl text-text leading-[1.15] tracking-tight">
              Your company.<br />
              <span className="text-accent">Running on autopilot</span>.
            </h1>
            <p className="mt-4 text-sm text-muted leading-relaxed max-w-sm">
              One conversation. One direction. Daily action. Your company starts running itself.
            </p>
            <div className="mt-8 space-y-4">
              {PILLARS.map((p) => {
                const Icon = p.icon;
                return (
                  <div key={p.num} className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0 mt-0.5">
                      <Icon size={14} strokeWidth={1.75} className="text-accent" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-text">{p.label}</p>
                      <p className="text-xs text-muted">{p.sub}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right form card */}
          <div className="w-full max-w-sm mx-auto md:mx-0">
            <div className="md:hidden text-center mb-6">
              <BrandMark size={36} />
              <h1 className="font-display text-2xl text-text mt-3">SmartDecigen</h1>
            </div>

            {refCode && (
              <div className="mb-4 rounded-xl border border-accent/20 bg-accent/5 px-4 py-2.5 text-sm text-muted">
                <Sparkles size={14} className="inline mr-1.5 text-accent" />
                You've been invited. Bonus credits will be applied after signup.
              </div>
            )}

            <div className="rounded-2xl border border-hairline bg-surface p-6 shadow-elevation-1">
              <div className="flex items-center rounded-xl bg-surface-2 p-0.5 mb-5">
                <button
                  onClick={() => setEmailMode('signup')}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors ${emailMode === 'signup' ? 'bg-surface text-text shadow-sm' : 'text-muted hover:text-text'}`}>
                  Start your company
                </button>
                <button
                  onClick={() => setEmailMode('login')}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors ${emailMode === 'login' ? 'bg-surface text-text shadow-sm' : 'text-muted hover:text-text'}`}>
                  Sign in
                </button>
              </div>

              <form onSubmit={submitEmail} className="space-y-3">
                {emailMode === 'signup' && (
                  <div className="relative">
                    <User size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                    <Input
                      placeholder="Your name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="pl-9 rounded-xl h-10 text-sm"
                      required
                    />
                  </div>
                )}
                <div className="relative">
                  <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                  <Input
                    type="email"
                    placeholder="Email address"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="pl-9 rounded-xl h-10 text-sm"
                    required
                  />
                </div>
                <div className="relative">
                  <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                  <Input
                    type="password"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pl-9 rounded-xl h-10 text-sm"
                    minLength={6}
                    required
                  />
                </div>

                <Button type="submit" disabled={busy}
                  className="w-full rounded-xl h-10 text-sm bg-accent hover:bg-accent/90 text-white">
                  {busy ? 'Please wait...' : emailMode === 'signup' ? 'Start your company' : 'Sign in'}
                  {!busy && <ArrowRight size={14} className="ml-1.5" />}
                </Button>
              </form>

              {emailMode === 'login' && (
                <p className="mt-3 text-center">
                  <button type="button" onClick={() => toast.info('Password reset is manual right now. Contact ceo@smartdecigen.com.')}
                    className="text-xs text-muted hover:text-accent transition-colors">
                    Forgot your password?
                  </button>
                </p>
              )}

              {emailMode === 'signup' && (
                <div className="mt-5 pt-4 border-t border-hairline">
                  <p className="text-[11px] text-muted text-center">What happens next</p>
                  <div className="mt-2 space-y-1.5">
                    {['Tell us your vision in one conversation', 'Get a direction with concrete next moves', 'Your autonomous agents start running'].map((s, i) => (
                      <div key={i} className="flex items-center gap-2 text-[11px] text-muted">
                        <span className="w-4 h-4 rounded-full bg-accent/10 text-[9px] flex items-center justify-center text-accent font-medium">{i + 1}</span>
                        {s}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <p className="mt-3 text-center text-[11px] text-muted">
              {emailMode === 'signup'
                ? `${config.signup_credits} free credits · No card · ~30 seconds`
                : "Don't have an account? "}
              {emailMode === 'login' && (
                <button type="button" onClick={() => setEmailMode('signup')}
                  className="text-accent hover:underline">Create account</button>
              )}
            </p>

            <div className="mt-4 flex items-center justify-center gap-4 text-[10px] text-muted">
              <span className="flex items-center gap-1"><Lock size={10} /> Privacy-first</span>
              <span>No spam</span>
              <span>Cancel anytime</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
