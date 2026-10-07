import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../App';
import { api } from '../lib/api';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { Users, Loader2, LogIn, AlertCircle } from 'lucide-react';

// Accept an org invite via share link
export default function JoinPage() {
  const { code } = useParams();
  const { user, setUser } = useAuth();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [info, setInfo] = useState(null); // { valid, org_name, role }
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    api.get(`/org/invites/${code}`)
      .then((r) => { if (alive) setInfo(r.data); })
      .catch(() => { if (alive) setInfo({ valid: false }); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [code]);

  // Join the workspace with the invite code
  const join = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    try {
      const r = await api.post('/org/join', { code });
      setUser((u) => (u ? { ...u, org_id: r.data.id, org_role: r.data.role } : u));
      localStorage.removeItem('sdg_pending_invite');
      toast.success(`You've joined ${r.data.name}.`);
      navigate('/app/team');
    } catch (e) {
      const status = e?.response?.status;
      if (status === 409) {
        toast.info('You are already part of an organization.');
        navigate('/app/team');
      } else {
        toast.error(e?.response?.data?.detail || 'Could not join. The link may be invalid.');
      }
    } finally { setBusy(false); }
  }, [busy, code, navigate, setUser]);

  // Stash invite and send to sign in
  const goSignIn = () => {
    localStorage.setItem('sdg_pending_invite', code);
    navigate('/auth');
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div data-testid="join-page" className="w-full max-w-md rounded-2xl border bg-surface p-8 text-center">
        {loading && (
          <div className="flex items-center gap-2 justify-center text-sm text-muted py-8">
            <Loader2 className="animate-spin" size={16} /> Checking invite…
          </div>
        )}

        {!loading && (!info || !info.valid) && (
          <div data-testid="join-invalid" className="py-6">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl border mb-4 text-muted">
              <AlertCircle size={20} />
            </div>
            <h2 className="font-display text-xl">{"This invite link isn't valid"}</h2>
            <p className="text-sm text-muted mt-2">It may have been revoked or already used. Ask the workspace owner for a fresh link.</p>
            <Button variant="secondary" className="rounded-xl mt-6" onClick={() => navigate('/')}>Go home</Button>
          </div>
        )}

        {!loading && info && info.valid && (
          <div className="py-2">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl border bg-background mb-4">
              <Users size={24} strokeWidth={1.5} />
            </div>
            <p className="text-xs uppercase tracking-widest text-muted">{"You've been invited to join"}</p>
            <h2 data-testid="join-org-name" className="font-display text-2xl sm:text-3xl mt-1">{info.org_name}</h2>
            <p className="text-sm text-muted mt-3">
              {"Join the workspace to get decisions backed by the team's playbook."}
            </p>

            {user ? (
              <Button data-testid="join-confirm-btn" onClick={join} disabled={busy} className="rounded-xl mt-6 w-full">
                {busy ? <Loader2 className="animate-spin" size={16} /> : `Join ${info.org_name}`}
              </Button>
            ) : (
              <Button data-testid="join-signin-btn" onClick={goSignIn} className="rounded-xl mt-6 w-full">
                <LogIn size={16} className="mr-2" /> Sign in or create an account to join
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
