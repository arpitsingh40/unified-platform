import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../App';
import { api } from '../lib/api';
import { isSupabaseConfigured, supabase } from '../lib/supabase';
import { askBrain as staticAskBrain, fetchBrainDocuments as staticFetchDocs, uploadBrainDocument as staticUploadDoc, deleteBrainDocument as staticDeleteDoc, getReviewsDue as staticReviewsDue } from '../lib/brain';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from './ui/dialog';
import { toast } from 'sonner';
import {
  Send, Upload, FileText, X, SlidersHorizontal, Loader2,
  CheckCircle2, AlertCircle, Clock, ArrowRight, Target, Sparkles,
} from 'lucide-react';

// Label map for answer/decide/plan result badges.
const MODE_LABEL = { answer: 'Answer', decide: 'Decision', plan: 'Plan' };
// Due-time presets offered when committing an action.
const DUE_OPTIONS = [
  { label: 'Today', hours: 8 },
  { label: '24h', hours: 24 },
  { label: '48h', hours: 48 },
  { label: '3 days', hours: 72 },
  { label: '1 week', hours: 168 },
];
// Generate a unique id for each new brain session.
const newSessionId = () =>
  (typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `s_${Date.now()}_${Math.random().toString(36).slice(2)}`);

// Main company-brain panel: ask questions, commit actions, upload docs.
export default function BrainSection({ compact }) {
  const isWebStatic = typeof window !== 'undefined' && import.meta.env.VITE_TARGET === 'web';
  const { setCredits } = useAuth();
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [actionInput, setActionInput] = useState('');
  const [committed, setCommitted] = useState(null);
  const [decisionStatus, setDecisionStatus] = useState(null);
  const [execBusy, setExecBusy] = useState(false);
  const [sessionId, setSessionId] = useState(() => newSessionId());
  const [dueHours, setDueHours] = useState(48);
  const [dueAt, setDueAt] = useState(null);
  const [showResult, setShowResult] = useState(false);
  const [resultInput, setResultInput] = useState('');
  const [docs, setDocs] = useState([]);
  const [canTrain, setCanTrain] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [trainOpen, setTrainOpen] = useState(false);
  const [instructions, setInstructions] = useState('');
  const [savingRules, setSavingRules] = useState(false);
  const fileRef = useRef(null);
  const [reviewsDue, setReviewsDue] = useState([]);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [reviewImpact, setReviewImpact] = useState('');
  const [reviewNote, setReviewNote] = useState('');

  // Fetch decision reviews that are due for closure.
  const loadReviews = useCallback(async () => {
    if (isWebStatic) { try { const r = await staticReviewsDue(); setReviewsDue(r.due || []); } catch {} return; }
    try { const r = await api.get('/brain/reviews/due'); setReviewsDue(r.data.due || []); } catch (_e) { /* noop */ }
  }, []);

  // Record a real-world outcome for a committed decision.
  const submitReview = useCallback(async (id, outcome) => {
    if (reviewBusy) return;
    setReviewBusy(true);
    try {
      const body = { outcome };
      if (reviewNote.trim()) body.actual = reviewNote.trim();
      const imp = parseInt(reviewImpact, 10);
      if (!Number.isNaN(imp)) body.impact_inr = imp;
      await api.post(`/brain/decisions/${id}/review`, body);
      toast.success('Outcome recorded.');
      setReviewImpact(''); setReviewNote('');
      loadReviews();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Could not record the outcome.'); }
    finally { setReviewBusy(false); }
  }, [reviewBusy, reviewNote, reviewImpact, loadReviews]);

  // Fetch uploaded documents and current brain settings — static mode uses localStorage+Supabase
  const loadDocs = useCallback(async () => {
    if (isWebStatic) { try { const r = await staticFetchDocs(); setDocs(r.docs); setCanTrain(r.can_train); } catch {} return; }
    try { const r = await api.get('/brain/documents'); setDocs(r.data.documents || []); setCanTrain(r.data.can_train !== false); } catch (_e) { /* noop */ }
  }, []);
  useEffect(() => {
    loadDocs();
    if (isWebStatic) return;
    api.get('/brain/settings').then((r) => setInstructions(r.data.instructions || '')).catch(() => {});
  }, [loadDocs]);

  useEffect(() => {
    const seed = sessionStorage.getItem('sdg_workspace_seed');
    if (!seed) return;
    try { const d = JSON.parse(seed); setResult(d); if (d.session_id) setSessionId(d.session_id); setCommitted(null); setDecisionStatus(null); setActionInput(d.next_action || ''); } catch (_e) { /* noop */ }
    sessionStorage.removeItem('sdg_workspace_seed');
  }, []);

  useEffect(() => {
    const hasProcessing = docs.some((d) => d.status === 'processing');
    if (!hasProcessing) return undefined;
    const id = setInterval(loadDocs, 4000);
    return () => clearInterval(id);
  }, [docs, loadDocs]);

  // Send a question — static (GH Pages free via brain.js + Supabase) or business-os
  const runAsk = useCallback(async (q, sid) => {
    if (!q.trim() || loading) return;
    setLoading(true);
    setResult(null); setShowResult(false); setResultInput(''); setDueAt(null); setKpiSent({});
    if (isWebStatic) {
      try {
        const r = await staticAskBrain({ question: q.trim(), sessionId: sid });
        setResult({ ...r, session_id: sid, decision_id: r.decisionId || sid, mode: r.mode, found_in_docs: r.found_in_docs });
        setCommitted(null); setDecisionStatus(null);
        setActionInput(r.next_action || '');
        toast.success(r.offline ? 'Answered offline (add Supabase + HF key for live).' : 'Grounded answer ready.');
      } catch (e) { toast.error(e?.message || 'Could not get an answer. Try again.'); }
      finally { setLoading(false); }
      return;
    }
    try {
      const r = await api.post('/brain/ask', { question: q.trim(), session_id: sid });
      setResult(r.data);
      if (r.data.session_id) setSessionId(r.data.session_id);
      setCommitted(null); setDecisionStatus(null);
      setActionInput(r.data.next_action || '');
      if (r.data.credits != null) setCredits(r.data.credits);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Could not get an answer. Try again.'); }
    finally { setLoading(false); }
  }, [loading, setCredits]);

  // Trigger a brain query with the current question.
  const ask = useCallback(() => runAsk(question, sessionId), [runAsk, question, sessionId]);
  // Reset workspace and start a brand-new session.
  const askNew = useCallback(() => {
    setQuestion(''); setResult(null); setSessionId(newSessionId()); setCommitted(null); setDecisionStatus(null);
  }, []);

  // Upload — static via localStorage (+ Supabase bucket when available)
  const uploadFile = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 8 * 1024 * 1024) { toast.error('File too large (max 8 MB).'); return; }
    setUploading(true);
    try {
      if (isWebStatic) {
        const r = await staticUploadDoc(f);
        toast.success(r.stored === 'local' || r.fallback === 'local' ? 'Saved locally (upload grounded answers next).' : 'Uploaded.');
        loadDocs();
      } else {
        const fd = new FormData(); fd.append('file', f);
        await api.post('/brain/documents', fd);
        toast.success('Uploaded. Indexing may take a moment.');
        loadDocs();
      }
    } catch (err) { toast.error(err?.message || err?.response?.data?.detail || 'Upload failed.'); }
    finally { setUploading(false); if (e.target) e.target.value = ''; }
  };

  const deleteDoc = async (docId) => {
    if (isWebStatic) { try { await staticDeleteDoc(docId); loadDocs(); } catch { toast.error('Could not remove document.'); } return; }
    try { await api.delete(`/brain/documents/${docId}`); loadDocs(); } catch (_e) { toast.error('Could not remove document.'); }
  };

  // Persist company rules — static saves to localStorage key
  const saveRules = async () => {
    if (isWebStatic) {
      try { localStorage.setItem('forge_brain_instructions', instructions); toast.success('Rules saved locally.'); setTrainOpen(false); } catch { toast.error('Could not save rules.'); }
      setSavingRules(false); return;
    }
    setSavingRules(true);
    try { await api.put('/brain/settings', { instructions }); toast.success('Company rules saved.'); setTrainOpen(false); } catch (_e) { toast.error('Could not save rules.'); }
    finally { setSavingRules(false); }
  };

  // Lock in the next action with a due time.
  const commitAction = async () => {
    if (!result?.decision_id || !actionInput.trim() || execBusy) return;
    setExecBusy(true);
    try {
      const due = new Date(Date.now() + dueHours * 3600000).toISOString();
      await api.post(`/brain/decisions/${result.decision_id}/commit`, { action: actionInput.trim(), due_at: due });
      setCommitted({ action: actionInput.trim(), due_at: due });
      setDecisionStatus('committed');
      setDueAt(due);
      toast.success('Locked in. Clock is ticking.');
    } catch (e) { toast.error(e?.response?.data?.detail || 'Could not commit the action.'); }
    finally { setExecBusy(false); }
  };

  // Log the final outcome of a committed action.
  const logResult = async (outcome) => {
    if (!result?.decision_id || execBusy) return;
    setExecBusy(true);
    try {
      await api.post(`/brain/decisions/${result.decision_id}/log-result`, { outcome, actual: resultInput.trim() });
      setDecisionStatus(outcome);
      toast.success('Logged.');
    } catch (e) { toast.error(e?.response?.data?.detail || 'Could not log result.'); }
    finally { setExecBusy(false); }
  };

  // Submit on Enter; Shift+Enter stays a newline.
  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); }
  };

  const readyCount = docs.filter((d) => d.status === 'ready').length;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-8 lg:gap-10">
      <section className="min-w-0">
        {!compact && (
          <>
            <h2 className="font-display text-3xl sm:text-4xl tracking-[-0.02em] leading-[1.05]">
              Your company brain.
            </h2>
            <p className="mt-3 text-sm md:text-base text-muted  leading-6 max-w-xl">
              Upload your documents — PDFs, slides, spreadsheets, whatever. The brain reads and indexes them,
              then answers your questions grounded in what your team actually knows.
            </p>
          </>
        )}

        <div className={`${compact ? 'mt-0' : 'mt-6'} rounded-2xl bg-surface border border-hairline/70 shadow-[0_1px_0_rgba(17,24,39,0.06),0_12px_30px_rgba(17,24,39,0.06)] p-3`}>
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder='e.g. "What did we decide about refund windows?" · "Summarise the Q3 plan deck."'
            className="min-h-[96px] border-0 bg-transparent focus-visible:ring-0 resize-none text-[15px] leading-6"
          />
          <div className="flex items-center justify-between px-1 pt-1 gap-2">
            <span className="text-xs text-muted  min-w-0 truncate">
              {readyCount > 0
                ? `${readyCount} document${readyCount > 1 ? 's' : ''} in knowledge`
                : (canTrain ? <span className="text-amber-600 font-medium">Upload documents on the right →</span> : 'Ask anything — backed by your team’s knowledge')}
            </span>
            <div className="flex items-center gap-2 shrink-0">
              {result && (
                <Button variant="ghost" onClick={askNew} disabled={loading || !question.trim()} className="rounded-xl text-muted ">
                  New topic
                </Button>
              )}
              <Button onClick={ask} disabled={loading || !question.trim()} className="rounded-xl active:scale-[0.98]">
                {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} strokeWidth={1.75} />}
                <span className="ml-2">{loading ? 'Thinking' : (result ? 'Continue' : 'Ask')}</span>
              </Button>
            </div>
          </div>
        </div>

        {reviewsDue.length > 0 && (
          <div className="mt-6 rounded-2xl border border-amber-300/70 bg-amber-50/60 p-4 sm:p-5 space-y-3">
            <div className="text-[11px] uppercase tracking-[0.12em] text-amber-800 flex items-center gap-1.5">
              <Clock size={12} /> Time to close the loop
              {reviewsDue.length > 1 ? <span className="normal-case tracking-normal rounded-full bg-amber-100 px-2 py-0.5">{reviewsDue.length - 1} more waiting</span> : null}
            </div>
            <div>
              <p className="text-sm font-medium leading-snug">{reviewsDue[0].question}</p>
              {reviewsDue[0].predicted_outcome?.claim ? (
                <p className="text-xs text-muted  mt-1 leading-snug">
                  Predicted: “{reviewsDue[0].predicted_outcome.claim}” ({reviewsDue[0].predicted_outcome.confidence}% confident). How did it actually go?
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input value={reviewImpact} onChange={(e) => setReviewImpact(e.target.value.replace(/[^0-9-]/g, ''))} placeholder="₹ impact (optional)" inputMode="numeric" className="w-36 rounded-xl border border-hairline/70 bg-background px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring" />
              <input value={reviewNote} onChange={(e) => setReviewNote(e.target.value)} placeholder="What actually happened? (optional)" className="flex-1 min-w-[180px] rounded-xl border border-hairline/70 bg-background px-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring" />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" disabled={reviewBusy} onClick={() => submitReview(reviewsDue[0].id, 'worked')} className="rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white">It worked</Button>
              <Button size="sm" variant="outline" disabled={reviewBusy} onClick={() => submitReview(reviewsDue[0].id, 'partly')} className="rounded-xl">Partly</Button>
              <Button size="sm" variant="outline" disabled={reviewBusy} onClick={() => submitReview(reviewsDue[0].id, 'didnt')} className="rounded-xl text-red-600 border-red-200 hover:bg-red-50">It didn’t</Button>
            </div>
          </div>
        )}

        {loading && (
          <div className="mt-6 text-sm text-muted  flex items-center gap-2" aria-live="polite">
            <Loader2 size={14} className="animate-spin" />
            Reading your documents and working it out…
          </div>
        )}

        {result && !loading && (
          <article className="mt-6 rounded-2xl bg-surface border border-hairline/70 shadow-[0_1px_0_rgba(17,24,39,0.06)] p-5 sm:p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="rounded-lg border-hairline/70 text-foreground">{MODE_LABEL[result.mode] || 'Answer'}</Badge>
              {result.mode === 'answer' && (
                result.found_in_docs
                  ? <span className="flex items-center gap-1 text-xs text-emerald-600"><CheckCircle2 size={13} /> grounded in your documents</span>
                  : <span className="flex items-center gap-1 text-xs text-amber-600"><AlertCircle size={13} /> not found in your documents</span>
              )}
            </div>
            {result.key_takeaway && <p className="text-lg md:text-xl font-display tracking-[-0.01em] leading-snug text-foreground">{result.key_takeaway}</p>}
            {result.situation_read && <p className="text-sm text-muted  italic border-l-2 border-hairline pl-3">{result.situation_read}</p>}
            <p className="text-[15px] md:text-base leading-7 whitespace-pre-wrap text-foreground">{result.answer}</p>
            {result.mode === 'decide' && result.recommendation && (
              <div className="rounded-xl bg-secondary/60 border border-hairline/70 border-l-2 border-l-ring px-4 py-3">
                <div className="text-[11px] uppercase tracking-[0.12em] text-muted  mb-1">Recommended</div>
                <p className="text-[15px] leading-6 font-display tracking-[-0.01em]">{result.recommendation}</p>
              </div>
            )}
            {result.mode === 'plan' && Array.isArray(result.plan) && result.plan.length > 0 && (
              <ol className="space-y-2">
                {result.plan.map((step, i) => (
                  <li key={i} className={`flex gap-3 rounded-xl px-4 py-3 border border-hairline/70 ${i === 0 ? 'bg-secondary/60' : 'bg-secondary/40'}`}>
                    <span className={`shrink-0 font-mono-plex text-xs mt-0.5 ${i === 0 ? 'text-ring' : 'text-muted '}`}>{String(i + 1).padStart(2, '0')}</span>
                    <span className={`text-[15px] leading-6 ${i === 0 ? 'font-medium' : ''}`}>{step}</span>
                  </li>
                ))}
              </ol>
            )}
            {result.next_action && (
              <div className="rounded-xl bg-secondary/60 border border-hairline/70 border-l-2 border-l-ring px-4 py-3">
                <div className="text-[11px] uppercase tracking-[0.12em] text-muted  mb-1 flex items-center gap-1.5">
                  <Target size={12} /> Your next move (24-48h)
                </div>
                <p className="text-[15px] md:text-base leading-6 font-display tracking-[-0.01em]">{result.next_action}</p>
                {result.hook && <p className="text-sm text-muted  mt-1.5">{result.hook}</p>}
              </div>
            )}
          </article>
        )}
      </section>

      <aside className="hidden lg:block space-y-4">
        <div className="sticky top-4 space-y-4">
          <div className="rounded-2xl border border-hairline/70 bg-surface/60 p-5">
            <div className="text-[11px] uppercase tracking-[0.12em] text-muted  mb-3 flex items-center gap-1.5">
              <FileText size={12} /> Knowledge
              <button onClick={() => setTrainOpen(true)} className="ml-auto text-muted  hover:text-foreground" title="Set company rules"><SlidersHorizontal size={13} /></button>
            </div>
            {canTrain && (
              <>
                <label className="flex items-center justify-center gap-2 rounded-xl border-2 border-dashed border-hairline/70 p-4 cursor-pointer hover:border-ring/50 transition-colors text-xs text-muted ">
                  {uploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                  {uploading ? 'Uploading…' : 'Upload document'}
                  <input ref={fileRef} type="file" accept=".pdf,.docx,.pptx,.xlsx,.csv,.txt,image/png,image/jpeg" onChange={uploadFile} className="hidden" />
                </label>
                <p className="text-[10px] text-muted  mt-1.5 leading-snug">PDF, Word, PowerPoint, Excel, CSV, text. Max 8 MB per file.</p>
              </>
            )}
            {!canTrain && (
              <p className="text-xs text-muted  leading-snug">This brain is trained by your workspace owner.</p>
            )}
            <div className="mt-3 space-y-1">
              {docs.length === 0 && (
                <p className="text-xs text-muted  text-center py-4">No documents yet.</p>
              )}
              {docs.map((d) => (
                <div key={d.id} className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-secondary/60 group">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText size={13} className="shrink-0 text-muted " />
                    <span className="text-xs truncate">{d.filename}</span>
                    {d.status === 'processing' && <Loader2 size={10} className="animate-spin shrink-0" />}
                    {d.status === 'ready' && <span className="text-[10px] text-emerald-600 shrink-0">ready</span>}
                  </div>
                  {canTrain && (
                    <button onClick={() => deleteDoc(d.id)} className="opacity-0 group-hover:opacity-100 transition-opacity shrink-0"><X size={12} className="text-muted  hover:text-foreground" /></button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {result?.reasoning?.assumptions_detected?.length > 0 && (
            <div className="rounded-2xl border border-hairline/70 bg-surface/60 p-5">
              <div className="text-[11px] uppercase tracking-[0.12em] text-muted  mb-2">Assumptions detected</div>
              <ul className="space-y-1">
                {result.reasoning.assumptions_detected.slice(0, 3).map((a, i) => (
                  <li key={i} className="text-xs text-foreground/85">• {a}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <Dialog open={trainOpen} onOpenChange={setTrainOpen}>
          <DialogContent className="rounded-2xl sm:max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-display text-xl">Train the brain</DialogTitle>
              <DialogDescription className="text-sm text-muted  mt-1">
                Write the rules and priorities the brain must follow on every decision.
              </DialogDescription>
            </DialogHeader>
            <Textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={6} className="text-sm" placeholder="e.g. Always follow our written refund policy. Never approve discounts above 10% without manager sign-off." />
            <DialogFooter>
              <Button variant="outline" onClick={() => setTrainOpen(false)} className="rounded-xl">Cancel</Button>
              <Button onClick={saveRules} disabled={savingRules} className="rounded-xl">{savingRules ? <Loader2 size={14} className="animate-spin mr-2" /> : null}Save rules</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </aside>
    </div>
  );
}
