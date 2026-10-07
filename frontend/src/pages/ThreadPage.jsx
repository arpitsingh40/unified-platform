import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ChevronDown, ChevronUp, Wand2, Copy, Mail, MessageCircle, Paperclip, X as XIcon,
  ArrowRight, MapPin, Sparkles, CheckCircle2, FileText, ListChecks, Clock, Lightbulb,
} from 'lucide-react';
import { Textarea } from '../components/ui/textarea';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../components/ui/collapsible';
import { ScrollArea } from '../components/ui/scroll-area';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import { TopBar } from '../components/TopBar';
import { api } from '../lib/api';
import { useAuth } from '../App';
import { useTilt3D } from '../hooks/use-3d-tilt';

const ACTION_WINDOW_MS = 48 * 3600 * 1000;
const MAX_ATTACH_BYTES = 8 * 1024 * 1024;
// File types accepted for attachments
const ACCEPTED_TYPES = [
  'image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif',
  'application/pdf', '.pdf',
  '.xlsx', '.xls', '.csv', 'text/csv',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx',
  'text/plain', '.txt', '.md', '.markdown', '.json', '.html', '.htm', '.log',
  '.py', '.js', '.ts', '.tsx', '.jsx', '.yaml', '.yml', '.sql',
].join(',');

// Prebuilt adjustment chips for the next action
const ADJUST_CHIPS = [
  { id: 'no-time', label: 'No time', phrase: "I don't have time for this step as written." },
  { id: 'blocked', label: 'Blocked by someone', phrase: "I'm blocked by someone else on this step." },
  { id: 'not-sure-how', label: 'Not sure how', phrase: "I'm not sure how to actually do this step." },
  { id: 'different-idea', label: 'I have a different idea', phrase: 'I have a different idea for this step.' },
];

// Format a duration as hours and minutes
const fmtRemaining = (ms) => {
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
};
// Format a timestamp as clock time
const fmtTime = (iso) => {
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
  catch { return ''; }
};

