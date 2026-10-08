import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { api } from '../lib/api';
import { supabase as sb } from '../lib/supabase';
import { TopBar } from '../components/TopBar';
import { SystemHealthBar, SystemHealthDetail, ConnectionPrompt, CapabilityPanel } from '../components/SystemHealth';
import { SalaarBrief } from '../components/SalaarBrief';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import {
  Send, Loader2, Sparkles, ArrowRight, Brain, ChevronDown, ChevronUp, CircleDot,
  Target, Gauge, Flag, CheckCircle2, Circle, AlertTriangle, HelpCircle, Lightbulb, Clock,
  Users, UserPlus, Calendar, Shield, ListChecks, Radar, Scale, Rocket, Activity,
  FlaskConical, Share2, Layers, Wifi,
} from 'lucide-react';

// Rotating landing input placeholders
const PLACEHOLDERS = [
  'The pivot you keep postponing…',
  'The founder you need to let go…',
  'The round you are not sure about…',
  'The customer segment you are ignoring…',
  'The co-founder conversation you keep delaying…',
  'The hire you know you need to make…',
  'The price change you are afraid to test…',
];

const STRING_FIELDS = ['objective', 'why_now', 'whats_at_stake', 'knowledge_level', 'urgency', 'impact', 'timeline'];

// Coerce a model field value to a string
function fieldValue(field, value) {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.filter((v) => String(v).trim()).join(' · ');
  if (typeof value === 'object') {
    return Object.entries(value).map(([k, v]) => `${k}: ${v}`).join(' · ');
  }
  return String(value).trim();
}

// Check whether a model field has content
function isFilled(field, value) {
  return fieldValue(field, value).length > 0;
}

// Render a labeled list block in the direction card
function DirList({ icon: Icon, label, items }) {
  if (!items || !items.length) return null;
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-muted flex items-center gap-1 mb-1">
        <Icon size={12} /> {label}
      </div>
      <ul className="space-y-1">
        {items.map((it, i) => (
          <li key={i} className="text-sm leading-snug text-foreground/90">{it}</li>
        ))}
      </ul>
    </div>
  );
}

// Business OS status strip — shows live org status on dashboard
function OSStatusStrip() {
  const [os, setOs] = useState(null);
  const isWebOs = typeof window !== 'undefined' && import.meta.env.VITE_TARGET === 'web';
  useEffect(() => {
    if (isWebOs) return;
    api.get('/business-os/status').then(r => setOs(r.data)).catch(() => {});
    const id = setInterval(() => {
      api.get('/business-os/status').then(r => setOs(r.data)).catch(() => {});
    }, 60000);
    return () => clearInterval(id);
  }, []);
  if (!os || !os.connected_tools || os.connected_tools.length === 0) return null;
  return (
    <div className="rounded-2xl border border-accent/15 bg-accent/[0.03] px-5 py-3.5 flex flex-wrap items-center gap-3 sm:gap-5">
      <div className="flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
        </span>
        <span className="text-xs font-medium text-text">Your company is running</span>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted">
        {os.agent_count > 0 && <span>{os.agent_count} agents active</span>}
        {os.connected_count > 0 && <span className="hidden sm:inline">{os.connected_count} tools connected</span>}
        {os.approvals?.pending > 0 && (
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 font-medium">
            {os.approvals.pending} pending
          </span>
        )}
      </div>
    </div>
  );
}

