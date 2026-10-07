import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../App';
import { api } from '../lib/api';
import { TopBar } from '../components/TopBar';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import { ListChecks, RotateCcw, CheckCircle, Inbox, Search, RefreshCw, Compass } from 'lucide-react';

const STAGE_ICONS = { capture: Inbox, clarify: Search, reflect: RefreshCw, plan: Compass };
const STAGE_COLORS = { capture: 'text-blue-500', clarify: 'text-amber-500', reflect: 'text-purple-500', plan: 'text-green-500' };

// Four-stage weekly review flow page
export default function WeeklyReviewPage() {
  const { user } = useAuth();
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [content, setContent] = useState('');

  // Load the current review and stage content
  const load = useCallback(() => {
    api.get('/v1/weekly-review').then(r => {
      setReview(r.data);
      setContent(r.data.content?.[r.data.stage] || '');
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  // Save stage content and advance
  const save = () => {
    api.patch('/v1/weekly-review', { content }).then(r => {
      setReview(r.data);
      setContent('');
      toast.success('Saved & advanced');
      load();
    }).catch(() => {});
  };

  // Reset the review back to capture
  const reset = () => {
    api.post('/v1/weekly-review/reset').then(r => {
      setReview(r.data);
      setContent('');
      toast.success('Review reset');
    }).catch(() => {});
  };

  if (loading) return (
    <div className="paper min-h-screen">
      <TopBar />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-12">
        <div className="h-8 w-48 animate-pulse rounded-lg bg-primary/10 mb-6" />
        <div className="h-64 animate-pulse rounded-xl bg-primary/10" />
      </main>
    </div>
  );

  if (!review) return null;

  const stageIdx = review.stages.indexOf(review.stage);
  const StageIcon = STAGE_ICONS[review.stage] || ListChecks;
  const stageColor = STAGE_COLORS[review.stage] || 'text-foreground';

  return (
    <div className="paper min-h-screen">
      <TopBar />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-8 pb-20">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="font-display text-2xl">Weekly Review</h1>
            <p className="text-sm text-muted mt-1">Week of {review.week_key}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={reset} className="rounded-xl gap-1.5"><RotateCcw size={13} /> Reset</Button>
        </div>

        <div className="flex items-center gap-2 mb-8">
          {review.stages.map((s, i) => {
            const Icon = STAGE_ICONS[s] || ListChecks;
            const done = i < stageIdx || (i === stageIdx && review.content?.[s]);
            const current = i === stageIdx;
            return (
              <div key={s} className={`flex items-center gap-1.5 text-xs ${current ? STAGE_COLORS[s] + ' font-medium' : done ? 'text-muted' : 'text-muted/50'}`}>
                <Icon size={12} />
                <span className="hidden sm:inline capitalize">{s}</span>
                {i < review.stages.length - 1 && <ChevronRightIcon />}
              </div>
            );
          })}
        </div>

        <div className="bg-surface-2 rounded-2xl border border-hairline p-6">
          <div className="flex items-center gap-2 mb-4">
            <StageIcon size={18} className={stageColor} />
            <h2 className="font-display text-lg">{review.stage_label}</h2>
            {review.content?.[review.stage] && <CheckCircle size={14} className="text-green-500 ml-auto" />}
          </div>

          <Textarea
            className="w-full min-h-[200px] rounded-xl text-sm mb-4"
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder={
              review.stage === 'capture' ? 'What happened this week? Wins, challenges, surprises, decisions, conversations...' :
              review.stage === 'clarify' ? 'What does each item mean? What patterns emerge? What needs attention?' :
              review.stage === 'reflect' ? 'What worked? What didn\'t? What did you learn? What would you do differently?' :
              'What are the top 3 priorities for next week? What\'s the first action?'
            }
          />

          <div className="flex justify-between">
            <Button variant="ghost" size="sm" className="text-xs text-muted" disabled>
              {stageIdx + 1} of {review.stages.length}
            </Button>
            <Button onClick={save} disabled={!content.trim()} className="rounded-xl gap-1.5">
              {stageIdx < review.stages.length - 1 ? 'Save & continue' : 'Complete review'} <CheckCircle size={14} />
            </Button>
          </div>
        </div>

        {review.status === 'completed' && (
          <div className="mt-6 bg-accent/10 rounded-xl p-4 text-center">
            <CheckCircle size={24} className="mx-auto mb-2 text-accent" />
            <p className="font-medium text-sm">This week's review is complete</p>
            <p className="text-xs text-muted mt-1">Come back next week for a fresh one.</p>
          </div>
        )}
      </main>
    </div>
  );
}

// Render a step separator chevron
function ChevronRightIcon() { return <span className="text-muted/30 text-[10px]">▸</span>; }