// Daily check-in thread conversation page
export default function ThreadPage() {
  const { threadId } = useParams();
  const navigate = useNavigate();
  const { user, setCredits } = useAuth();
  const paneRef = useTilt3D(1.2);
  const [thread, setThread] = useState(null);
  const [reengagement, setReengagement] = useState(null);
  const [actionOverdue, setActionOverdue] = useState(false);
  const [message, setMessage] = useState('');
  const [mode, setMode] = useState('normal');
  const [thinking, setThinking] = useState(false);
  const [assistLoading, setAssistLoading] = useState(false);
  const [nowTick, setNowTick] = useState(() => Date.now());
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [adjustChip, setAdjustChip] = useState(null);
  const [adjustText, setAdjustText] = useState('');
  const [artifactEdit, setArtifactEdit] = useState(null);
  const [attachment, setAttachment] = useState(null);
  const [myTasks, setMyTasks] = useState([]);
  const [thinkingElapsed, setThinkingElapsed] = useState(0);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLimit, setHistoryLimit] = useState(50);
  const fileInputRef = useRef(null);
  const [fieldRefresh, setFieldRefresh] = useState(false);

  // Briefly toggle field refresh flag
  const onFieldRefresh = useCallback(() => {
    setFieldRefresh(true);
    setTimeout(() => setFieldRefresh(false), 300);
  }, []);

  useEffect(() => {
    api.get('/org/tasks/mine').then((r) => setMyTasks(r.data.tasks || [])).catch(() => {});
  }, []);
  useEffect(() => {
    try { localStorage.setItem('sdg_last_thread', threadId); } catch { /* */ }
    api.get(`/threads/${threadId}`).then((r) => {
      setThread(r.data.thread);
      setReengagement(r.data.reengagement_line);
      setActionOverdue(r.data.action_overdue);
    }).catch(() => toast.error('Thread not found.'));
  }, [threadId]);

  useEffect(() => {
    const id = setInterval(() => setNowTick(Date.now()), 30000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!thinking) { setThinkingElapsed(0); return; }
    const started = Date.now();
    const id = setInterval(() => setThinkingElapsed(Date.now() - started), 500);
    return () => clearInterval(id);
  }, [thinking]);

  // Validate and read an attached file
  const pickFile = (file) => {
    if (!file) return;
    if (file.size > MAX_ATTACH_BYTES) {
      toast.error('File is too large. Keep it under 8 MB.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setAttachment({ name: file.name, mime: file.type || '', dataUrl: reader.result });
    reader.onerror = () => toast.error('Could not read that file.');
    reader.readAsDataURL(file);
  };

  // Send a message and sync thread state
  const sendText = useCallback(async (text, adjust = false) => {
    const msg = (text || '').trim();
    if (!msg || thinking) return false;
    setThinking(true);
    try {
      const body = { message: msg, mode: adjust ? 'normal' : mode, adjust };
      if (attachment && !adjust) {
        const idx = (attachment.dataUrl || '').indexOf(',');
        body.attachment_base64 = idx >= 0 ? attachment.dataUrl.slice(idx + 1) : attachment.dataUrl;
        body.attachment_filename = attachment.name;
        body.attachment_mime = attachment.mime;
      }
      const r = await api.post(`/threads/${threadId}/turn`, body);
      setThread(r.data.thread);
      onFieldRefresh();
      setCredits(r.data.credits);
      setMessage('');
      setAttachment(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setReengagement(null);
      setActionOverdue(false);
      if (r.data.had_attachment) {
        toast.success(`Read your file — ${r.data.cost} credit${r.data.cost > 1 ? 's' : ''} (${(r.data.tokens || 0).toLocaleString()} tokens).`);
      }
      return true;
    } catch (err) {
      toast.error(err.response?.status === 402 ? 'Not enough credits for this turn.'
        : err.response?.data?.detail || 'The engine did not respond. Try again.');
      return false;
    } finally {
      setThinking(false);
    }
  }, [thinking, threadId, setCredits, mode, attachment, onFieldRefresh]);

  // Send the current composer message
  const send = useCallback(() => sendText(message), [sendText, message]);

  // Send an adjustment for the next action
  const sendAdjust = useCallback(async () => {
    const chip = ADJUST_CHIPS.find((c) => c.id === adjustChip);
    const extra = adjustText.trim();
    if (!chip && !extra) return;
    const composed = `About the next action you gave me: ${chip ? chip.phrase + ' ' : ''}${extra}`.trim();
    const ok = await sendText(composed, true);
    if (ok) {
      setAdjustOpen(false);
      setAdjustChip(null);
      setAdjustText('');
      toast.success('Step reshaped around your input.');
    }
  }, [adjustChip, adjustText, sendText]);

  // Send on Enter without shift
  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  // Change the thread status
  const setStatus = async (status) => {
    try {
      await api.patch(`/threads/${threadId}/status`, { status });
      setThread((t) => ({ ...t, status }));
      toast.success(`Thread ${status}.`);
    } catch {
      toast.error('Could not update status.');
    }
  };

  const artifact = thread?.current_action_artifact || null;
  const artifactKey = artifact?.generated_at || null;
  const artifactText = (artifactEdit && artifactEdit.key === artifactKey) ? artifactEdit.text : (artifact?.artifact || '');

  // Draft the current action artifact
  const doItForMe = async () => {
    if (assistLoading || thinking) return;
    setAssistLoading(true);
    try {
      const r = await api.post(`/threads/${threadId}/complete-action`);
      setThread((t) => ({ ...t, current_action_artifact: r.data.artifact }));
      setCredits(r.data.credits);
      toast.success(`Ready — ${r.data.cost} credit${r.data.cost > 1 ? 's' : ''} for ${(r.data.artifact.tokens || 0).toLocaleString()} tokens.`);
    } catch (err) {
      toast.error(err.response?.status === 402 ? 'Not enough credits.' : err.response?.data?.detail || 'Could not prepare this. Try again.');
    } finally {
      setAssistLoading(false);
    }
  };

  // Copy the artifact text to clipboard
  const copyArtifact = async () => {
    try {
      await navigator.clipboard.writeText(artifactText);
      toast.success('Copied — paste it where it needs to go.');
    } catch {
      toast.error('Copy failed — select the text and copy manually.');
    }
  };

  const mailtoHref = `mailto:?subject=${encodeURIComponent(artifact?.subject || artifact?.title || '')}&body=${encodeURIComponent(artifactText)}`;
  const waHref = `https://wa.me/?text=${encodeURIComponent(artifactText)}`;

  if (!thread) {
    return (
      <div className="relative z-10 min-h-screen paper">
        <TopBar />
        <main className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
          <div className="rounded-2xl border border-hairline bg-surface shadow-elevation-2 p-8 space-y-4">
            <Skeleton className="h-4 w-3/4 rounded-lg" />
            <Skeleton className="h-4 w-1/2 rounded-lg" />
            <Skeleton className="h-24 rounded-xl" />
          </div>
        </main>
      </div>
    );
  }

  const messages = thread.messages || [];
  const inactive = thread.status !== 'active';
  const deadline = thread.last_turn_at ? new Date(thread.last_turn_at).getTime() + ACTION_WINDOW_MS : null;
  const remainingMs = deadline ? deadline - nowTick : null;
  const windowClosed = remainingMs !== null ? remainingMs <= 0 : actionOverdue;
  const geoCity = thread.user_geo?.city;
  const geoCountry = thread.user_geo?.country;
  const showGeo = geoCity && geoCity !== 'Unknown' && geoCity !== 'Local';
  const hasNextAction = thread.current_next_action && thread.current_next_action !== '(none yet)' && thread.current_next_action !== '';

  return (
    <div className="relative z-10 min-h-screen paper">
      <TopBar />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8 flex flex-col" style={{ minHeight: 'calc(100vh - 64px)' }}>

        {/* Status strip */}
        <div className="flex items-center justify-between mb-5 flex-wrap gap-2">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge data-testid="thread-status-badge" variant="accent" className="rounded-lg text-[11px] font-normal">
              {thread.status}
            </Badge>
            <span className="text-[11px] text-muted">{thread.rolling?.pace_calibration}</span>
            {showGeo && (
              <span data-testid="thread-geo-pill"
                className="inline-flex items-center gap-1 text-[10px] text-muted font-mono-plex">
                <MapPin size={10} strokeWidth={2} /> {geoCity}, {geoCountry}
              </span>
            )}
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" data-testid="thread-status-menu" className="rounded-xl text-xs text-muted">
                Manage <ChevronDown size={14} strokeWidth={1.75} className="ml-1" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="rounded-xl">
              {thread.status !== 'active' && <DropdownMenuItem data-testid="status-activate" onClick={() => setStatus('active')}>Reactivate</DropdownMenuItem>}
              {thread.status === 'active' && <DropdownMenuItem data-testid="status-pause" onClick={() => setStatus('paused')}>Pause</DropdownMenuItem>}
              <DropdownMenuItem data-testid="status-graduate" onClick={() => setStatus('graduated')}>{"Graduate — it's done"}</DropdownMenuItem>
              <DropdownMenuItem data-testid="status-release" onClick={() => setStatus('released')}>Release — let it go</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Situation Pane */}
        <div ref={paneRef} data-testid="situation-pane"
          className="perspective-3d flex-1 flex flex-col rounded-2xl border border-hairline bg-surface shadow-elevation-2 p-5 sm:p-6 lg:p-8 transition-all duration-200">

          {/* Re-engagement line */}
          {reengagement && (
            <div data-testid="reengagement-line" className="mb-5 px-4 py-3 rounded-xl border border-hairline bg-surface-2/50">
              <p className="text-sm text-muted leading-6">{reengagement}</p>
            </div>
          )}

          {/* Pending tasks reminder */}
          {myTasks.length > 0 && !thinking && (
            <div className="mb-5 rounded-xl border border-accent/20 bg-accent-wash/30 px-4 py-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm">
                  <ListChecks size={14} className="text-accent" />
                  <span className="font-medium text-text">You have <span className="tabular-nums">{myTasks.length}</span> task{myTasks.length > 1 ? 's' : ''} this week</span>
                </div>
                <button onClick={() => navigate('/app/my-tasks')}
                  className="text-xs text-accent hover:underline shrink-0">View all</button>
              </div>
              <div className="mt-2 space-y-1">
                {myTasks.slice(0, 3).map((t) => (
                  <div key={t.id} className="flex items-center justify-between gap-2 text-xs">
                    <span className="truncate text-muted">{t.title}</span>
                    <span className={`shrink-0 capitalize ${t.due_at && new Date(t.due_at).getTime() < Date.now() && t.status !== 'done' ? 'text-destructive' : 'text-muted'}`}>
                      {t.status.replace(/_/g, ' ')}
                    </span>
                  </div>
                ))}
                {myTasks.length > 3 && <p className="text-[10px] text-muted">+{myTasks.length - 3} more</p>}
              </div>
            </div>
          )}

          {/* Accountability prompt */}
          {windowClosed && !thinking && !inactive && !reengagement && (
            <div data-testid="accountability-prompt" className="mb-5 rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3">
              <p className="text-sm leading-6 mb-3">The 48-hour window on this action closed. What is the result?</p>
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" data-testid="accountability-done-button"
                  onClick={() => sendText('Done — I did it.')}
                  className="rounded-xl">I did it</Button>
                <Button size="sm" variant="secondary" data-testid="accountability-not-done-button"
                  onClick={() => sendText("I didn't do it yet — something got in the way.")}
                  className="rounded-xl">Not yet</Button>
              </div>
            </div>
          )}

          {/* Thinking state — shimmer overlay */}
          {thinking ? (
            <div data-testid="engine-thinking-state" className="flex-1 space-y-5" aria-live="polite" aria-label="Processing your message">
              <div className="space-y-2">
                <Skeleton className="h-3 w-24 rounded-md" />
                <Skeleton className="h-4 w-full rounded-md" />
                <Skeleton className="h-4 w-3/4 rounded-md" />
              </div>
              <Separator />
              <div className="space-y-2">
                <Skeleton className="h-3 w-20 rounded-md" />
                <Skeleton className="h-4 w-2/3 rounded-md" />
              </div>
              <Separator />
              <div className="rounded-2xl bg-surface-2/60 h-32 flex items-center justify-center">
                <div className="flex items-center gap-2">
                  <Clock size={14} strokeWidth={1.75} className="text-muted" />
                  <span className="text-sm text-muted italic">Processing&hellip; {Math.round(thinkingElapsed / 1000)}s</span>
                </div>
              </div>
            </div>
          ) : (
            <>
              {/* 4 Living Fields */}
              <div className="flex-1 space-y-5" data-refresh={fieldRefresh ? 'true' : 'false'}>

                {/* Current State */}
                {thread.current_mirror && (
                  <section data-testid="situation-current-state">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted mb-1.5">Current state</p>
                    <p className="text-sm md:text-base leading-6 text-text line-clamp-3">{thread.current_mirror}</p>
                  </section>
                )}

                {(thread.current_mirror || thread.current_big_picture) && <Separator />}

                {/* Why This Matters / Big Picture */}
                {thread.current_big_picture && (
                  <section data-testid="situation-big-picture">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted mb-1.5">Why this matters</p>
                    <p className="text-sm leading-6 text-muted italic">{thread.current_big_picture}</p>
                  </section>
                )}

                {hasNextAction && <Separator />}

                {/* Next Action — hero */}
                {hasNextAction && (
                  <section data-testid="situation-next-action" className="hero-callout px-5 py-5 sm:px-6 sm:py-6">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-accent/70 mb-2">Next action</p>
                    <p className="font-display text-xl sm:text-2xl md:text-3xl leading-[1.15] text-text tracking-[-0.02em]">
                      {thread.current_next_action}
                    </p>
                    {thread.current_action_payoff && (
                      <p className="mt-3 text-sm text-muted leading-5">
                        <span className="text-text/60">Payoff: </span>{thread.current_action_payoff}
                      </p>
                    )}
                    <div className="mt-4 flex flex-wrap items-center gap-2" data-testid="action-card-inline">
                      <Button size="sm" data-testid="action-mark-done-button" disabled={thinking || inactive} onClick={() => sendText('Done — I did it.')}
                        className="rounded-xl h-9 px-4 text-xs shadow-elevation-1">
                        <CheckCircle2 size={13} strokeWidth={2} className="mr-1.5" /> I did it
                      </Button>
                      <Button size="sm" variant="secondary" data-testid="action-adjust-button" disabled={thinking || inactive} onClick={() => setAdjustOpen((v) => !v)}
                        className="rounded-xl h-9 px-4 text-xs border border-hairline">
                        Adjust
                      </Button>
                      <Button size="sm" variant="secondary" data-testid="action-draft-button" disabled={assistLoading || thinking || inactive} onClick={doItForMe}
                        className="rounded-xl h-9 px-4 text-xs border border-hairline">
                        <Wand2 size={13} strokeWidth={2} className="mr-1.5" /> {assistLoading ? 'Drafting\u2026' : 'Do it for me'}
                      </Button>
                    </div>
                  </section>
                )}

                {/* Outbox card */}
                {thread.current_outbox && (
                  <div data-testid="outbox-card"
                    className="rounded-xl border border-accent/30 bg-accent-wash/20 px-4 py-3">
                    <div className="flex items-baseline gap-2 mb-1">
                      <Lightbulb size={12} strokeWidth={2} className="text-accent shrink-0 translate-y-0.5" />
                      <p className="text-[11px] uppercase tracking-[0.16em] text-muted">Outside-the-box play</p>
                    </div>
                    <p className="text-sm leading-6 text-text/90">{thread.current_outbox}</p>
                  </div>
                )}

                {/* Adjust panel */}
                {adjustOpen && (
                  <div data-testid="adjust-panel"
                    className="rounded-xl border border-hairline bg-surface-2 px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted mb-2">What is getting in the way?</p>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {ADJUST_CHIPS.map((c) => (
                        <button key={c.id} type="button" data-testid={`adjust-chip-${c.id}`}
                          onClick={() => setAdjustChip((s) => s === c.id ? null : c.id)}
                          className={`px-2.5 py-1 rounded-lg text-[11px] border transition-colors ${adjustChip === c.id ? 'border-accent bg-accent/10' : 'border-hairline bg-surface hover:bg-surface-2'}`}>
                          {c.label}
                        </button>
                      ))}
                    </div>
                    <Textarea data-testid="adjust-text"
                      value={adjustText} onChange={(e) => setAdjustText(e.target.value)}
                      placeholder="Add anything specific (optional)\u2026"
                      className="min-h-[64px] rounded-xl bg-surface border-hairline text-sm" />
                    <div className="mt-2 flex items-center justify-end gap-2">
                      <Button size="sm" variant="secondary" onClick={() => setAdjustOpen(false)}
                        className="rounded-lg h-8 px-3 text-xs border border-hairline">Cancel</Button>
                      <Button size="sm" data-testid="adjust-send-button" onClick={sendAdjust}
                        disabled={!adjustChip && !adjustText.trim()}
                        className="rounded-lg h-8 px-3 text-xs">Reshape it</Button>
                    </div>
                  </div>
                )}

                {/* Artifact / Workbench */}
                {artifact && (
                  <div data-testid="workbench-panel"
                    className="rounded-xl border border-hairline bg-surface-2 px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted mb-2 flex items-center gap-1.5">
                      <Sparkles size={12} strokeWidth={2} className="text-accent" /> Ready to ship
                      {artifact.subject && <span className="text-text/85 normal-case tracking-normal ml-2">{artifact.subject}</span>}
                    </p>
                    <p className="text-sm leading-6 whitespace-pre-line">{artifactText}</p>
                    {artifact.handoff && (
                      <p className="mt-2 text-xs italic text-muted border-l-2 border-accent/40 pl-3 leading-5">{artifact.handoff}</p>
                    )}
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Button size="sm" variant="secondary" data-testid="workbench-copy" onClick={copyArtifact}
                        className="rounded-lg h-8 px-3 text-xs border border-hairline">
                        <Copy size={12} strokeWidth={2} className="mr-1.5" /> Copy
                      </Button>
                      {(artifact.channel === 'email' || artifact.subject) && (
                        <Button size="sm" variant="secondary" asChild className="rounded-lg h-8 px-3 text-xs border border-hairline">
                          <a data-testid="workbench-mailto" href={mailtoHref}>
                            <Mail size={12} strokeWidth={2} className="mr-1.5" /> Email
                          </a>
                        </Button>
                      )}
                      {artifact.channel === 'whatsapp' && (
                        <Button size="sm" variant="secondary" asChild className="rounded-lg h-8 px-3 text-xs border border-hairline">
                          <a data-testid="workbench-whatsapp" href={waHref} target="_blank" rel="noreferrer">
                            <MessageCircle size={12} strokeWidth={2} className="mr-1.5" /> WhatsApp
                          </a>
                        </Button>
                      )}
                      <Button size="sm" data-testid="workbench-shipped-button" onClick={() => sendText('Done — I shipped it.')} disabled={thinking}
                        className="rounded-lg h-8 px-3 text-xs ml-auto">Shipped</Button>
                    </div>
                  </div>
                )}

                {/* Open Question */}
                {thread.current_open_question && thread.current_open_question !== '(none yet)' && (
                  <section data-testid="situation-open-question">
                    <p className="text-[11px] uppercase tracking-[0.16em] text-muted mb-1.5">Open question</p>
                    <p className="text-sm leading-6 text-text border-l-2 border-accent/50 pl-3">
                      {thread.current_open_question}
                    </p>
                  </section>
                )}

                {/* Empty state */}
                {messages.length === 0 && !thread.current_mirror && (
                  <p data-testid="empty-chat-hint" className="text-center text-sm text-muted py-8">
                    Start typing below. The engine will read first, then ask one thing at a time.
                  </p>
                )}
              </div>

              {/* Divider before composer */}
              <Separator className="my-3" />

              {/* Composer */}
              <div>
                <Textarea data-testid="composer-textarea"
                  value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={onKeyDown}
                  disabled={thinking || inactive}
                  placeholder={inactive ? `This thread is ${thread.status}. Reactivate it to continue.` : 'Say where things actually are. Attach a file if it helps. Enter to send \u00B7 Shift+Enter for a new line.'}
                  className="min-h-[80px] sm:min-h-[120px] rounded-xl bg-surface border-hairline text-[15px] leading-6 focus-visible:ring-2 focus-visible:ring-accent" />
                {attachment && (
                  <div data-testid="attachment-preview"
                    className="mt-2 flex items-center justify-between gap-3 px-3 py-2 rounded-xl bg-surface-2 border border-hairline">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText size={13} strokeWidth={1.75} className="text-muted shrink-0" />
                      <span className="text-xs truncate text-text/85">{attachment.name}</span>
                      <span className="text-[10px] text-muted shrink-0 font-mono-plex">
                        {(attachment.mime || '').split('/')[1]?.toUpperCase() || 'FILE'}
                      </span>
                    </div>
                    <button type="button" data-testid="attachment-clear"
                      onClick={() => { setAttachment(null); if (fileInputRef.current) fileInputRef.current.value = ''; }}
                      className="text-muted hover:text-text p-1 -m-1 rounded" aria-label="Remove attachment">
                      <XIcon size={13} strokeWidth={2} />
                    </button>
                  </div>
                )}
                <input ref={fileInputRef} type="file" data-testid="attachment-file-input"
                  className="hidden" accept={ACCEPTED_TYPES}
                  onChange={(e) => pickFile(e.target.files?.[0])} />
                <div className="flex items-center justify-between mt-2 gap-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <button type="button" data-testid="attachment-button"
                      onClick={() => fileInputRef.current?.click()} disabled={thinking || inactive}
                      title="Attach file, PDF, doc, sheet, image"
                      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-hairline bg-surface text-[11px] text-muted hover:text-text transition-colors disabled:opacity-50">
                      <Paperclip size={12} strokeWidth={1.75} />
                      {attachment ? 'Replace' : 'Attach'}
                    </button>
                    <div data-testid="mode-toggle"
                      className="flex items-center rounded-xl border border-hairline bg-surface p-0.5">
                      <button type="button" data-testid="mode-normal-button" onClick={() => setMode('normal')} disabled={thinking}
                        className={`px-3 py-1.5 sm:px-2.5 sm:py-1 rounded-lg text-[11px] transition-colors ${mode === 'normal' ? 'bg-accent-wash text-text' : 'text-muted hover:text-text'}`}>Normal</button>
                      <button type="button" data-testid="mode-ultra-button" onClick={() => setMode('ultra')} disabled={thinking}
                        className={`px-3 py-1.5 sm:px-2.5 sm:py-1 rounded-lg text-[11px] transition-colors ${mode === 'ultra' ? 'bg-accent-wash text-text' : 'text-muted hover:text-text'}`}>Ultra thinking</button>
                    </div>
                  </div>
                  <Button onClick={send} disabled={thinking || inactive || !message.trim()} data-testid="composer-send-button"
                    className="rounded-xl h-10 px-4 active:scale-[0.97] transition-all duration-200">
                    {thinking ? 'Thinking\u2026' : <><span>Send</span><ArrowRight size={14} strokeWidth={1.75} className="ml-1.5" /></>}
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Low-credit warning */}
        {user && user.credits !== undefined && user.credits < 20 && user.credits > 0 && (
          <div data-testid="low-credit-warning" className="mt-3 flex items-center justify-between gap-2 rounded-xl border border-destructive/20 bg-destructive/5 px-3 py-2">
            <span className="text-xs text-muted">{user.credits.toLocaleString()} tokens left this month &mdash; {' '}
              <button onClick={() => navigate('/app/billing')} className="underline font-medium text-accent">top up</button> to keep going.
            </span>
          </div>
        )}

        {/* Conversation History — collapsible */}
        <Collapsible open={historyOpen} onOpenChange={setHistoryOpen} className="mt-3">
          <CollapsibleTrigger asChild>
            <button data-testid="history-toggle-button"
              className="flex items-center gap-2 text-xs text-muted hover:text-text transition-colors w-full justify-center py-2 rounded-xl hover:bg-surface-2/60">
              {historyOpen ? <ChevronUp size={14} strokeWidth={1.75} /> : <ChevronDown size={14} strokeWidth={1.75} />}
              {historyOpen ? 'Hide history' : `Show history (${messages.length} messages)`}
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="mt-2 rounded-xl border border-hairline bg-surface-2/30">
              <ScrollArea data-testid="history-scroll-area" className="max-h-96 overflow-y-auto px-4 py-3">
                <div className="space-y-2">
                  {messages.slice(-historyLimit).map((m, i) => (
                    <div key={i} data-testid={`history-message-${i}`}
                      className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[85%] rounded-xl px-3 py-2 ${m.role === 'user' ? 'bg-accent-wash/50' : 'bg-surface'}`}>
                        <p className="text-xs leading-5 text-text whitespace-pre-wrap">{m.text}</p>
                        <p className="text-[10px] text-muted mt-0.5 font-mono-plex text-right">{fmtTime(m.at)}</p>
                      </div>
                    </div>
                  ))}
                  {messages.length > historyLimit && (
                    <button data-testid="load-older-messages"
                      onClick={() => setHistoryLimit(l => l + 50)}
                      className="text-xs text-accent hover:underline w-full text-center py-2 block">
                      Load older messages ({messages.length - historyLimit} remaining)
                    </button>
                  )}
                </div>
              </ScrollArea>
            </div>
          </CollapsibleContent>
        </Collapsible>

      </main>
    </div>
  );
}
