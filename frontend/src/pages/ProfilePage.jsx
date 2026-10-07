import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { TopBar } from '../components/TopBar';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import { Card, CardContent } from '../components/ui/card';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { useAuth } from '../App';
import { Sparkles, Compass, Wallet, Trophy, Mountain, ArrowRight, Lock, Loader2, Send, RotateCcw, Brain, CheckCircle2, UserCog, Building2, User, Mail, ShieldCheck } from 'lucide-react';
import { trackPixel } from '../lib/pixel';

// Baseline questionnaire questions
const QUESTIONS = [
  { key: 'dream', icon: Compass, eyebrow: 'Baseline 1 of 4', title: 'What is the outcome you are actually chasing?', hint: 'Not the generic vision — the concrete result you need to make this worth it.', placeholder: "e.g. Build a calm, profitable studio that clears ₹3L/month." },
  { key: 'capacity', icon: Wallet, eyebrow: 'Baseline 2 of 4', title: 'What is your real capacity right now?', hint: 'Honest hours per week, money you can risk, energy you can spare.', placeholder: "e.g. ~8 hours a week after my day job, ~₹50k I can lose." },
  { key: 'advantage', icon: Trophy, eyebrow: 'Baseline 3 of 4', title: 'What is your real edge?', hint: 'The skill, network, taste, or knowledge most people in your spot do not have.', placeholder: "e.g. 6 years inside the industry, 200+ warm contacts." },
  { key: 'potential', icon: Mountain, eyebrow: 'Baseline 4 of 4', title: 'What does success actually look like?', hint: 'The ceiling you can almost see, but never name.', placeholder: "e.g. The go-to person for D2C brand stories in India." },
];

// Labels for founder profile fields
const PROFILE_FIELDS = {
  personality: 'Personality', working_style: 'How you work', communication_style: 'Communication style',
  decision_style: 'Decision style', risk_appetite: 'Risk appetite', strengths: 'Strengths to lean on',
  blind_spots: 'Blind spots to cover', motivations: 'What drives you', industry_summary: 'Your industry',
};

