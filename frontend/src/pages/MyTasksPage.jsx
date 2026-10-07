import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { TopBar } from '../components/TopBar';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import { Loader2, CheckCircle2, Clock, Upload, MessageCircle, AlertTriangle, FileText, ChevronDown, ChevronUp, Send } from 'lucide-react';
import { toast } from 'sonner';

// Badge colors per task status
const STATUS_COLORS = {
  pending: 'bg-muted text-muted border-hairline/60',
  in_progress: 'bg-blue-50 text-blue-700 border-blue-200',
  awaiting_review: 'bg-amber-50 text-amber-700 border-amber-200',
  done: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  blocked: 'bg-red-50 text-red-700 border-red-200',
  needs_clarification: 'bg-orange-50 text-orange-700 border-orange-200',
};

// Format a task due date
const fmtDate = (iso) => {
  if (!iso) return '';
  try { return new Date(iso).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' }); }
  catch { return ''; }
};

// Expandable task card with proof and clarify flows
const TaskCard = ({ task, onUpdate, busy }) => {
  const [expanded, setExpanded] = useState(false);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [clarifyOpen, setClarifyOpen] = useState(false);
  const [clarifyQuestion, setClarifyQuestion] = useState('');
  const [clarifyBusy, setClarifyBusy] = useState(false);
  const [clarifyAnswer, setClarifyAnswer] = useState('');

  // Read and validate an attached file
  const handleFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 8 * 1024 * 1024) {
      toast.error('File too large. Keep under 8 MB.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setFile({ name: f.name, type: f.type, data: reader.result });
    reader.readAsDataURL(f);
  };

  // Submit proof file for AI review
  const submitProof = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const base64 = file.data.split(',')[1];
      await api.patch(`/org/tasks/${task.id}`, {
        status: 'awaiting_review',
        proof_files: [{ name: file.name, type: file.type, data: base64, uploaded_at: new Date().toISOString() }],
      });
      toast.success('Proof submitted. AI is reviewing it now.');
      setFile(null);
      onUpdate();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not submit proof.');
    } finally { setUploading(false); }
  };

  // Update the task status
  const changeStatus = async (status) => {
    try {
      await api.patch(`/org/tasks/${task.id}`, { status });
      toast.success(`Task marked as ${status}.`);
      onUpdate();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not update status.');
    }
  };

  // Open the clarification dialog
  const askAboutTask = () => {
    setClarifyQuestion('');
    setClarifyAnswer('');
    setClarifyOpen(true);
  };

  // Ask the brain about this task
  const submitClarify = async () => {
    if (!clarifyQuestion.trim()) return;
    setClarifyBusy(true);
    try {
      const r = await api.post('/brain/task-clarify', { task_id: task.id, question: clarifyQuestion.trim() });
      setClarifyAnswer(r.data.answer);
      toast.success('Answer ready');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not get clarification.');
    } finally { setClarifyBusy(false); }
  };

  const due = task.due_at ? new Date(task.due_at) : null;
  const overdue = due && due.getTime() < Date.now() && task.status !== 'done';

  return (
    <>
    <div className={`rounded-xl border bg-background px-4 py-3 ${overdue ? 'border-amber-200' : 'border-hairline/70'}`}>
      <div className="flex items-start justify-between gap-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs px-2 py-0.5 rounded-full border ${STATUS_COLORS[task.status] || 'bg-muted text-muted'}`}>
              {task.status.replace(/_/g, ' ')}
            </span>
            {overdue && <span className="text-[10px] text-amber-600 flex items-center gap-1"><Clock size={10} /> Overdue</span>}
            <span className="text-[10px] text-muted">{task.department_function}</span>
          </div>
          <p className="text-sm font-medium mt-1">{task.title}</p>
          {expanded && task.description && (
            <p className="text-xs text-muted mt-1.5 leading-5">{task.description}</p>
          )}
        </div>
        {expanded ? <ChevronUp size={16} className="text-muted shrink-0 mt-1" /> : <ChevronDown size={16} className="text-muted shrink-0 mt-1" />}
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-hairline/60 space-y-3">
          {task.founder_context && (
            <div className="rounded-lg border border-hairline/60 bg-[hsl(var(--accent))]/30 px-3 py-2 space-y-0.5">
              {task.founder_context.split('\n').map((line, i) => (
                <p key={i} className={`text-[11px] leading-5 ${i === 0 ? 'font-medium text-foreground' : 'text-muted'}`}>
                  {line}
                </p>
              ))}
            </div>
          )}

          <div className="flex items-center gap-2 text-xs text-muted">
            <Clock size={12} /> Due: {fmtDate(task.due_at)}
            {task.ai_review?.status !== 'pending' && (
              <Badge className={`rounded-lg text-[10px] font-normal ${task.ai_review?.status === 'approved' ? 'bg-emerald-50 text-emerald-700' : task.ai_review?.status === 'flagged' ? 'bg-amber-50 text-amber-700' : ''}`}>
                AI: {task.ai_review?.status}
              </Badge>
            )}
          </div>

          {task.status === 'pending' && (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => changeStatus('in_progress')} className="rounded-lg h-8 px-3 text-xs">Start working</Button>
              <Button size="sm" variant="secondary" onClick={askAboutTask} className="rounded-lg h-8 px-3 text-xs border border-hairline/70">
                <MessageCircle size={12} className="mr-1" /> Ask about this
              </Button>
            </div>
          )}

          {task.status === 'in_progress' && (
            <div className="space-y-3">
              {!file ? (
                <div>
                  <label className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-hairline/70 bg-background text-xs cursor-pointer hover:bg-[hsl(var(--accent))]/40 transition-colors">
                    <Upload size={12} /> Upload proof (image/file)
                    <input type="file" accept="image/*,.pdf,.docx,.xlsx,.csv,.txt" className="hidden" onChange={handleFile} />
                  </label>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-2 rounded-lg border border-hairline/60 bg-[hsl(var(--accent))]/30 px-3 py-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText size={13} className="text-muted shrink-0" />
                    <span className="text-xs truncate">{file.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button size="sm" onClick={submitProof} disabled={uploading} className="rounded-lg h-7 px-2.5 text-[11px]">
                      {uploading ? <Loader2 className="animate-spin" size={11} /> : 'Submit proof'}
                    </Button>
                    <button onClick={() => setFile(null)} className="text-muted hover:text-foreground text-xs">Change</button>
                  </div>
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" onClick={askAboutTask} className="rounded-lg h-8 px-3 text-xs border border-hairline/70">
                  <MessageCircle size={12} className="mr-1" /> Ask about this
                </Button>
              </div>
            </div>
          )}

          {task.status === 'awaiting_review' && (
            <div className="flex items-center gap-2 text-xs">
              <Loader2 className="animate-spin" size={12} />
              AI is reviewing your proof...
              <Button size="sm" variant="secondary" onClick={askAboutTask} className="rounded-lg h-7 px-2.5 text-[11px] border border-hairline/70">
                <MessageCircle size={11} className="mr-1" /> Ask
              </Button>
            </div>
          )}
        </div>
      )}
    </div>

    {/* Clarification Dialog */}
    <Dialog open={clarifyOpen} onOpenChange={setClarifyOpen}>
      <DialogContent className="sm:max-w-md rounded-2xl">
        <DialogHeader>
          <DialogTitle className="font-display text-lg font-normal">Ask about this task</DialogTitle>
          <DialogDescription className="text-sm text-muted">
            {task.title}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          {!clarifyAnswer ? (
            <>
              <div className="relative">
                <textarea
                  value={clarifyQuestion}
                  onChange={e => setClarifyQuestion(e.target.value)}
                  placeholder="What do you need help with? E.g. 'How should I approach this?' or 'What's the first step?'"
                  className="w-full rounded-xl border bg-background px-3 py-2 text-sm min-h-[80px] resize-none"
                  rows={3}
                  autoFocus
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitClarify(); } }}
                />
              </div>
              <Button
                className="w-full rounded-xl"
                onClick={submitClarify}
                disabled={clarifyBusy || !clarifyQuestion.trim()}
              >
                {clarifyBusy ? <Loader2 size={14} className="animate-spin mr-2" /> : <Send size={14} className="mr-2" />}
                Ask
              </Button>
            </>
          ) : (
            <div className="rounded-xl border bg-accent/5 p-4">
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{clarifyAnswer}</p>
              <Button
                variant="secondary"
                size="sm"
                className="rounded-lg mt-3"
                onClick={() => { setClarifyQuestion(''); setClarifyAnswer(''); }}
              >
                Ask another
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
    </>
  );
};

