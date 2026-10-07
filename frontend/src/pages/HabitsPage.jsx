import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../App';
import { api } from '../lib/api';
import { TopBar } from '../components/TopBar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { Plus, Check, Flame, Trash2, Target, RotateCcw, Archive } from 'lucide-react';

// Daily habit tracker page
export default function HabitsPage() {
  const { user } = useAuth();
  const [habits, setHabits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newTitle, setNewTitle] = useState('');
  const [newIdentity, setNewIdentity] = useState('');
  const [showForm, setShowForm] = useState(false);

  // Load the user's habit list
  const load = useCallback(() => {
    api.get('/v1/habits').then(r => setHabits(r.data.habits || [])).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  // Create a new daily habit
  const create = () => {
    if (!newTitle.trim()) return;
    api.post('/v1/habits', { title: newTitle.trim(), identity_statement: newIdentity.trim(), frequency: 'daily' })
      .then(() => { setNewTitle(''); setNewIdentity(''); setShowForm(false); load(); toast.success('Habit created'); })
      .catch(() => {});
  };

  // Log today's completion for a habit
  const logHabit = (id) => {
    api.post(`/v1/habits/${id}/log`, { note: '' })
      .then(() => { load(); toast.success('Logged!'); })
      .catch(() => {});
  };

  // Delete a habit permanently
  const del = (id) => {
    api.delete(`/v1/habits/${id}`).then(() => { load(); toast.success('Habit removed'); }).catch(() => {});
  };

  // Archive or restore a habit
  const toggleArchive = (id, archived) => {
    api.patch(`/v1/habits/${id}`, { archived: !archived }).then(() => load()).catch(() => {});
  };

  const active = habits.filter(h => !h.archived);
  const archived = habits.filter(h => h.archived);

  if (loading) return (
    <div className="paper min-h-screen">
      <TopBar />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-12">
        <div className="h-8 w-48 animate-pulse rounded-lg bg-primary/10 mb-6" />
        <div className="space-y-3">
          <div className="h-16 animate-pulse rounded-xl bg-primary/10" />
          <div className="h-16 animate-pulse rounded-xl bg-primary/10" />
          <div className="h-16 animate-pulse rounded-xl bg-primary/10" />
        </div>
      </main>
    </div>
  );

  return (
    <div className="paper min-h-screen">
      <TopBar />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pt-8 pb-20">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="font-display text-2xl">Habit Tracker</h1>
            <p className="text-sm text-muted mt-1">Identity-based habits. Never miss twice.</p>
          </div>
          <Button onClick={() => setShowForm(!showForm)} className="rounded-xl gap-1.5">
            <Plus size={15} /> New habit
          </Button>
        </div>

        {showForm && (
          <div className="bg-surface-2 rounded-xl p-4 mb-6 space-y-3 border border-hairline">
            <Input placeholder="Habit name (e.g. 'Write 500 words')" value={newTitle} onChange={e => setNewTitle(e.target.value)} className="rounded-xl" />
            <Input placeholder="Identity (e.g. 'I am a writer')" value={newIdentity} onChange={e => setNewIdentity(e.target.value)} className="rounded-xl" />
            <div className="flex gap-2">
              <Button onClick={create} size="sm" className="rounded-xl">Create</Button>
              <Button variant="ghost" size="sm" onClick={() => setShowForm(false)} className="rounded-xl">Cancel</Button>
            </div>
          </div>
        )}

        {active.length === 0 && (
          <div className="text-center py-16 text-muted">
            <Target size={40} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm">No habits yet. Create one to start tracking.</p>
          </div>
        )}

        <div className="space-y-2">
          {active.map(h => (
            <div key={h.id} className="flex items-center gap-3 bg-surface-2 rounded-xl px-4 py-3 border border-hairline">
              <button onClick={() => logHabit(h.id)} className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-colors ${h.done_today ? 'bg-accent text-background' : 'border border-muted/30 hover:border-accent/50'}`}>
                {h.done_today && <Check size={15} />}
              </button>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm truncate">{h.title}</div>
                <div className="flex items-center gap-3 text-xs text-muted mt-0.5">
                  <span className="flex items-center gap-1"><Flame size={12} className="text-orange-400" /> {h.streak} day streak</span>
                  <span>Best: {h.longest_streak}</span>
                  <span>Done: {h.total_done}x</span>
                </div>
                {h.identity_statement && <div className="text-[11px] text-accent/70 mt-0.5 italic">"{h.identity_statement}"</div>}
              </div>
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="icon" className="w-7 h-7 rounded-lg" onClick={() => toggleArchive(h.id, h.archived)} title="Archive"><Archive size={13} /></Button>
                <Button variant="ghost" size="icon" className="w-7 h-7 rounded-lg text-destructive/60 hover:text-destructive" onClick={() => del(h.id)} title="Delete"><Trash2 size={13} /></Button>
              </div>
            </div>
          ))}
        </div>

        {archived.length > 0 && (
          <>
            <h2 className="font-display text-lg mt-8 mb-3 text-muted">Archived</h2>
            <div className="space-y-2 opacity-60">
              {archived.map(h => (
                <div key={h.id} className="flex items-center gap-3 bg-surface-2 rounded-xl px-4 py-3 border border-hairline">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">{h.title}</div>
                    <div className="text-xs text-muted mt-0.5">Streak: {h.streak} · Best: {h.longest_streak} · Done: {h.total_done}x</div>
                  </div>
                  <Button variant="ghost" size="icon" className="w-7 h-7 rounded-lg" onClick={() => toggleArchive(h.id, h.archived)} title="Restore"><RotateCcw size={13} /></Button>
                </div>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
