import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../App';
import { api } from '../lib/api';
import { TopBar } from '../components/TopBar';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import { Book, Target, Radar, Activity, ListChecks, Scale, CircleDot, CheckCircle, ChevronRight, ArrowRight, RotateCcw } from 'lucide-react';

const ICONS = { target: Target, radar: Radar, activity: Activity, list_checks: ListChecks, scale: Scale, circle_dot: CircleDot, book: Book };

// Framework playbook browser and runner
export default function PlaybooksPage() {
  const { user } = useAuth();
  const [playbooks, setPlaybooks] = useState([]);
  const [available, setAvailable] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [loading, setLoading] = useState(true);

  // Load started and available playbooks
  const load = useCallback(() => {
    Promise.all([
      api.get('/v1/playbooks'),
      api.get('/v1/playbooks/available'),
    ]).then(([p, a]) => {
      setPlaybooks(p.data.playbooks || []);
      setAvailable(a.data.playbooks || []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  // Start a new playbook
  const create = (key) => {
    api.post('/v1/playbooks', { playbook_key: key })
      .then(r => { load(); setActiveId(r.data.id); toast.success('Playbook started'); })
      .catch(() => {});
  };

  // Save inputs for the current stage
  const saveStage = (id, inputs) => {
    api.patch(`/v1/playbooks/${id}`, { inputs }).then(r => { load(); }).catch(() => {});
  };

  // Advance to the next playbook stage
  const advance = (id) => {
    api.post(`/v1/playbooks/${id}/advance`).then(r => { load(); toast.success('Advanced to next stage'); }).catch(() => {});
  };

  if (loading) return (
    <div className="paper min-h-screen">
      <TopBar />
      <main className="max-w-4xl mx-auto px-4 sm:px-6 pt-12">
        <div className="h-8 w-48 animate-pulse rounded-lg bg-primary/10 mb-6" />
        <div className="space-y-3">
          <div className="h-20 animate-pulse rounded-xl bg-primary/10" />
          <div className="h-20 animate-pulse rounded-xl bg-primary/10" />
        </div>
      </main>
    </div>
  );

  const active = activeId ? playbooks.find(p => p.id === activeId) : (playbooks.find(p => p.status === 'in_progress') || null);
  const completed = playbooks.filter(p => p.status === 'completed');

  return (
    <div className="paper min-h-screen">
      <TopBar />
      <main className="max-w-4xl mx-auto px-4 sm:px-6 pt-8 pb-20">
        <h1 className="font-display text-2xl mb-1">Framework Playbooks</h1>
        <p className="text-sm text-muted mb-6">Apply proven frameworks from the knowledge base to your business.</p>

        {active && (
          <div className="bg-surface-2 rounded-2xl border border-hairline p-6 mb-8">
            <div className="flex items-center justify-between mb-4">
              <div>
                <span className="text-xs text-muted uppercase tracking-wider">{active.book}</span>
                <h2 className="font-display text-xl mt-0.5">{active.title}</h2>
              </div>
              <span className="text-xs text-muted">{active.progress_pct}% complete</span>
            </div>
            <div className="w-full bg-background rounded-full h-1.5 mb-6">
              <div className="bg-accent h-1.5 rounded-full transition-all" style={{ width: `${active.progress_pct}%` }} />
            </div>
            {active.stage_info && (
              <div className="mb-4">
                <h3 className="font-medium text-sm mb-2">{active.stage_info.label}</h3>
                {active.stage_info.input_fields && active.stage_info.input_fields.map(f => (
                  <div key={f} className="mb-3">
                    <label className="text-xs text-muted block mb-1">{f.replace(/_/g, ' ')}</label>
                    <Textarea
                      className="rounded-xl text-sm min-h-[80px]"
                      value={active.inputs?.[f] || ''}
                      onChange={e => {
                        const pi = { ...(active.inputs || {}), [f]: e.target.value };
                        saveStage(active.id, pi);
                      }}
                      placeholder={`Enter your ${f.replace(/_/g, ' ')}...`}
                    />
                  </div>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <Button onClick={() => advance(active.id)} className="rounded-xl gap-1.5">
                {active.stage_info?.key === (active.registry?.stages?.[active.registry.stages.length - 1]?.key) ? 'Complete' : 'Next stage'} <ArrowRight size={15} />
              </Button>
              {completed.length > 0 && (
                <Button variant="outline" onClick={() => create(active.playbook_key)} className="rounded-xl gap-1.5">
                  <RotateCcw size={14} /> Redo
                </Button>
              )}
            </div>
          </div>
        )}

        <h2 className="font-display text-lg mb-3">Available Frameworks</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-8">
          {available.map(a => {
            const Icon = ICONS[a.icon] || Book;
            const inProgress = playbooks.find(p => p.playbook_key === a.key && p.status === 'in_progress');
            return (
              <button key={a.key} onClick={() => create(a.key)}
                className="text-left bg-surface-2 rounded-xl border border-hairline p-4 hover:bg-surface-2/80 transition-colors">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0 mt-0.5">
                    <Icon size={16} className="text-accent" />
                  </div>
                  <div className="min-w-0">
                    <div className="font-medium text-sm flex items-center gap-2">
                      {a.title}
                      {inProgress && <span className="text-[10px] text-accent bg-accent/10 px-2 py-0.5 rounded-full">In progress</span>}
                    </div>
                    <div className="text-xs text-muted mt-0.5 line-clamp-2">{a.description}</div>
                    <div className="text-[10px] text-muted/60 mt-1">{a.book} · {a.stages.length} stages</div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {completed.length > 0 && (
          <>
            <h2 className="font-display text-lg mb-3">Completed</h2>
            <div className="space-y-2 opacity-70">
              {completed.map(p => (
                <div key={p.id} className="flex items-center gap-3 bg-surface-2 rounded-xl px-4 py-3 border border-hairline">
                  <CheckCircle size={16} className="text-accent shrink-0" />
                  <div className="flex-1 min-w-0"><span className="font-medium text-sm">{p.title}</span> <span className="text-xs text-muted">({p.book})</span></div>
                  <Button variant="ghost" size="sm" onClick={() => create(p.playbook_key)} className="rounded-xl text-xs">Redo</Button>
                </div>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