// Assigned tasks list page
export default function MyTasksPage() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  // Load tasks assigned to the user
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/org/tasks/mine');
      setTasks(r.data.tasks || []);
    } catch (e) {
      if (e?.response?.status === 403) navigate('/app');
    } finally { setLoading(false); }
  }, [navigate]);

  useEffect(() => { load(); }, [load]);

  const filtered = filter === 'all' ? tasks : tasks.filter((t) => t.status === filter);
  const pending = tasks.filter((t) => t.status === 'pending').length;
  const inProgress = tasks.filter((t) => t.status === 'in_progress').length;
  const overdue = tasks.filter((t) => t.due_at && new Date(t.due_at).getTime() < Date.now() && t.status !== 'done').length;

  return (
    <div className="min-h-screen">
      <TopBar title="My Tasks" backTo="/app" />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pb-24 pt-4 space-y-4">
        {loading ? (
          <div className="flex items-center gap-2 justify-center text-sm text-muted py-24">
            <Loader2 className="animate-spin" size={16} /> Loading your tasks...
          </div>
        ) : tasks.length === 0 ? (
          <div className="text-center py-24">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl border mb-4 text-muted"><CheckCircle2 size={20} /></div>
            <h2 className="font-display text-xl">No tasks yet</h2>
            <p className="text-sm text-muted mt-2">Your tasks will appear here once the founder generates the weekly plan.</p>
            <Button variant="secondary" className="rounded-xl mt-6" onClick={() => navigate('/app/brain')}>Open Brain</Button>
          </div>
        ) : (
          <>
            {/* summary */}
            <div className="grid grid-cols-4 gap-2 text-center">
              <div className="rounded-xl bg-[hsl(var(--accent))]/50 px-3 py-2">
                <div className="text-lg font-display">{tasks.length}</div>
                <div className="text-[10px] text-muted">Total</div>
              </div>
              <div className="rounded-xl bg-blue-50 px-3 py-2">
                <div className="text-lg font-display text-blue-600">{pending}</div>
                <div className="text-[10px] text-muted">Pending</div>
              </div>
              <div className="rounded-xl bg-emerald-50 px-3 py-2">
                <div className="text-lg font-display text-emerald-600">{inProgress}</div>
                <div className="text-[10px] text-muted">Active</div>
              </div>
              {overdue > 0 ? (
                <div className="rounded-xl bg-amber-50 px-3 py-2">
                  <div className="text-lg font-display text-amber-600">{overdue}</div>
                  <div className="text-[10px] text-muted">Overdue</div>
                </div>
              ) : (
                <div className="rounded-xl bg-[hsl(var(--accent))]/50 px-3 py-2">
                  <div className="text-lg font-display text-muted">0</div>
                  <div className="text-[10px] text-muted">Overdue</div>
                </div>
              )}
            </div>

            {/* filter tabs */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {['all', 'pending', 'in_progress', 'awaiting_review'].map((f) => (
                <button key={f} onClick={() => setFilter(f)}
                  className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${filter === f ? 'bg-foreground text-background' : 'bg-[hsl(var(--accent))]/50 text-muted hover:text-foreground border border-hairline/60'}`}>
                  {f === 'all' ? 'All' : f.replace(/_/g, ' ')}
                  {f !== 'all' && <span className="ml-1 text-[10px] opacity-60">({tasks.filter((t) => t.status === f).length})</span>}
                </button>
              ))}
            </div>

            {/* task list */}
            <div className="space-y-2">
              {filtered.map((task) => (
                <TaskCard key={task.id} task={task} onUpdate={load} />
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
