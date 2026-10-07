import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { api } from '../lib/api';
import { TopBar } from '../components/TopBar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import {
  Users, Building2, Link2, Copy, Trash2, Crown, UserPlus, Loader2, ShieldCheck, Target, Lock, Save, Rocket, ArrowRight,
} from 'lucide-react';

// Workspace management page for teams
export default function TeamPage() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [org, setOrg] = useState(null);
  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);

  const [orgName, setOrgName] = useState('');
  const [joinCode, setJoinCode] = useState('');
  const [busy, setBusy] = useState(false);

  const [strategy, setStrategy] = useState({ north_star: '', target: '', deadline: '', priorities: '', decision_rules: '', current_arr: null, target_arr: null });
  const [savingStrategy, setSavingStrategy] = useState(false);

  // Load members, invites, and strategy
  const loadOwnerData = useCallback(async () => {
    try {
      const [m, i] = await Promise.all([api.get('/org/members'), api.get('/org/invites')]);
      setMembers(m.data.members || []);
      setInvites(i.data.invites || []);
    } catch (_e) { /* member or transient */ }
    try {
      const s = await api.get('/org/strategy');
      setStrategy({
        north_star: s.data.north_star || '', target: s.data.target || '', deadline: s.data.deadline || '',
        priorities: (s.data.priorities || []).join('\n'), decision_rules: s.data.decision_rules || '',
        current_arr: s.data.current_arr ?? null, target_arr: s.data.target_arr ?? null,
      });
    } catch (_e) { /* not owner */ }
  }, []);

  // Load the current workspace
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/org');
      setOrg(r.data);
      if (r.data.is_owner) await loadOwnerData();
    } catch (e) {
      if (e?.response?.status === 404) setOrg(null);
      else toast.error('Could not load your workspace.');
    } finally {
      setLoading(false);
    }
  }, [loadOwnerData]);

  useEffect(() => { load(); }, [load]);

  // Sync org info into the user context
  const syncUserOrg = (data) => {
    setUser((u) => (u ? { ...u, org_id: data.id, org_role: data.role } : u));
  };

  // Create a new workspace
  const createOrg = async () => {
    if (orgName.trim().length < 2 || busy) return;
    setBusy(true);
    try {
      const r = await api.post('/org', { name: orgName.trim() });
      syncUserOrg(r.data);
      toast.success(`Workspace "${r.data.name}" created.`);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not create workspace.');
    } finally { setBusy(false); }
  };

  // Join a workspace by invite code
  const joinByCode = async () => {
    const code = joinCode.trim();
    if (code.length < 4 || busy) return;
    setBusy(true);
    try {
      const r = await api.post('/org/join', { code });
      syncUserOrg(r.data);
      toast.success(`You've joined ${r.data.name}.`);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'That invite link is not valid.');
    } finally { setBusy(false); }
  };

  // Create and copy an invite link
  const createInvite = async () => {
    setBusy(true);
    try {
      const r = await api.post('/org/invites', {});
      setInvites((prev) => [r.data, ...prev]);
      try {
        await navigator.clipboard.writeText(r.data.join_url);
        toast.success('Invite link created and copied to clipboard.');
      } catch (_e) {
        toast.success('Invite link created.');
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not create an invite.');
    } finally { setBusy(false); }
  };

  // Copy an invite link to clipboard
  const copyLink = async (url) => {
    try { await navigator.clipboard.writeText(url); toast.success('Link copied.'); }
    catch (_e) { toast.error('Copy failed — select the link manually.'); }
  };

  // Revoke a pending invite
  const revokeInvite = async (code) => {
    try {
      await api.post(`/org/invites/${code}/revoke`);
      setInvites((prev) => prev.map((i) => (i.code === code ? { ...i, status: 'revoked' } : i)));
      toast.success('Invite revoked.');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not revoke.');
    }
  };

  // Remove a member from the workspace
  const removeMember = async (userId, name) => {
    try {
      await api.delete(`/org/members/${userId}`);
      setMembers((prev) => prev.filter((m) => m.user_id !== userId));
      setOrg((o) => (o ? { ...o, member_count: Math.max(1, (o.member_count || 1) - 1) } : o));
      toast.success(`${name || 'Member'} removed.`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not remove member.');
    }
  };

  // Save the North Star strategy
  const saveStrategy = async () => {
    if (savingStrategy) return;
    setSavingStrategy(true);
    try {
      const priorities = strategy.priorities.split('\n').map((s) => s.trim()).filter(Boolean);
      const r = await api.put('/org/strategy', {
        north_star: strategy.north_star, target: strategy.target, deadline: strategy.deadline,
        priorities, decision_rules: strategy.decision_rules,
        current_arr: strategy.current_arr, target_arr: strategy.target_arr,
      });
      setOrg((o) => (o ? { ...o, strategy_set: r.data.strategy_set } : o));
      toast.success('North Star saved. It now quietly guides every decision your team makes.');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not save your North Star.');
    } finally { setSavingStrategy(false); }
  };

  // ---------------------------------------------------------------- render
  return (
    <div className="min-h-screen">
      <TopBar title="Workspace" backTo="/" />
      <main data-testid="team-page" className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pb-24 pt-4">

        {loading && (
          <div className="space-y-4 py-10">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 animate-pulse rounded-2xl bg-primary/10" />
              <div className="space-y-2 flex-1">
                <div className="h-6 w-48 animate-pulse rounded-md bg-primary/10" />
                <div className="h-4 w-32 animate-pulse rounded-md bg-primary/10" />
              </div>
            </div>
            <div className="h-px bg-border/50" />
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-16 animate-pulse rounded-xl bg-primary/10" />
              ))}
            </div>
          </div>
        )}

        {/* ---------------- NO ORG: create or join ---------------- */}
        {!loading && !org && (
          <div className="space-y-6 pt-6">
            <div className="text-center max-w-lg mx-auto">
              <h2 className="font-display text-2xl sm:text-3xl">Bring your team into one room.</h2>
              <p className="text-sm text-muted mt-2">
                Create a workspace to train it once, then invite your team. Or join an existing one with a link.
              </p>
            </div>

            <div className="rounded-2xl border bg-surface p-6">
              <div className="flex items-center gap-2 mb-3">
                <Building2 size={16} strokeWidth={1.75} />
                <h3 className="font-medium text-sm">Create a workspace</h3>
              </div>
              <div className="flex flex-col sm:flex-row gap-2">
                <Input data-testid="create-org-name" value={orgName} onChange={(e) => setOrgName(e.target.value)}
                  placeholder="e.g. Acme Solar" className="rounded-xl"
                  onKeyDown={(e) => e.key === 'Enter' && createOrg()} />
                <Button data-testid="create-org-submit" onClick={createOrg} disabled={busy || orgName.trim().length < 2}
                  className="rounded-xl shrink-0">
                  {busy ? <Loader2 className="animate-spin" size={15} /> : 'Create workspace'}
                </Button>
              </div>
              <p className="text-xs text-muted mt-2">You become the owner. You can invite teammates next.</p>
            </div>

            <div className="rounded-2xl border bg-surface p-6">
              <div className="flex items-center gap-2 mb-3">
                <Link2 size={16} strokeWidth={1.75} />
                <h3 className="font-medium text-sm">Join with an invite code</h3>
              </div>
              <div className="flex flex-col sm:flex-row gap-2">
                <Input data-testid="join-code-input" value={joinCode} onChange={(e) => setJoinCode(e.target.value)}
                  placeholder="Paste your invite code" className="rounded-xl"
                  onKeyDown={(e) => e.key === 'Enter' && joinByCode()} />
                <Button data-testid="join-code-submit" variant="secondary" onClick={joinByCode}
                  disabled={busy || joinCode.trim().length < 4} className="rounded-xl shrink-0">
                  Join
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* ---------------- MEMBER VIEW ---------------- */}
        {!loading && org && !org.is_owner && (
          <div data-testid="member-view" className="pt-10 text-center max-w-lg mx-auto">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl border bg-surface mb-4">
              <Users size={22} strokeWidth={1.5} />
            </div>
            <h2 className="font-display text-2xl">{org.name}</h2>
            <p className="text-sm text-muted mt-2">
              {"You're part of this workspace. Your decisions here are backed by the team's playbook."}
            </p>
            <div className="mt-6">
              <Button onClick={() => navigate('/app/brain')} className="rounded-xl">Open Brain</Button>
            </div>
          </div>
        )}

        {/* ---------------- OWNER VIEW ---------------- */}
        {!loading && org && org.is_owner && (
          <div className="space-y-8 pt-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-11 h-11 rounded-2xl border bg-surface flex items-center justify-center shrink-0">
                  <Building2 size={20} strokeWidth={1.5} />
                </div>
                <div className="min-w-0">
                  <h2 data-testid="org-name" className="font-display text-2xl truncate">{org.name}</h2>
                  <p className="text-xs text-muted">{org.member_count} {org.member_count === 1 ? 'member' : 'members'}</p>
                </div>
              </div>
              <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border bg-surface">
                <Crown size={12} /> Owner
              </span>
            </div>

            {/* Guided goal setup CTA */}
            <button
              data-testid="goal-setup-cta"
              onClick={() => navigate('/app/goal-setup')}
              className="w-full text-left rounded-2xl border border-[hsl(var(--ring))]/30 bg-[hsl(var(--accent))]/50 hover:bg-[hsl(var(--accent))]/70 transition-colors p-5 flex items-center gap-4 group"
            >
              <div className="w-11 h-11 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center shrink-0">
                <Rocket size={20} strokeWidth={1.75} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-medium text-sm">{org.strategy_set ? 'Revisit your goal setup' : 'Set up your goal — guided'}</div>
                <p className="text-xs text-muted mt-0.5">
                  {org.strategy_set
                    ? 'Walk through your North Star, the number, and your priorities step by step.'
                    : 'A few friendly steps: your dream, the number to hit, where you are now, and your non-negotiables. Takes about two minutes.'}
                </p>
              </div>
              <ArrowRight size={18} className="shrink-0 text-muted group-hover:translate-x-0.5 transition-transform" />
            </button>

            {/* North Star — the hidden moat (founder-only) */}
            <section className="rounded-2xl border bg-surface p-6">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <Target size={16} strokeWidth={1.75} />
                  <h3 className="font-medium text-sm">Your North Star</h3>
                </div>
                <span className="inline-flex items-center gap-1.5 text-[11px] px-2 py-0.5 rounded-full border bg-background text-muted">
                  <Lock size={11} /> Private to you
                </span>
              </div>
              <p className="text-xs text-muted mb-4">
                Only you can see this. Your team never sees it, yet every decision the brain gives them is quietly steered toward it.
              </p>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-muted">The dream</label>
                  <Textarea data-testid="strategy-northstar" value={strategy.north_star}
                    onChange={(e) => setStrategy((s) => ({ ...s, north_star: e.target.value }))}
                    placeholder="e.g. Reach 100 crore annual revenue and become the top C&I solar EPC in North India."
                    className="rounded-xl mt-1 min-h-[64px]" />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-muted">Target</label>
                    <Input data-testid="strategy-target" value={strategy.target}
                      onChange={(e) => setStrategy((s) => ({ ...s, target: e.target.value }))}
                      placeholder="100 Cr ARR" className="rounded-xl mt-1" />
                  </div>
                  <div>
                    <label className="text-xs text-muted">By when</label>
                    <Input data-testid="strategy-deadline" value={strategy.deadline}
                      onChange={(e) => setStrategy((s) => ({ ...s, deadline: e.target.value }))}
                      placeholder="Mar 2027" className="rounded-xl mt-1" />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-muted">Strategic priorities (one per line)</label>
                  <Textarea data-testid="strategy-priorities" value={strategy.priorities}
                    onChange={(e) => setStrategy((s) => ({ ...s, priorities: e.target.value }))}
                    placeholder={"Win commercial & industrial rooftop deals\nPush EPC ticket sizes above 50L\nProtect 18% margins"}
                    className="rounded-xl mt-1 min-h-[80px]" />
                </div>
                <div>
                  <label className="text-xs text-muted">Decision rules</label>
                  <Textarea data-testid="strategy-rules" value={strategy.decision_rules}
                    onChange={(e) => setStrategy((s) => ({ ...s, decision_rules: e.target.value }))}
                    placeholder="Never quote below 18% margin. Prefer C&I over residential."
                    className="rounded-xl mt-1 min-h-[64px]" />
                </div>
                <div className="flex justify-end">
                  <Button data-testid="strategy-save" onClick={saveStrategy} disabled={savingStrategy} className="rounded-xl">
                    {savingStrategy ? <Loader2 className="animate-spin" size={15} /> : <><Save size={14} className="mr-1.5" /> Save North Star</>}
                  </Button>
                </div>
              </div>
            </section>

            {/* Invite */}
            <section className="rounded-2xl border bg-surface p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <UserPlus size={16} strokeWidth={1.75} />
                  <h3 className="font-medium text-sm">Invite your team</h3>
                </div>
                <Button data-testid="create-invite-btn" size="sm" onClick={createInvite} disabled={busy} className="rounded-xl">
                  {busy ? <Loader2 className="animate-spin" size={14} /> : <><Link2 size={14} className="mr-1.5" /> New link</>}
                </Button>
              </div>
              {invites.length === 0 && (
                <p className="text-xs text-muted">No invite links yet. Create one to share with a teammate.</p>
              )}
              <div className="space-y-2">
                {invites.map((inv) => (
                  <div key={inv.code} className="flex items-center gap-2 text-xs">
                    <code data-testid="invite-link"
                      className={`flex-1 truncate font-mono-plex px-3 py-2 rounded-lg border bg-background ${inv.status !== 'pending' ? 'opacity-40 line-through' : ''}`}>
                      {inv.join_url}
                    </code>
                    <span className={`px-2 py-0.5 rounded-full border ${inv.status === 'pending' ? '' : 'text-muted'}`}>{inv.status}</span>
                    {inv.status === 'pending' && (
                      <>
                        <button data-testid="invite-copy" onClick={() => copyLink(inv.join_url)}
                          className="p-2.5 sm:p-1.5 rounded-lg border hover:bg-muted transition-colors" title="Copy link">
                          <Copy size={13} />
                        </button>
                        <button data-testid="invite-revoke" onClick={() => revokeInvite(inv.code)}
                          className="p-2.5 sm:p-1.5 rounded-lg border hover:bg-muted transition-colors text-muted" title="Revoke">
                          <Trash2 size={13} />
                        </button>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </section>

            {/* Members */}
            <section className="rounded-2xl border bg-surface p-6">
              <div className="flex items-center gap-2 mb-4">
                <Users size={16} strokeWidth={1.75} />
                <h3 className="font-medium text-sm">Members</h3>
              </div>
              <div className="divide-y">
                {members.map((m) => (
                  <div data-testid="member-row" key={m.user_id} className="flex items-center justify-between py-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium truncate">{m.name || m.email}</p>
                        {m.role === 'owner' && <Crown size={12} className="text-muted shrink-0" />}
                      </div>
                      <p className="text-xs text-muted truncate">{m.email}</p>
                    </div>
                    {m.role !== 'owner' ? (
                      <button data-testid="member-remove" onClick={() => removeMember(m.user_id, m.name)}
                        className="text-xs text-muted hover:text-destructive transition-colors flex items-center gap-1">
                        <Trash2 size={12} /> Remove
                      </button>
                    ) : (
                      <span className="text-xs text-muted">You</span>
                    )}
                  </div>
                ))}
              </div>
            </section>

            <div className="flex items-center gap-2 text-xs text-muted">
              <ShieldCheck size={13} />
              Next: train this workspace with your playbook so every member makes on-strategy decisions.
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