// Conversational journey page for shaping direction
export default function JourneyPage() {
  const { user, setCredits } = useAuth();
  const navigate = useNavigate();
  const [journey, setJourney] = useState(null);
  const [loading, setLoading] = useState(true);
  const [objective, setObjective] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [phIdx, setPhIdx] = useState(0);
  const [panelOpen, setPanelOpen] = useState(false);
  const [shaping, setShaping] = useState(false);
  const [refining, setRefining] = useState(false);
  const [approving, setApproving] = useState(false);
  const [refineText, setRefineText] = useState('');
  const [teamStarting, setTeamStarting] = useState(false);
  const [teamSkipping, setTeamSkipping] = useState(false);
  const [teamBuilding, setTeamBuilding] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [resultDrafts, setResultDrafts] = useState({});
  const [sessionId, setSessionId] = useState(null);
  const endRef = useRef(null);

  const isWeb = import.meta.env.VITE_TARGET === 'web' && !!sb;
  // Load an in-progress journey — web: from Supabase (free), desktop/dev: from business-os
  const load = useCallback(async () => {
    if (isWeb) {
      try {
        const { data: { user } } = await sb.auth.getUser();
        if (!user) { setLoading(false); return; }
        const { data: convs } = await sb.from('conversations').select('id, objective, updated_at').eq('user_id', user.id).order('updated_at', { ascending: false }).limit(1);
        const conv = convs?.[0];
        if (conv) {
          const { data: msgs } = await sb.from('messages').select('role, content, created_at').eq('conversation_id', conv.id).order('id', { ascending: true });
          setJourney({ started: true, session_id: conv.id, webConversationId: conv.id, messages: (msgs ?? []).map((m) => ({ role: m.role, text: m.content, at: m.created_at })), model: { objective: conv.objective } });
          setSessionId(conv.id);
        }
      } catch (_e) { /* noop */ } finally { setLoading(false); }
      return;
    }
    try {
      const r = await api.get('/journey');
      if (r.data?.started) {
        setJourney(r.data);
        if (r.data.session_id) setSessionId(r.data.session_id);
      }
    } catch (_e) { /* noop */ } finally { setLoading(false); }
  }, [isWeb]);

  useEffect(() => { load(); }, [load]);

  // rotating placeholder on the landing
  useEffect(() => {
    if (journey?.started) return undefined;
    const id = setInterval(() => setPhIdx((i) => (i + 1) % PLACEHOLDERS.length), 2600);
    return () => clearInterval(id);
  }, [journey?.started]);

  useEffect(() => {
    if (journey?.started) endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [journey?.messages?.length, journey?.has_direction, journey?.milestones?.length, journey?.stage,
      journey?.team?.started, journey?.team?.messages?.length, journey?.team?.plan, busy]);

  const handleError = (e) => {
    const status = e?.response?.status;
    const raw = e?.response?.data;
    const detail = typeof raw === 'string' ? raw : (raw?.detail || raw?.error || raw?.message || '');
    if (status === 401) {
      toast.error(typeof detail === 'string' && detail ? detail : 'Session expired. Please sign in again.');
      return;
    }
    if (status === 402) {
      toast.error('You are out of credits. Top up to keep going.');
    } else {
      // Supabase Edge Function returns {error: "..."} even on 502/500 — surface it
      const msg = typeof detail === 'string' && detail ? detail : (e?.message || '');
      toast.error(msg.slice(0, 280) || 'Your thinking partner could not respond. You were not charged, try again.');
    }
  };

  // Start a new journey — web: Edge Function `chat` (Supabase + DeepSeek, free), else business-os
  const start = useCallback(async () => {
    const obj = objective.trim();
    if (!obj || busy) return;
    setBusy(true);
    if (isWeb) {
      try {
        // optimistic: show user message
        setJourney((prev) => prev ? { ...prev, messages: [...(prev.messages ?? []), { role: 'user', text: obj, at: new Date().toISOString() }] } : { started: true, session_id: null, webConversationId: null, messages: [{ role: 'user', text: obj, at: new Date().toISOString() }], model: { objective: obj } });
        setObjective('');
        const { data, error } = await sb.functions.invoke('chat', { body: { message: obj, objective: obj, conversation_id: journey?.webConversationId ?? undefined } });
        if (error) throw new Error(error.message || 'Edge Function error');
        const reply = data?.reply ?? String(data?.data ?? '');
        const convId = data?.conversation_id ?? journey?.webConversationId ?? null;
        setJourney((prev) => ({ ...(prev ?? { started: true }), session_id: convId, webConversationId: convId, messages: [...(prev?.messages ?? [{ role: 'user', text: obj }]), { role: 'assistant', text: reply, at: new Date().toISOString() }], model: { objective: obj }, started: true }));
        if (convId) setSessionId(convId);
        setPanelOpen(true);
      } catch (e) {
        const detail = e?.message ?? 'Chat failed.';
        if (String(detail).includes('LLM') || String(detail).includes('502')) {
          setJourney((j) => j ? { ...j, messages: [...j.messages, { role: 'assistant', text: `Offline mode (LLM busy — ${String(detail).slice(0, 220)}). Quick start:\n\n• Goal in one sentence\n• Easiest 48h action\n• Download FORGE for Windows for local execution.`, at: new Date().toISOString() }] } : { started: true, messages: [{ role: 'assistant', text: `Offline: ${String(detail).slice(0, 200)} — try again or download FORGE.exe.` }] });
        } else handleError({ response: { status: 0, data: { detail } } });
      } finally { setBusy(false); }
      return;
    }
    try {
      const r = await api.post('/journey/start', { objective: obj });
      setJourney((prev) => (prev ? { ...prev, ...r.data } : r.data));
      if (r.data.session_id) setSessionId(r.data.session_id);
      if (typeof r.data.credits === 'number') setCredits(r.data.credits);
      setPanelOpen(true);
    } catch (e) { handleError(e); } finally { setBusy(false); }
  }, [objective, busy, setCredits, isWeb, journey?.webConversationId]);

  // History for offline resilience (JourneyPage scroll)
  const historyEndRef = useRef(null);
  useEffect(() => { historyEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [journey?.messages]);

  // Send a chat — web: same Edge Function, else business-os
  const send = useCallback(async () => {
    const msg = message.trim();
    if (!msg || busy) return;
    if (isWeb) {
      setBusy(true);
      setJourney((j) => (j ? { ...j, messages: [...j.messages, { role: 'user', text: msg, at: new Date().toISOString() }] } : j));
      setMessage('');
      try {
        const { data, error } = await sb.functions.invoke('chat', { body: { message: msg, conversation_id: journey?.webConversationId ?? sessionId ?? undefined } });
        if (error) throw new Error(error.message || 'Edge Function error');
        const reply = data?.reply ?? '';
        const convId = data?.conversation_id ?? journey?.webConversationId ?? null;
        setJourney((prev) => ({ ...(prev ?? {}), webConversationId: convId, session_id: convId, messages: [...(prev?.messages ?? []), { role: 'assistant', text: reply, at: new Date().toISOString() }] }));
        if (convId) setSessionId(convId);
      } catch (e) {
        handleError({ response: { status: 0, data: { detail: e?.message ?? 'Chat failed' } } });
        setMessage(msg);
      } finally { setBusy(false); }
      return;
    }
    const teamMode = journey?.team?.started && !journey?.team?.plan;
    setBusy(true);
    if (teamMode) {
      setJourney((j) => (j ? { ...j, team: { ...j.team, messages: [...j.team.messages, { role: 'user', text: msg, at: null }] } } : j));
    } else {
      setJourney((j) => (j ? { ...j, messages: [...j.messages, { role: 'user', text: msg, at: null }] } : j));
    }
    setMessage('');
    try {
      const r = await api.post(teamMode ? '/journey/team/message' : '/journey/message', { message: msg, ...(sessionId ? { session_id: sessionId } : {}) });
      setJourney((prev) => (prev ? { ...prev, ...r.data } : r.data));
      if (r.data.session_id) setSessionId(r.data.session_id);
      if (typeof r.data.credits === 'number') setCredits(r.data.credits);
    } catch (e) {
      const detail = e?.response?.data?.detail || e?.message || 'Chat failed.';
      // Surface Edge Function non-2xx (Zen 403/502, HF no credits) with graceful fallback
      if (String(detail).includes('LLM') || e?.response?.status === 502) {
        // Keep the user's message, add a local offline reply so they can continue planning
        setJourney((j) => j ? { ...j, messages: [...j.messages, { role: 'assistant', text: `I'm temporarily offline (LLM busy — ${String(detail).slice(0, 220)}). Here's a lightweight plan to keep going:\n\n• Vision → one sentence: what changes for the user?\n• 48h move → the smallest promise you can keep.\n• Download FORGE for Windows to run locally with your own models.`, at: new Date().toISOString() }] } : j);
        toast.info('LLM is busy — showing offline plan. Download FORGE.exe to run locally.');
      } else {
        handleError(e);
      }
      setMessage(msg);
      api.get('/journey').then((r) => r.data && setJourney(r.data)).catch(() => {});
    } finally { setBusy(false); }
  }, [message, busy, journey, setCredits, sessionId, isWeb]);

  // Submit on Ctrl/Cmd+Enter
  const onKey = (e, fn) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); fn(); }
  };

  // Ask the engine to shape a direction (web GH Pages has no business-os direction — show offline)
  const shapeDirection = useCallback(async () => {
    if (isWeb) { toast.info('Direction shaping runs in the Windows app. Your chat is saved — download FORGE.exe to shape direction & milestones.'); return; }
    setShaping(true);
    try {
      const r = await api.post('/journey/direction');
      setJourney(r.data);
      if (typeof r.data.credits === 'number') setCredits(r.data.credits);
    } catch (e) { handleError(e); } finally { setShaping(false); }
  }, [setCredits, isWeb]);

  // Refine the direction with feedback
  const refineDirection = useCallback(async () => {
    if (isWeb) { toast.info('Refine runs in the Windows app. Download FORGE.exe for direction & milestones.'); return; }
    const fb = refineText.trim();
    if (!fb || refining) return;
    setRefining(true);
    try {
      const r = await api.post('/journey/direction/refine', { feedback: fb });
      setJourney(r.data);
      if (typeof r.data.credits === 'number') setCredits(r.data.credits);
      setRefineText('');
    } catch (e) { handleError(e); } finally { setRefining(false); }
  }, [refineText, refining, setCredits, isWeb]);

  // Approve the direction to build milestones
  const approveDirection = useCallback(async () => {
    if (isWeb) { toast.info('Milestones are built in the Windows app. Download FORGE.exe to continue.'); return; }
    setApproving(true);
    try {
      const r = await api.post('/journey/direction/approve');
      setJourney(r.data);
      if (typeof r.data.credits === 'number') setCredits(r.data.credits);
      window.dispatchEvent(new Event('sdg-journey-changed'));
    } catch (e) { handleError(e); } finally { setApproving(false); }
  }, [setCredits, isWeb]);

  // Advance a milestone through its statuses
  const cycleMilestone = useCallback(async (m) => {
    const next = m.status === 'not_started' ? 'in_progress' : m.status === 'in_progress' ? 'done' : 'not_started';
    try {
      const r = await api.post(`/journey/milestones/${m.id}/status`, { status: next });
      setJourney(r.data);
    } catch (e) { handleError(e); }
  }, []);

  // Start the team setup conversation
  const startTeam = useCallback(async () => {
    setTeamStarting(true);
    try {
      const r = await api.post('/journey/team/start');
      setJourney(r.data);
      window.dispatchEvent(new Event('sdg-journey-changed'));
    } catch (e) { handleError(e); } finally { setTeamStarting(false); }
  }, []);

  // Skip the team setup offer
  const skipTeam = useCallback(async () => {
    setTeamSkipping(true);
    try {
      const r = await api.post('/journey/team/skip');
      setJourney(r.data);
    } catch (e) { handleError(e); } finally { setTeamSkipping(false); }
  }, []);

  // Build the team operating plan
  const buildTeam = useCallback(async () => {
    setTeamBuilding(true);
    try {
      const r = await api.post('/journey/team/build');
      setJourney(r.data);
      if (typeof r.data.credits === 'number') setCredits(r.data.credits);
      window.dispatchEvent(new Event('sdg-journey-changed'));
    } catch (e) { handleError(e); } finally { setTeamBuilding(false); }
  }, [setCredits]);

  // Create and copy a public share link
  const shareDirection = useCallback(async () => {
    setSharing(true);
    try {
      const r = await api.post('/share/direction');
      const url = `${window.location.origin}${r.data.path}`;
      try {
        await navigator.clipboard.writeText(url);
        toast.success('Public link copied. Share your call with other founders.');
      } catch (_e) {
        toast.success(`Your public decision card: ${url}`);
      }
    } catch (e) { handleError(e); } finally { setSharing(false); }
  }, []);

  // Save a milestone outcome
  const saveMilestoneResult = useCallback(async (m) => {
    const text = (resultDrafts[m.id] || '').trim();
    if (!text) return;
    try {
      const r = await api.post(`/journey/milestones/${m.id}/status`, { status: 'done', result: text });
      setJourney(r.data);
      setResultDrafts((d) => ({ ...d, [m.id]: '' }));
      toast.success('Outcome saved. Your engine just got smarter.');
    } catch (e) { handleError(e); }
  }, [resultDrafts]);

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <TopBar />
        <div className="flex-1 max-w-5xl mx-auto w-full px-4 sm:px-6 py-10 space-y-6">
          <div className="flex gap-6 h-[70vh]">
            <div className="flex-1 space-y-4">
              <div className="h-10 w-3/5 animate-pulse rounded-lg bg-primary/10" />
              <div className="h-4 w-full animate-pulse rounded-lg bg-primary/10" />
              <div className="h-4 w-4/5 animate-pulse rounded-lg bg-primary/10" />
              <div className="h-4 w-2/5 animate-pulse rounded-lg bg-primary/10" />
              <div className="h-20 w-full animate-pulse rounded-2xl bg-primary/10 mt-6" />
              <div className="h-20 w-full animate-pulse rounded-2xl bg-primary/10" />
            </div>
            <div className="w-72 space-y-4 hidden lg:block">
              <div className="h-4 w-24 animate-pulse rounded-md bg-primary/10" />
              <div className="h-16 animate-pulse rounded-xl bg-primary/10" />
              <div className="h-16 animate-pulse rounded-xl bg-primary/10" />
              <div className="h-16 animate-pulse rounded-xl bg-primary/10" />
              <div className="h-16 animate-pulse rounded-xl bg-primary/10" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------- LANDING (not started)
  if (!journey?.started) {
    return (
      <div className="min-h-screen flex flex-col bg-background">
        <TopBar />
        <main className="flex-1 flex items-center justify-center px-4 sm:px-6" style={{paddingBottom: 'env(safe-area-inset-bottom, 16px)'}}>
          <div className="w-full max-w-xl mx-auto -mt-10 sm:-mt-16 space-y-8">
            <OSStatusStrip />

            {/* Company status cards — shown when org exists */}
            {user?.org_id && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { icon: Layers, label: 'Organization', value: 'Ready', color: 'text-emerald-600' },
                  { icon: Zap, label: 'Agents', value: '12 initialized', color: 'text-accent' },
                  { icon: Brain, label: 'Knowledge', value: 'Upload docs', color: 'text-muted', onClick: () => navigate('/app/brain') },
                  { icon: Wifi, label: 'Tools', value: 'Connect', color: 'text-muted', onClick: () => navigate('/app/business-os') },
                ].map(c => (
                  <button key={c.label} onClick={c.onClick}
                    className="rounded-xl border border-hairline bg-surface p-3 sm:p-4 text-left hover:border-accent/30 hover:shadow-sm transition-all">
                    <c.icon size={16} strokeWidth={1.5} className={c.color} />
                    <p className="text-[11px] text-muted mt-2 uppercase tracking-wide">{c.label}</p>
                    <p className={`text-sm font-medium mt-0.5 ${c.color}`}>{c.value}</p>
                  </button>
                ))}
              </div>
            )}

            <div className="text-center space-y-5" data-testid="journey-landing">
              <h1 className="font-display text-2xl sm:text-4xl lg:text-5xl text-text tracking-[-0.02em] leading-[1.08]">
                What's on your mind?
              </h1>
              <p className="text-muted text-sm max-w-sm mx-auto">
                Ask anything. Get direction. Your company runs in the background.
              </p>

              {busy ? (
                <div className="flex flex-col items-center py-8" data-testid="journey-generating">
                  <div className="rounded-2xl border border-hairline bg-surface px-6 py-5 w-full max-w-lg text-center shadow-elevation-1">
                    <div className="relative mx-auto w-10 h-10 mb-4">
                      <div className="absolute inset-0 rounded-full border-2 border-accent/20" />
                      <div className="absolute inset-0 rounded-full border-2 border-t-accent animate-spin-slow" />
                    </div>
                    <p className="text-sm font-medium text-text">Building your company model…</p>
                    <p className="text-xs text-muted mt-1.5">This takes about a minute. Every word shapes the response.</p>
                  </div>
                  <div className="mt-5 w-full max-w-lg space-y-2">
                    {[...Array(3)].map((_, i) => (
                      <div key={i} className="h-2.5 rounded-full bg-surface-2 animate-pulse" style={{ width: `${85 - i * 12}%`, animationDelay: `${i * 150}ms` }} />
                    ))}
                  </div>
                </div>
              ) : (
                <div className="mt-2">
                  <div className="rounded-2xl border border-hairline bg-surface shadow-elevation-1 p-1.5">
                    <Textarea
                      data-testid="journey-objective-input"
                      value={objective}
                      onChange={(e) => setObjective(e.target.value)}
                      onKeyDown={(e) => onKey(e, start)}
                      placeholder={PLACEHOLDERS[phIdx]}
                      rows={3}
                      className="text-base sm:text-lg resize-none border-0 focus-visible:ring-0 shadow-none bg-transparent px-4 py-3.5 placeholder:text-muted/50"
                    />
                    <div className="flex items-center justify-between px-3 pb-2">
                      <span className="text-[11px] text-muted/60">
                        {user?.credits ?? 0} credits · Enter to start
                      </span>
                      <Button
                        data-testid="journey-start-btn"
                        onClick={start}
                        disabled={!objective.trim() || busy}
                        size="sm"
                        className="rounded-xl gap-1.5"
                      >
                        Start <ArrowRight size={14} strokeWidth={2} />
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    );
  }

  // ---------------------------------------------------------------- CHAT (started)
  const model = journey.model || {};
  const order = journey.field_order || Object.keys(journey.field_labels || {});
  const labels = journey.field_labels || {};
  const filled = order.filter((f) => isFilled(f, model[f]));
  const empties = order.filter((f) => !isFilled(f, model[f]));
  const conf = journey.confidence ?? 0;
  const reasoning = journey.reasoning || null;
  const team = journey.team || {};
  const teamMode = team.started && !team.plan;
  const showTeamOffer = !!(journey.milestones && journey.milestones.length) && !team.started && !team.offer_dismissed && !team.plan;
  const teamHasAnswer = (team.messages || []).some((m) => m.role === 'user');

  const isWebPanel = typeof window !== 'undefined' && import.meta.env.VITE_TARGET === 'web';
  const Panel = (
    <div className="space-y-5">
      {!isWebPanel ? (
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-muted uppercase tracking-wide">Decision confidence</span>
          <span data-testid="journey-confidence" className="font-mono-plex text-xs text-foreground">{conf}%</span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
          <div className="h-full rounded-full bg-primary transition-all duration-700" style={{ width: `${conf}%` }} />
        </div>
        <div className="text-xs text-muted mt-1.5">{journey.confidence_band}</div>
        {journey.ready_for_direction && !journey.has_direction ? (
          <div className="mt-3 flex items-start gap-2 rounded-xl bg-secondary/70 px-3 py-2 text-xs text-foreground">
            <Sparkles size={13} className="mt-0.5 shrink-0" />
            <span>I have enough to shape an initial direction with you. Keep going, or shape it below.</span>
          </div>
        ) : null}
      </div>
      ) : null}
        {journey.milestones && journey.milestones.length ? (
          <div className="mt-3">
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-muted uppercase tracking-wide flex items-center gap-1"><Flag size={11} /> Plan progress</span>
              <span className="font-mono-plex">{journey.progress_pct}%</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
              <div className="h-full rounded-full bg-emerald-500 transition-all duration-700" style={{ width: `${journey.progress_pct}%` }} />
            </div>
          </div>
        ) : null}
      </div>

      {(journey.hypotheses || []).length ? (
        <div className="pt-3 border-t border-hairline/60 space-y-2" data-testid="journey-hypotheses-panel">
          <div className="text-[11px] uppercase tracking-wide text-muted flex items-center gap-1">
            <FlaskConical size={11} /> Current hypotheses
          </div>
          <div className="space-y-2">
            {journey.hypotheses.map((h) => {
              const ruledOut = h.status === 'ruled_out';
              const leading = h.status === 'leading';
              const evid = [
                ...(h.evidence_for || []).map((e) => `+ ${e}`),
                ...(h.evidence_against || []).map((e) => `- ${e}`),
              ].join('\n');
              return (
                <div key={h.id} data-testid={`hypothesis-${h.id}`} title={evid}>
                  <div className="flex items-start justify-between gap-2 text-[11px]">
                    <span className={`leading-snug ${ruledOut ? 'line-through text-muted/60' : leading ? 'font-semibold text-foreground' : 'text-foreground/85'}`}>
                      {h.statement}
                    </span>
                    <span className={`font-mono-plex shrink-0 ${ruledOut ? 'text-muted/60' : leading ? 'text-emerald-600 font-semibold' : 'text-muted'}`}>
                      {h.probability}%
                    </span>
                  </div>
                  <div className="h-1 w-full rounded-full bg-muted overflow-hidden mt-0.5">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${ruledOut ? 'bg-muted-foreground/30' : leading ? 'bg-emerald-500' : 'bg-primary/60'}`}
                      style={{ width: `${h.probability}%` }}
                    />
                  </div>
                  {ruledOut ? (
                    <div className="text-[10px] uppercase tracking-wide text-muted/60 mt-0.5">ruled out</div>
                  ) : null}
                </div>
              );
            })}
          </div>
          <p className="text-[10px] text-muted leading-snug">
            Each answer you give moves these probabilities. Hover one to see the evidence.
          </p>
        </div>
      ) : null}

      {reasoning ? (
        <div className="pt-3 border-t border-hairline/60 space-y-3" data-testid="journey-reasoning-panel">
          <div className="text-[11px] uppercase tracking-wide text-muted flex items-center gap-1">
            <Radar size={11} /> How clearly I see each dimension
          </div>
          <div className="space-y-1.5">
            {(reasoning.dim_order || []).map((d) => {
              const u = reasoning.uncertainty?.[d];
              if (!u) return null;
              const biggest = reasoning.biggest_uncertainty === d;
              const clarity = 100 - (u.score ?? 100);
              return (
                <div key={d} data-testid={`reasoning-dim-${d}`} title={u.note || ''}>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className={biggest ? 'font-semibold text-foreground' : 'text-muted'}>
                      {reasoning.dim_labels?.[d] || d}{biggest ? ' · probing this' : ''}
                    </span>
                    <span className="font-mono-plex text-muted">{clarity}%</span>
                  </div>
                  <div className="h-1 w-full rounded-full bg-muted overflow-hidden mt-0.5">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${biggest ? 'bg-amber-500' : 'bg-primary/60'}`}
                      style={{ width: `${clarity}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          {reasoning.question_rationale ? (
            <div className="rounded-xl bg-secondary/60 px-3 py-2 text-xs leading-snug" data-testid="reasoning-rationale">
              <span className="text-[10px] uppercase tracking-wide text-muted block mb-0.5">
                {reasoning.sufficient ? 'Why I stopped asking' : 'Why I asked that'}
              </span>
              {reasoning.sufficient && reasoning.sufficiency_reason ? reasoning.sufficiency_reason : reasoning.question_rationale}
            </div>
          ) : null}
          {reasoning.assumptions_detected?.length ? (
            <div data-testid="reasoning-assumptions">
              <div className="text-[10px] uppercase tracking-wide text-muted mb-1">Assumptions I am hearing</div>
              <ul className="space-y-1">
                {reasoning.assumptions_detected.map((a, i) => (
                  <li key={i} className="text-xs text-foreground/85 leading-snug flex items-start gap-1.5">
                    <AlertTriangle size={11} className="mt-0.5 shrink-0 text-amber-500" />{a}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-1.5">
            {reasoning.decision_type && reasoning.decision_type !== 'other' ? (
              <span className="text-[10px] uppercase tracking-wide rounded-full bg-secondary px-2 py-0.5">
                {reasoning.decision_type} problem
              </span>
            ) : null}
            {reasoning.reversible === false ? (
              <span className="text-[10px] uppercase tracking-wide rounded-full bg-red-100 text-red-700 px-2 py-0.5">one-way door</span>
            ) : reasoning.reversible === true ? (
              <span className="text-[10px] uppercase tracking-wide rounded-full bg-emerald-100 text-emerald-700 px-2 py-0.5">reversible</span>
            ) : null}
            {(reasoning.expert_lenses || []).map((l, i) => (
              <span key={i} className="text-[10px] rounded-full border border-hairline/70 px-2 py-0.5 text-muted">{l}</span>
            ))}
          </div>
        </div>
      ) : null}

      <div className="space-y-3 pt-3 border-t border-hairline/60">
        <div className="text-[11px] uppercase tracking-wide text-muted">What I understand</div>
        {filled.map((f) => (
          <div key={f} data-testid={`journey-field-${f}`}>
            <div className="text-[11px] uppercase tracking-wide text-muted">{labels[f] || f}</div>
            <div className="text-sm text-foreground leading-snug mt-0.5">{fieldValue(f, model[f])}</div>
          </div>
        ))}
        {filled.length === 0 ? (
          <div className="text-sm text-muted">Building your picture as we talk…</div>
        ) : null}
      </div>

      {empties.length ? (
        <div className="pt-2 border-t border-hairline/60">
          <div className="text-[11px] uppercase tracking-wide text-muted mb-2">Still exploring</div>
          <div className="flex flex-wrap gap-1.5">
            {empties.map((f) => (
              <span key={f} className="inline-flex items-center gap-1 text-[11px] text-muted rounded-full border border-dashed border-hairline/70 px-2 py-0.5">
                <CircleDot size={10} strokeWidth={2} className="opacity-50" /> {labels[f] || f}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );

  return (
    <div className="h-dvh flex flex-col">
      <TopBar />
      <SalaarBrief />
      {journey?.started && <SystemHealthBar journey={journey} />}
      {journey?.started && <SystemHealthDetail journey={journey} />}
      {journey?.system_health?.at_risk?.length > 0 && (
        <ConnectionPrompt func={journey.system_health.at_risk[0].function} />
      )}
      <main className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pb-4 overflow-hidden flex flex-col">
        <div className={`flex-1 grid gap-6 overflow-hidden min-h-0 ${panelOpen ? 'grid-cols-1 lg:grid-cols-[1fr_300px]' : 'grid-cols-1'}`}>
        <section className="flex flex-col min-h-0" data-testid="journey-chat">
          <div className="flex-1 overflow-y-auto space-y-5 py-4">
            {journey.messages.map((m, i) => (
              m.role === 'assistant' ? (
                <div key={i} className="flex gap-3 items-start" data-testid="journey-msg-assistant">
                  <span className="mt-0.5 inline-flex items-center justify-center w-7 h-7 rounded-lg bg-primary text-primary-foreground shrink-0">
                    <Brain size={15} strokeWidth={1.75} />
                  </span>
                  <div className="flex flex-col gap-2 max-w-[44rem]">
                    <div className="rounded-2xl rounded-tl-sm bg-surface border border-hairline/70 px-4 py-3 text-[15px] leading-relaxed whitespace-pre-wrap">
                      {m.text}
                    </div>
                    {/* first-turn "Why I asked" card */}
                    {i === 0 && journey.reasoning?.question_rationale && (
                      <div className="rounded-xl bg-secondary/60 border border-hairline/60 px-3.5 py-2.5 text-xs leading-snug" data-testid="first-turn-rationale">
                        <span className="text-[10px] uppercase tracking-wide text-muted block mb-0.5">Why I asked that</span>
                        {journey.reasoning.question_rationale}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div key={i} className="flex justify-end" data-testid="journey-msg-user">
                  <div className="rounded-2xl rounded-tr-sm bg-secondary px-4 py-3 text-[15px] leading-relaxed whitespace-pre-wrap max-w-[40rem]">
                    {m.text}
                  </div>
                </div>
              )
            ))}
            {busy && !teamMode ? (
              <div className="flex gap-3 items-center text-muted" data-testid="journey-thinking">
                <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-primary/80 text-primary-foreground shrink-0">
                  <Brain size={15} strokeWidth={1.75} />
                </span>
                <Loader2 className="animate-spin" size={16} /> <span className="text-sm">Thinking…</span>
              </div>
            ) : null}

            {/* Shape-direction CTA */}
            {journey.ready_for_direction && !journey.has_direction ? (
              <div className="rounded-2xl border border-primary/30 bg-secondary/50 p-4 flex items-center justify-between gap-3" data-testid="shape-direction-cta">
                <div className="flex items-start gap-2 text-sm">
                  <Sparkles size={16} className="mt-0.5 shrink-0 text-primary" />
                  <span>I have enough to shape an initial direction with you.</span>
                </div>
                <Button data-testid="shape-direction-btn" onClick={shapeDirection} disabled={shaping} className="rounded-full shrink-0">
                  {shaping ? <Loader2 className="animate-spin mr-2" size={15} /> : <Target size={15} className="mr-2" />}
                  {shaping ? 'Shaping' : 'Shape it'}
                </Button>
              </div>
            ) : null}

            {/* Initial Direction card */}
            {journey.direction ? (
              <div className="rounded-2xl border border-hairline/70 bg-surface p-5 space-y-4" data-testid="direction-card">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium uppercase tracking-wide text-muted flex items-center gap-1.5">
                    <Target size={13} /> Decision package
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 text-xs rounded-full bg-secondary px-2.5 py-1" title="A rough estimate, not a promise" data-testid="direction-probability">
                      <Gauge size={12} /> ~{journey.direction.success_probability}% odds
                    </span>
                    <Button size="sm" variant="outline" className="rounded-full h-7 px-2.5 text-xs" onClick={shareDirection} disabled={sharing} data-testid="share-direction-btn" title="Create a public decision card and copy the link">
                      {sharing ? <Loader2 className="animate-spin" size={12} /> : <Share2 size={12} />}
                      <span className="ml-1">{sharing ? 'Sharing' : 'Share'}</span>
                    </Button>
                  </div>
                </div>
                {journey.direction.decision ? (
                  <div className="rounded-xl bg-primary/5 border border-primary/20 px-3.5 py-2.5" data-testid="direction-decision">
                    <span className="text-[11px] uppercase tracking-wide text-muted block">The call</span>
                    <div className="text-[15px] font-medium leading-snug mt-0.5">{journey.direction.decision}</div>
                  </div>
                ) : null}
                <div>
                  <div className="font-display text-lg leading-snug">{journey.direction.goal}</div>
                  {journey.direction.probability_rationale ? (
                    <div className="text-xs text-muted mt-1">{journey.direction.probability_rationale}</div>
                  ) : null}
                </div>
                {journey.direction.highest_leverage ? (
                  <div className="flex items-start gap-2 rounded-xl bg-secondary/60 px-3 py-2.5 text-sm">
                    <Lightbulb size={15} className="mt-0.5 shrink-0 text-primary" />
                    <div>
                      <span className="text-[11px] uppercase tracking-wide text-muted block">Highest leverage</span>
                      {journey.direction.highest_leverage}
                    </div>
                  </div>
                ) : null}
                <div className="grid sm:grid-cols-3 gap-4">
                  <DirList icon={Flag} label="Blockers" items={journey.direction.blockers} />
                  <DirList icon={AlertTriangle} label="Risks" items={journey.direction.risks} />
                  <DirList icon={HelpCircle} label="Missing info" items={journey.direction.missing_info} />
                </div>
                {journey.direction.trade_offs?.length ? (
                  <div className="pt-3 border-t border-hairline/60" data-testid="direction-tradeoffs">
                    <div className="text-[11px] uppercase tracking-wide text-muted flex items-center gap-1 mb-1.5">
                      <Scale size={12} /> Trade-offs you are accepting
                    </div>
                    <ul className="space-y-1">
                      {journey.direction.trade_offs.map((t, i) => (
                        <li key={i} className="text-sm leading-snug text-foreground/90">{t}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {journey.direction.first_moves?.length ? (
                  <div data-testid="direction-first-moves">
                    <div className="text-[11px] uppercase tracking-wide text-muted flex items-center gap-1 mb-1.5">
                      <Rocket size={12} /> First moves
                    </div>
                    <ol className="space-y-1">
                      {journey.direction.first_moves.map((t, i) => (
                        <li key={i} className="text-sm leading-snug text-foreground/90">{i + 1}. {t}</li>
                      ))}
                    </ol>
                  </div>
                ) : null}
                {journey.direction.learning_loop && (journey.direction.learning_loop.signals?.length || journey.direction.learning_loop.assumptions_to_test?.length) ? (
                  <div className="grid sm:grid-cols-2 gap-4 pt-3 border-t border-hairline/60" data-testid="direction-learning-loop">
                    <DirList icon={Activity} label="Signals to watch" items={journey.direction.learning_loop.signals} />
                    <DirList icon={FlaskConical} label="Assumptions to test" items={journey.direction.learning_loop.assumptions_to_test} />
                  </div>
                ) : null}
                {journey.stage === 'refine' && !journey.milestones.length ? (
                  <div className="pt-3 border-t border-hairline/60 space-y-2.5" data-testid="direction-refine">
                    <div className="text-xs text-muted">Does this represent your business? Refine it, or approve to lock measurable milestones.</div>
                    <Textarea
                      data-testid="refine-input"
                      value={refineText}
                      onChange={(e) => setRefineText(e.target.value)}
                      rows={2}
                      placeholder="Tell me what's off, e.g. 'margins are tighter than that' or 'I can't hire yet'…"
                      className="resize-none rounded-xl text-sm"
                    />
                    <div className="flex flex-wrap items-center gap-2">
                      <Button variant="outline" data-testid="refine-btn" onClick={refineDirection} disabled={!refineText.trim() || refining} className="rounded-full">
                        {refining ? <Loader2 className="animate-spin mr-2" size={15} /> : null}{refining ? 'Refining' : 'Refine'}
                      </Button>
                      <Button data-testid="approve-btn" onClick={approveDirection} disabled={approving} className="rounded-full">
                        {approving ? <Loader2 className="animate-spin mr-2" size={15} /> : <CheckCircle2 size={15} className="mr-2" />}
                        {approving ? 'Building' : 'Approve & build milestones'}
                      </Button>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}

            {/* Milestones tracker */}
            {journey.milestones && journey.milestones.length ? (
              <div className="rounded-2xl border border-hairline/70 bg-surface p-5 space-y-4" data-testid="milestones-card">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium uppercase tracking-wide text-muted flex items-center gap-1.5">
                    <Flag size={13} /> Milestones
                  </span>
                  <span className="font-mono-plex text-xs" data-testid="milestones-progress">{journey.progress_pct}% done</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                  <div className="h-full rounded-full bg-emerald-500 transition-all duration-700" style={{ width: `${journey.progress_pct}%` }} />
                </div>
                <ol className="space-y-2.5">
                  {journey.milestones.map((m) => (
                    <li key={m.id} data-testid="milestone-row" className="flex items-start gap-3 rounded-xl border border-hairline/60 px-3 py-2.5">
                      <button onClick={() => cycleMilestone(m)} data-testid={`milestone-status-${m.order}`} className="mt-0.5 shrink-0" title="Click to update status">
                        {m.status === 'done'
                          ? <CheckCircle2 size={18} className="text-emerald-600" />
                          : m.status === 'in_progress'
                            ? <CircleDot size={18} className="text-amber-500" />
                            : <Circle size={18} className="text-muted" />}
                      </button>
                      <div className="flex-1 min-w-0">
                        <div className={`text-sm font-medium ${m.status === 'done' ? 'line-through text-muted' : ''}`}>{m.order}. {m.title}</div>
                        {m.success_metric ? <div className="text-xs text-muted mt-0.5">{m.success_metric}</div> : null}
                        <div className="flex items-center gap-2 mt-1.5">
                          {m.target ? <span className="text-[11px] rounded-full bg-secondary px-2 py-0.5">{m.target}</span> : null}
                          {m.deadline ? <span className="text-[11px] text-muted inline-flex items-center gap-1"><Clock size={11} />{m.deadline}</span> : null}
                        </div>
                        {m.status === 'done' && m.result ? (
                          <div className="text-xs text-emerald-700 mt-1.5" data-testid={`milestone-result-${m.order}`}>
                            Outcome: {m.result}
                          </div>
                        ) : null}
                        {m.status === 'done' && !m.result ? (
                          <div className="flex items-center gap-1.5 mt-1.5" data-testid={`milestone-result-input-${m.order}`}>
                            <input
                              data-testid={`milestone-result-field-${m.order}`}
                              value={resultDrafts[m.id] || ''}
                              onChange={(e) => setResultDrafts((d) => ({ ...d, [m.id]: e.target.value }))}
                              placeholder="What actually happened? (feeds your engine)"
                              maxLength={500}
                              className="flex-1 text-xs rounded-lg border border-hairline/70 bg-background px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary/40"
                            />
                            <Button size="sm" variant="outline" className="h-7 rounded-lg text-xs px-2" onClick={() => saveMilestoneResult(m)} disabled={!(resultDrafts[m.id] || '').trim()} data-testid={`milestone-result-save-${m.order}`}>
                              Save
                            </Button>
                          </div>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            ) : null}

            {/* Journey → Thread bridge: start daily check-ins */}
            {journey.milestones && journey.milestones.length > 0 && journey.stage === 'milestones' && (
              <div className="rounded-2xl border border-primary/20 bg-secondary/40 p-5" data-testid="journey-to-thread-bridge">
                <div className="flex items-start gap-3">
                  <Target size={18} className="mt-0.5 text-primary shrink-0" />
                  <div>
                    <div className="font-display text-base">Ready for daily check-ins?</div>
                    <p className="text-sm text-muted mt-0.5 leading-relaxed">
                      Your direction and milestones are set. Now open a thread to get a daily next action, accountability tracking, and progress toward your goal.
                    </p>
                    <Button
                      onClick={() => navigate(`/app/new?title=${encodeURIComponent(journey.objective || '')}&why=${encodeURIComponent('Follow through on my direction: ' + (journey.objective || ''))}`)}
                      className="mt-3 rounded-full"
                      data-testid="journey-to-thread-btn"
                    >
                      <ArrowRight size={15} className="mr-1.5" /> Open daily check-ins
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* Team offer */}
            {showTeamOffer ? (
              <div className="rounded-2xl border border-primary/30 bg-secondary/40 p-5" data-testid="team-offer">
                <div className="flex items-start gap-2 mb-3">
                  <Users size={18} className="mt-0.5 text-primary shrink-0" />
                  <div>
                    <div className="font-display text-base">Would you like to involve your team?</div>
                    <div className="text-sm text-muted mt-0.5">I can turn this plan into a daily, weekly and monthly operating rhythm for the people who will execute it.</div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button data-testid="team-yes-btn" onClick={startTeam} disabled={teamStarting} className="rounded-full">
                    {teamStarting ? <Loader2 className="animate-spin mr-2" size={15} /> : <UserPlus size={15} className="mr-2" />}
                    {teamStarting ? 'Starting' : 'Yes, set up my team'}
                  </Button>
                  <Button data-testid="team-skip-btn" variant="outline" onClick={skipTeam} disabled={teamSkipping} className="rounded-full">
                    {teamSkipping ? <Loader2 className="animate-spin mr-2" size={15} /> : null}No, keep going solo
                  </Button>
                </div>
              </div>
            ) : null}

            {/* Team setup conversation */}
            {team.started && !team.plan ? (
              <div className="space-y-5" data-testid="team-setup">
                <div className="flex items-center gap-2 pt-1">
                  <span className="text-[11px] uppercase tracking-wide text-muted flex items-center gap-1.5"><Users size={13} /> Team setup</span>
                  <span className="text-[11px] text-muted font-mono-plex">{team.confidence}%</span>
                  <div className="flex-1 h-px bg-border/60" />
                </div>
                {team.messages.map((m, i) => (
                  m.role === 'assistant' ? (
                    <div key={i} className="flex gap-3 items-start" data-testid="team-msg-assistant">
                      <span className="mt-0.5 inline-flex items-center justify-center w-7 h-7 rounded-lg bg-primary text-primary-foreground shrink-0"><Brain size={15} strokeWidth={1.75} /></span>
                      <div className="rounded-2xl rounded-tl-sm bg-surface border border-hairline/70 px-4 py-3 text-[15px] leading-relaxed whitespace-pre-wrap max-w-[44rem]">{m.text}</div>
                    </div>
                  ) : (
                    <div key={i} className="flex justify-end" data-testid="team-msg-user">
                      <div className="rounded-2xl rounded-tr-sm bg-secondary px-4 py-3 text-[15px] leading-relaxed whitespace-pre-wrap max-w-[40rem]">{m.text}</div>
                    </div>
                  )
                ))}
                {busy && teamMode ? (
                  <div className="flex gap-3 items-center text-muted" data-testid="team-thinking">
                    <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-primary/80 text-primary-foreground shrink-0"><Brain size={15} strokeWidth={1.75} /></span>
                    <Loader2 className="animate-spin" size={16} /> <span className="text-sm">Thinking…</span>
                  </div>
                ) : null}
              </div>
            ) : null}

            {/* Team operating plan */}
            {team.plan ? (
              <div className="rounded-2xl border border-hairline/70 bg-surface p-5 space-y-4" data-testid="team-plan-card">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium uppercase tracking-wide text-muted flex items-center gap-1.5"><Users size={13} /> Team operating plan</span>
                  <Button size="sm" variant="outline" className="rounded-full h-8" onClick={() => navigate('/app/team')} data-testid="open-team-btn">
                    <UserPlus size={14} className="mr-1.5" /> Invite your team
                  </Button>
                </div>
                <div className="grid sm:grid-cols-3 gap-4">
                  <DirList icon={Calendar} label="Daily" items={team.plan.daily} />
                  <DirList icon={Calendar} label="Weekly" items={team.plan.weekly} />
                  <DirList icon={Calendar} label="Monthly" items={team.plan.monthly} />
                </div>
                {team.plan.responsibilities && team.plan.responsibilities.length ? (
                  <div className="pt-3 border-t border-hairline/60">
                    <div className="text-[11px] uppercase tracking-wide text-muted flex items-center gap-1 mb-1.5"><ListChecks size={12} /> Responsibilities</div>
                    <ul className="space-y-1.5">
                      {team.plan.responsibilities.map((r, i) => (
                        <li key={i} className="text-sm leading-snug">
                          {r.who ? <span className="font-medium">{r.who}</span> : null}{r.who && r.what ? ': ' : ''}<span className="text-foreground/90">{r.what}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <div className="grid sm:grid-cols-3 gap-4 pt-3 border-t border-hairline/60">
                  <DirList icon={ArrowRight} label="Dependencies" items={team.plan.dependencies} />
                  <DirList icon={Shield} label="Escalation" items={team.plan.escalation_rules} />
                  <DirList icon={Gauge} label="Success metrics" items={team.plan.success_metrics} />
                </div>
              </div>
            ) : null}

            <div ref={endRef} />
          </div>

          {/* understanding panel toggle (all sizes) */}
          <button
            onClick={() => setPanelOpen((o) => !o)}
            className="flex items-center justify-between rounded-xl border border-hairline/70 px-3 py-2 text-sm text-muted mb-3 lg:sticky lg:top-0 lg:bg-background/80 lg:backdrop-blur"
            data-testid="journey-panel-toggle"
          >
            <span>Decision confidence · {conf}% · {panelOpen ? 'Hide details' : 'Show details'}</span>
            {panelOpen ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
          </button>
          {panelOpen ? <div className="lg:hidden rounded-2xl border border-hairline/70 bg-surface/60 p-4 mb-3">{Panel}</div> : null}

          {/* low-credit warning */}
          {user && user.credits !== undefined && user.credits < 20 && user.credits > 0 && (
            <div data-testid="journey-low-credit-warning" className="mb-2 flex items-center justify-between gap-2 rounded-xl border border-amber-200 bg-amber-50/60 px-3 py-2">
              <span className="text-xs text-amber-700">{user.credits.toLocaleString()} tokens left — {' '}
                <button onClick={() => navigate('/app/billing')} className="underline font-medium">top up</button> to keep going.
              </span>
            </div>
          )}

          {/* composer */}
          <div className="mt-3">
            <div className="rounded-2xl border border-hairline bg-surface shadow-elevation-1 p-1.5 flex items-end gap-2 transition-shadow focus-within:shadow-elevation-2 focus-within:border-accent/30">
              <Textarea
                data-testid="journey-message-input"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => onKey(e, send)}
                placeholder="Your answer…"
                rows={2}
                className="min-h-[52px] sm:min-h-[56px] max-h-32 resize-none border-0 focus-visible:ring-0 shadow-none bg-transparent text-[15px] px-3 py-3 placeholder:text-muted/40"
              />
              <Button
                data-testid="journey-send-btn"
                onClick={send}
                disabled={!message.trim() || busy}
                size="icon"
                className="rounded-xl h-9 w-9 sm:h-10 sm:w-10 shrink-0 mb-0.5 mr-0.5"
              >
                {busy ? <Loader2 className="animate-spin" size={16} /> : <Send size={16} strokeWidth={2} />}
              </Button>
            </div>
            <p className="text-[11px] text-muted/60 mt-2 text-center">
              {user?.credits ?? 0} credits · Enter to send
            </p>
          </div>
        </section>

          {/* understanding panel (desktop) */}
        {panelOpen ? (
        <aside className="hidden lg:block">
          <div className="sticky top-4 rounded-2xl border border-hairline/70 bg-surface/60 p-5" data-testid="journey-understanding-panel">
            {Panel}
          </div>
        </aside>
        ) : null}
      </div>
      </main>
    </div>
  );
}
