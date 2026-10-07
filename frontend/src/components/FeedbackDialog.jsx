import { useState } from 'react';
import { Star } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { api } from '../lib/api';

// Feedback category options for the picker.
const CATEGORIES = [
  { id: 'bug', label: 'Bug' },
  { id: 'idea', label: 'Idea' },
  { id: 'praise', label: 'Praise' },
  { id: 'other', label: 'Other' },
];

// Modal dialog for collecting star-rated feedback.
export const FeedbackDialog = ({ open, onOpenChange }) => {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [category, setCategory] = useState('idea');
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);

  // Clear all form fields after sending.
  const reset = () => { setRating(0); setHover(0); setCategory('idea'); setMessage(''); };

  // Validate and post the feedback to the API.
  const submit = async () => {
    if (!rating || !message.trim()) return;
    setSending(true);
    try {
      await api.post('/feedback', { rating, category, message: message.trim() });
      toast.success('Thank you — your feedback was sent.');
      reset();
      onOpenChange(false);
    } catch {
      toast.error('Could not send feedback. Please try again.');
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="feedback-dialog" className="sm:max-w-md rounded-2xl">
        <DialogHeader>
          <DialogTitle className="font-display text-xl font-normal">Share feedback</DialogTitle>
          <DialogDescription className="text-xs text-muted">
            Tell the founder what works and what does not. Every note is read.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 pt-1">
          <div>
            <p className="text-[10px] uppercase tracking-[0.12em] text-muted mb-2">How is it so far?</p>
            <div className="flex items-center gap-1.5">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} type="button" data-testid={`feedback-star-${n}`}
                  onClick={() => setRating(n)}
                  onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(0)}
                  className="p-0.5 transition-transform hover:scale-110">
                  <Star size={22} strokeWidth={1.5}
                    className={(hover || rating) >= n
                      ? 'fill-amber-400 text-amber-400'
                      : 'text-hairline'} />
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="text-[10px] uppercase tracking-[0.12em] text-muted mb-2">What is it about?</p>
            <div className="flex flex-wrap gap-1.5">
              {CATEGORIES.map((c) => (
                <button key={c.id} type="button" data-testid={`feedback-category-${c.id}`}
                  onClick={() => setCategory(c.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                    category === c.id
                      ? 'bg-accent text-text border-transparent'
                      : 'bg-surface border-hairline text-muted hover:text-text'}`}>
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <Textarea data-testid="feedback-message" value={message}
              onChange={(e) => setMessage(e.target.value)} maxLength={2000} rows={4}
              placeholder="What should we know?"
              className="rounded-xl resize-none text-sm" />
            <p className="text-right text-[10px] text-muted mt-1">{message.length}/2000</p>
          </div>

          <Button data-testid="feedback-submit" onClick={submit}
            disabled={sending || !rating || !message.trim()}
            className="w-full rounded-xl">
            {sending ? 'Sending…' : 'Send feedback'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