// Baseline and operating profile page
export default function ProfilePage() {
  const navigate = useNavigate();
  const { setUser, user, setCredits } = useAuth();
  const endRef = useRef(null);

  const [tab, setTab] = useState('baseline');
  const [qStep, setQStep] = useState(0);
  const [answers, setAnswers] = useState({ dream: '', capacity: '', advantage: '', potential: '' });
  const [qBusy, setQBusy] = useState(false);
  const [qCompleted, setQCompleted] = useState(false);
  const [qBonus, setQBonus] = useState(100);

  const [fpLoading, setFpLoading] = useState(true);
  const [fpDenied, setFpDenied] = useState(false);
  const [fpNoOrg, setFpNoOrg] = useState(false);
  const [profile, setProfile] = useState(null);
  const [question, setQuestion] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [fpCount, setFpCount] = useState(0);
  const [fpTarget, setFpTarget] = useState(6);
  const [fpCanFinish, setFpCanFinish] = useState(false);
  const [fpAnswer, setFpAnswer] = useState('');
  const [fpBusy, setFpBusy] = useState(false);

  useEffect(() => {
    api.get('/user/questionnaire').then((r) => {
      setQBonus(r.data?.bonus_credits ?? 100);
      setQCompleted(!!r.data?.completed);
      if (r.data?.answers) setAnswers({ dream: r.data.answers.dream || '', capacity: r.data.answers.capacity || '', advantage: r.data.answers.advantage || '', potential: r.data.answers.potential || '' });
    }).catch(() => {});
  }, []);

  // Load founder profile and interview state
  const loadFp = useCallback(async () => {
    setFpLoading(true);
    try {
      const r = await api.get('/founder/profile');
      const d = r.data;
      setFpTarget(d.interview?.target || 6);
      setFpCount(d.interview?.count || 0);
      setFpCanFinish(!!d.interview?.can_finish);
      setTranscript(d.interview?.transcript || []);
      if (d.has_profile) { setProfile(d.profile); setQuestion(null); }
      else if (d.interview?.status === 'in_progress' && d.interview?.pending_question) { setQuestion(d.interview.pending_question); setProfile(null); }
      else { setQuestion(null); setProfile(null); }
    } catch (e) {
      if (e?.response?.status === 404) setFpNoOrg(true);
      else setFpDenied(true);
    } finally { setFpLoading(false); }
  }, []);

  useEffect(() => { loadFp(); }, [loadFp]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [question, transcript, profile]);

  // Save baseline answers for bonus credits
  const submitQ = async () => {
    if (qBusy) return;
    setQBusy(true);
    try {
      const r = await api.post('/user/questionnaire', answers);
      if (typeof r.data?.credits === 'number' && setCredits) setCredits(r.data.credits);
      if (setUser && user) {
        const next = { ...user, credits: r.data.credits ?? user.credits, questionnaire_completed: true };
        setUser(next);
      }
      if (r.data?.first_completion) { trackPixel('CompleteRegistration', { value: 399, currency: 'INR' }); toast.success(`+${r.data.credits_added} credits dropped in your wallet.`); }
      else { toast.message('Your answers are updated.'); }
      setQCompleted(true);
    } catch (err) { toast.error(err.response?.data?.detail || 'Could not save. Try again.'); }
    finally { setQBusy(false); }
  };

  // Start the founder profile interview
  const fpStart = async () => {
    setFpBusy(true);
    try {
      const r = await api.post('/founder/interview/start');
      setProfile(null); setTranscript([]); setFpCount(0); setFpCanFinish(false);
      setQuestion(r.data.question); setFpTarget(r.data.target);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Could not start.'); }
    finally { setFpBusy(false); }
  };

  // Send an interview answer
  const fpSend = async () => {
    if (fpBusy || !fpAnswer.trim()) return;
    const myQ = question; const myA = fpAnswer.trim();
    setFpBusy(true);
    setTranscript((t) => [...t, { q: myQ, a: myA }]);
    setFpAnswer(''); setQuestion(null);
    try {
      const r = await api.post('/founder/interview/answer', { message: myA });
      setFpCount(r.data.count || 0); setFpTarget(r.data.target || fpTarget);
      setFpCanFinish((r.data.count || 0) >= 2);
      if (r.data.done) { setProfile(r.data.profile); setQuestion(null); toast.success('Your profile is ready.'); }
      else { setQuestion(r.data.question); }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Something went wrong.');
      setQuestion(myQ); setFpAnswer(myA);
      setTranscript((t) => t.slice(0, -1));
    } finally { setFpBusy(false); }
  };

  // Finish the interview early
  const fpFinish = async () => {
    setFpBusy(true);
    try { const r = await api.post('/founder/interview/finish'); setProfile(r.data.profile); setQuestion(null); toast.success('Profile built.'); }
    catch (e) { toast.error(e?.response?.data?.detail || 'Could not finish yet.'); }
    finally { setFpBusy(false); }
  };

  const cq = QUESTIONS[qStep];
  const qVal = answers[cq?.key];
  const missingQ = !qCompleted && cq;

  return (
    <div className="min-h-screen">
      <TopBar title="Your profile" backTo="/app" />
      <main className="max-w-2xl mx-auto px-4 sm:px-6 py-6">
        <div className="flex gap-1 mb-6 p-1 rounded-xl bg-muted/50">
          <button onClick={() => setTab('baseline')} className={`flex-1 text-sm py-2 rounded-lg transition-colors ${tab === 'baseline' ? 'bg-background shadow-sm font-medium' : 'text-muted'}`}>Baseline</button>
          <button onClick={() => setTab('operating')} className={`flex-1 text-sm py-2 rounded-lg transition-colors ${tab === 'operating' ? 'bg-background shadow-sm font-medium' : 'text-muted'}`}>Operating profile</button>
        </div>

        {tab === 'baseline' && (
          <div>
            <div className="mb-6">
              <h1 className="font-display text-2xl">Your baseline</h1>
              <p className="text-sm text-muted mt-1">4 questions so the engine knows your reality. {!qCompleted && `${qBonus} bonus credits when done.`}</p>
            </div>

            {qCompleted ? (
              <Card className="rounded-2xl">
                <CardContent className="p-6 space-y-3">
                  {QUESTIONS.map((q) => (
                    <div key={q.key}><div className="text-xs text-muted">{q.title}</div><div className="text-sm mt-0.5">{answers[q.key] || '(not set)'}</div></div>
                  ))}
                  <Button variant="secondary" size="sm" onClick={() => setQCompleted(false)} className="rounded-xl mt-2">Edit answers</Button>
                </CardContent>
              </Card>
            ) : (
              <Card className="rounded-2xl">
                <CardContent className="p-6">
                  <div className="flex items-center gap-2 mb-4">
                    {QUESTIONS.map((q, i) => (<div key={q.key} className={`h-1 flex-1 rounded-full ${i <= qStep ? 'bg-foreground' : 'bg-foreground/10'}`} />))}
                  </div>
                  <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-accent font-semibold mb-2"><cq.icon size={14} /> {cq.eyebrow}</div>
                  <h2 className="font-display text-xl">{cq.title}</h2>
                  <p className="text-sm text-muted mt-2">{cq.hint}</p>
                  <Textarea value={qVal} onChange={(e) => setAnswers((a) => ({ ...a, [cq.key]: e.target.value }))} placeholder={cq.placeholder} className="rounded-xl mt-4 min-h-[120px]" autoFocus />
                  <div className="flex justify-between mt-4">
                    <button onClick={() => setQStep((s) => Math.max(0, s - 1))} disabled={qStep === 0} className="text-xs text-muted hover:text-foreground disabled:opacity-40">← Back</button>
                    <Button onClick={qStep < 3 ? () => setQStep((s) => s + 1) : submitQ} disabled={!qVal?.trim() || qBusy} className="rounded-xl">
                      {qBusy ? 'Saving...' : qStep < 3 ? 'Next' : `Unlock ${qBonus} credits`} <ArrowRight size={14} className="ml-1.5" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {tab === 'operating' && (
          <div>
            {fpLoading ? (
              <div className="flex items-center gap-2 justify-center text-sm text-muted py-20"><Loader2 className="animate-spin" size={16} /> Loading…</div>
            ) : fpNoOrg || fpDenied ? (
              <div className="text-center py-16">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl border mb-4 text-muted">{fpNoOrg ? <Building2 size={20} /> : <Lock size={20} />}</div>
                <h2 className="font-display text-xl">{fpNoOrg ? 'Create your workspace first' : 'Only the founder sets this up'}</h2>
                <p className="text-sm text-muted mt-2">{fpNoOrg ? 'The operating profile lives on your workspace.' : 'This is for the workspace owner.'}</p>
                <Button className="rounded-xl mt-6" onClick={() => navigate(fpNoOrg ? '/app/team' : '/app')}>{fpNoOrg ? 'Go to Team' : 'Go to app'}</Button>
              </div>
            ) : profile ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2"><UserCog size={16} /><h2 className="font-display text-xl">Your operating profile</h2></div>
                <section className="rounded-2xl border bg-surface p-6">
                  <div className="flex items-center gap-2 text-emerald-600 text-xs mb-2"><CheckCircle2 size={14} /> Profile active</div>
                  <p className="font-display text-lg leading-snug">{profile.summary}</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 mt-5">
                    {Object.entries(PROFILE_FIELDS).map(([k, label]) => profile[k] ? (<div key={k}><div className="text-xs uppercase tracking-wider text-muted">{label}</div><div className="text-sm mt-0.5">{profile[k]}</div></div>) : null)}
                  </div>
                </section>
                <div className="flex gap-2"><Button variant="secondary" onClick={fpStart} disabled={fpBusy} className="rounded-xl"><RotateCcw size={14} className="mr-1.5" /> Start over</Button></div>
              </div>
            ) : question ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2 h-1.5 rounded-full bg-muted overflow-hidden"><div className="h-full bg-primary transition-all" style={{ width: `${Math.min(100, Math.round((fpCount / Math.max(1, fpTarget)) * 100))}%` }} /></div>
                {transcript.map((t, i) => (<div key={i} className="space-y-2"><div className="flex gap-2"><span className="shrink-0 w-7 h-7 rounded-lg bg-accent flex items-center justify-center"><Brain size={14} /></span><div className="rounded-2xl bg-secondary/50 px-4 py-2.5 text-sm">{t.q}</div></div><div className="flex justify-end"><div className="rounded-2xl bg-primary text-primary-foreground px-4 py-2.5 text-sm max-w-[85%]">{t.a}</div></div></div>))}
                <div className="flex gap-2"><span className="shrink-0 w-7 h-7 rounded-lg bg-accent flex items-center justify-center"><Brain size={14} /></span><div className="rounded-2xl bg-secondary/50 px-4 py-2.5 text-sm">{question}</div></div>
                <div ref={endRef} />
                <div className="rounded-2xl border bg-surface p-3 sticky bottom-4 shadow-sm">
                  <Textarea value={fpAnswer} onChange={(e) => setFpAnswer(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) fpSend(); }} placeholder="Answer in your own words…" className="rounded-xl border-0 min-h-[70px] resize-none" />
                  <div className="flex items-center justify-between mt-2">
                    <Button variant="ghost" size="sm" onClick={fpFinish} disabled={fpBusy || !fpCanFinish} className="rounded-lg text-xs">{fpBusy ? <Loader2 className="animate-spin" size={13} /> : 'Finish & build my profile'}</Button>
                    <Button size="sm" onClick={fpSend} disabled={fpBusy || !fpAnswer.trim()} className="rounded-xl">{fpBusy ? <Loader2 className="animate-spin" size={14} /> : <>Send <Send size={13} className="ml-1.5" /></>}</Button>
                  </div>
                </div>
              </div>
            ) : (
              <section className="rounded-2xl border bg-surface p-6 text-center">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-accent mb-4"><Sparkles size={22} /></div>
                <h2 className="font-display text-2xl">A few minutes, once.</h2>
                <p className="text-sm text-muted mt-2 max-w-md mx-auto">The brain learns how you operate, so it never gives generic advice again.</p>
                <Button onClick={fpStart} disabled={fpBusy} className="rounded-xl mt-6">{fpBusy ? <Loader2 className="animate-spin" size={15} /> : <>Start the conversation <ArrowRight size={15} className="ml-1.5" /></>}</Button>
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
