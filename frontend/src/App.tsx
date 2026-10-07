import { useState, useEffect, createContext, useContext, useCallback, lazy, Suspense, FC } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { ThemeProvider } from 'next-themes';
import { Toaster } from './components/ui/sonner';
import ErrorBoundary from './components/ErrorBoundary';

// Wraps lazy pages with an error boundary HOC
const withErrorBoundary = (Component: React.LazyExoticComponent<React.ComponentType<any>>) =>
  (props: any) => <ErrorBoundary><Component {...props} /></ErrorBoundary>;
import { Button } from './components/ui/button';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from './components/ui/dialog';
import { api } from './lib/api';
import { toast } from 'sonner';
import './App.css';

const LandingPage = lazy(() => import('./pages/LandingPage'));
const AuthPage = lazy(() => import('./pages/AuthPage'));
const JourneyPage = lazy(() => import('./pages/JourneyPage'));
const ThreadPage = lazy(() => import('./pages/ThreadPage'));
const BrainPage = lazy(() => import('./pages/BrainPage'));
const DecisionsPage = lazy(() => import('./pages/DecisionsPage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const BillingPage = lazy(() => import('./pages/BillingPage'));
const PaymentResultPage = lazy(() => import('./pages/PaymentResultPage'));
const TeamPage = lazy(() => import('./pages/TeamPage'));
const JoinPage = lazy(() => import('./pages/JoinPage'));
const CockpitPage = lazy(() => import('./pages/CockpitPage'));
const MyTasksPage = lazy(() => import('./pages/MyTasksPage'));
const GoalSetupPage = lazy(() => import('./pages/GoalSetupPage'));
const MissionControlPage = lazy(() => import('./pages/MissionControlPage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const DecisionCardPage = lazy(() => import('./pages/DecisionCardPage'));
const HabitsPage = lazy(() => import('./pages/HabitsPage'));
const PlaybooksPage = lazy(() => import('./pages/PlaybooksPage'));
const WeeklyReviewPage = lazy(() => import('./pages/WeeklyReviewPage'));
const BusinessOSPage = lazy(() => import('./pages/BusinessOSPage'));
const ConnectionsPage = lazy(() => import('./pages/ConnectionsPage'));
const RecordRoomPage = lazy(() => import('./pages/RecordRoomPage'));

// Authenticated user shape stored in context
interface AppUser {
  id: string;
  email: string;
  name: string;
  credits: number;
  is_admin: boolean;
  questionnaire_completed: boolean;
  org_id?: string;
  org_role?: string;
  phone?: string;
  [key: string]: unknown;
}

// Contract for the auth context value
interface AuthContextType {
  user: AppUser | null;
  login: (usr: AppUser) => void;
  logout: () => void;
  setCredits: (credits: number) => void;
  setUser: React.Dispatch<React.SetStateAction<AppUser | null>>;
}

// Holds the global auth state and actions
const AuthContext = createContext<AuthContextType | null>(null);
// Access auth context or throw if missing
export const useAuth = (): AuthContextType => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthContext.Provider");
  return ctx;
};

// Modal shown when credits run out
function InsufficientCreditsModal() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    const handler = (e: CustomEvent) => {
      setMessage(e.detail || 'No active subscription. Subscribe to continue using the engine.');
      setOpen(true);
    };
    window.addEventListener('sdg-insufficient-credits', handler as EventListener);
    return () => window.removeEventListener('sdg-insufficient-credits', handler as EventListener);
  }, []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-md rounded-2xl">
        <DialogHeader>
          <DialogTitle className="font-display text-xl font-normal">Need a subscription</DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground mt-1">
            {message}
          </DialogDescription>
        </DialogHeader>
        <div className="py-2 text-sm text-muted-foreground leading-relaxed">
          Subscribe to a plan to get 10M tokens per month and keep your conversations going.
        </div>
        <DialogFooter className="flex gap-2 sm:gap-3">
          <Button variant="outline" onClick={() => setOpen(false)} className="rounded-xl">
            Dismiss
          </Button>
          <Button onClick={() => { setOpen(false); navigate('/app/billing'); }} className="rounded-xl">
            View plans
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Root app with auth state and routes
const App: FC = () => {
  const [user, setUser] = useState<AppUser | null>(null);
  const [checking, setChecking] = useState(true);

  const login = useCallback((usr: AppUser) => {
    setUser(usr);
  }, []);

  const logout = useCallback(() => {
    api.post('/auth/logout').catch(() => {});
    setUser(null);
  }, []);

  const setCredits = useCallback((credits: number) => {
    setUser((u) => u ? { ...u, credits } : u);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const verify = () => {
      api.get<AppUser>('/auth/me').then((r) => {
        if (cancelled) return;
        setUser(r.data);
      }).catch(() => {
        if (cancelled) return;
        setUser(null);
      }).finally(() => {
        if (!cancelled) setChecking(false);
      });
    };
    verify();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!user) return;
    const beat = () => api.post('/track/session', { session_id: sessionStorage.getItem('sdg_session') || null })
      .then((r: { data: { session_id: string } }) => sessionStorage.setItem('sdg_session', r.data.session_id))
      .catch(() => {});
    beat();
    const id = setInterval(beat, 60000);
    return () => clearInterval(id);
  }, [user]);

  useEffect(() => {
    if (!user || user.org_id) return;
    const pending = localStorage.getItem('sdg_pending_invite');
    if (!pending) return;
    api.post('/org/join', { code: pending })
      .then((r: { data: { id: string; name: string; role: string } }) => {
        localStorage.removeItem('sdg_pending_invite');
        setUser((u) => (u ? { ...u, org_id: r.data.id, org_role: r.data.role } : u));
        toast.success(`You've joined ${r.data.name}.`);
      })
      .catch(() => { localStorage.removeItem('sdg_pending_invite'); });
  }, [user]);

  if (checking) {
    return (
      <div className="paper min-h-screen">
        <div className="flex items-center justify-center min-h-screen bg-background">
          <div className="space-y-4 w-full max-w-md mx-auto px-6">
            <div className="h-8 w-3/5 animate-pulse rounded-lg bg-primary/10" />
            <div className="h-4 w-2/5 animate-pulse rounded-lg bg-primary/10" />
            <div className="mt-8 space-y-3">
              <div className="h-3 w-full animate-pulse rounded-lg bg-primary/10" />
              <div className="h-3 w-full animate-pulse rounded-lg bg-primary/10" />
              <div className="h-3 w-4/5 animate-pulse rounded-lg bg-primary/10" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, setCredits, setUser }}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <div className="paper min-h-screen">
        <BrowserRouter>
          <InsufficientCreditsModal />
          <Suspense fallback={<div className="flex items-center justify-center min-h-screen bg-background"><div className="space-y-4 w-full max-w-md mx-auto px-6"><div className="h-8 w-3/5 animate-pulse rounded-lg bg-primary/10" /><div className="h-4 w-2/5 animate-pulse rounded-lg bg-primary/10" /><div className="mt-8 space-y-3"><div className="h-3 w-full animate-pulse rounded-lg bg-primary/10" /><div className="h-3 w-full animate-pulse rounded-lg bg-primary/10" /><div className="h-3 w-4/5 animate-pulse rounded-lg bg-primary/10" /></div></div></div>}>
          <Routes>
            <Route path="/" element={user ? <Navigate to="/app" replace /> : withErrorBoundary(LandingPage)({})} />
            <Route path="/auth" element={user ? <Navigate to="/app" replace /> : withErrorBoundary(AuthPage)({})} />
            <Route path="/app" element={user ? withErrorBoundary(JourneyPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/decisions" element={user ? withErrorBoundary(DecisionsPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/brain" element={user ? withErrorBoundary(BrainPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/brain/:decisionId" element={user ? withErrorBoundary(BrainPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/thread/:threadId" element={user ? withErrorBoundary(ThreadPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/team" element={user ? withErrorBoundary(TeamPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/my-tasks" element={user ? withErrorBoundary(MyTasksPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/cockpit" element={user ? withErrorBoundary(CockpitPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/mission-control" element={user ? withErrorBoundary(MissionControlPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/goal-setup" element={user ? withErrorBoundary(GoalSetupPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/founder-profile" element={user ? withErrorBoundary(ProfilePage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/questionnaire" element={user ? withErrorBoundary(ProfilePage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/profile" element={user ? withErrorBoundary(ProfilePage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/join/:code" element={withErrorBoundary(JoinPage)({})} />
            <Route path="/d/:shareId" element={withErrorBoundary(DecisionCardPage)({})} />
            <Route path="/app/billing" element={user ? withErrorBoundary(BillingPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/pay/result" element={withErrorBoundary(PaymentResultPage)({})} />
            <Route path="/app/admin" element={user ? withErrorBoundary(AdminPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/habits" element={user ? withErrorBoundary(HabitsPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/playbooks" element={user ? withErrorBoundary(PlaybooksPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/weekly-review" element={user ? withErrorBoundary(WeeklyReviewPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/business-os" element={user ? withErrorBoundary(BusinessOSPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/connections" element={user ? withErrorBoundary(ConnectionsPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="/app/record-room" element={user ? withErrorBoundary(RecordRoomPage)({}) : <Navigate to="/auth" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          </Suspense>
        </BrowserRouter>
        <Toaster position="bottom-right" />
      </div>
      </ThemeProvider>
    </AuthContext.Provider>
  );
}

export default App;
