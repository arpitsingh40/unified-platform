import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTheme } from 'next-themes';
import { LogOut, CircleUser, Plus, LayoutDashboard, MessageSquare, Users, Clock, BookOpen, CheckSquare, MessageCircle, Target, Flag, CheckCircle, Sun, Moon, Flame, Compass, Zap, History, Brain, UserCog } from 'lucide-react';
import { Button } from './ui/button';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { FeedbackDialog } from './FeedbackDialog';
import { api } from '../lib/api';
import { useAuth } from '../App';

// Format remaining time until a due date as "2d 3h".
const fmtLeft = (iso) => {
  if (!iso) return '';
  const ms = new Date(iso).getTime() - Date.now();
  if (ms < 0) return 'overdue';
  const m = Math.round(ms / 60000);
  const d = Math.floor(m / 1440); const h = Math.floor((m % 1440) / 60); const mm = m % 60;
  return d > 0 ? `${d}d ${h}h` : h > 0 ? `${h}h` : `${mm}m`;
};

// Primary navigation groups with routes and icons.
const NAV_SECTIONS = [
  {
    id: 'think', label: '',
    items: [
      { to: '/app', label: 'Threads', icon: MessageCircle, testid: 'nav-threads' },
      { to: '/app/brain', label: 'Brain', icon: Brain, testid: 'nav-brain' },
    ],
  },
  {
    id: 'run', label: '',
    items: [
      { to: '/app/business-os', label: 'Ops', icon: Zap, testid: 'nav-business-os' },
      { to: '/app/team', label: 'Team', icon: Users, testid: 'nav-team' },
    ],
  },
];

// App header with nav, theme toggle, credits, and account menu.
export const TopBar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, setTheme } = useTheme();
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [active, setActive] = useState(null);
  const [threadCount, setThreadCount] = useState(0);
  const [journeyState, setJourneyState] = useState(null);

  // Fetch the active action timer state from the brain.
  const loadActive = useCallback(() => {
    if (!user) return;
    api.get('/brain/active').then((r) => setActive(r.data?.next || null)).catch(() => {});
  }, [user]);

  useEffect(() => {
    if (!user) return undefined;
    const loadJourney = () => api.get('/journey').then((r) => {
      setJourneyState({
        started: r.data?.started || false,
        has_direction: r.data?.has_direction || false,
        milestones: (r.data?.milestones || []).length > 0,
        team_plan: !!(r.data?.team?.plan),
      });
    }).catch(() => {});
    loadJourney();
    window.addEventListener('sdg-journey-changed', loadJourney);
    return () => window.removeEventListener('sdg-journey-changed', loadJourney);
  }, [user]);

  useEffect(() => {
    if (!user) return;
    api.get('/goals').then((r) => {
      const items = r.data?.goals || [];
      setThreadCount(items.filter((g) => g.status === 'active').length);
    }).catch(() => {});
  }, [user]);

  useEffect(() => {
    loadActive();
    const id = setInterval(loadActive, 60000);
    const onChange = () => loadActive();
    window.addEventListener('sdg-actions-changed', onChange);
    return () => { clearInterval(id); window.removeEventListener('sdg-actions-changed', onChange); };
  }, [loadActive]);

  // Highlight the nav item matching the current route.
  const isActive = (to) => (to === '/app' ? location.pathname === '/app' : location.pathname.startsWith(to));
  // Switch between light and dark themes.
  const toggleTheme = () => setTheme(theme === 'dark' ? 'light' : 'dark');

  const allNavItems = NAV_SECTIONS.flatMap(s => s.items);
  const allRoutes = allNavItems.map(n => n.to);

  return (
    <header className="relative z-10 max-w-5xl mx-auto px-3 sm:px-6 lg:px-8 pt-4 sm:pt-6 pb-2 overflow-x-clip">
      <div className="flex items-center justify-between gap-3">
        <button onClick={() => navigate('/app')} data-testid="brand-home" className="flex items-center gap-2 shrink-0">
          <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-text text-background font-display text-sm">S</span>
          <span className="font-display text-lg sm:text-xl hidden sm:inline">SmartDecigen</span>
        </button>

        <nav className="hidden lg:flex items-center gap-1 ml-3 mr-auto">
          {NAV_SECTIONS.map(section => (
            <div key={section.id} className="flex items-center">
              <span className="text-[9px] uppercase tracking-[0.2em] text-muted/50 px-2 select-none">{section.label}</span>
              {section.items.map((n) => {
                const Icon = n.icon;
                return (
                  <button key={n.to} data-testid={n.testid} onClick={() => navigate(n.to)}
                    className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm transition-colors ${isActive(n.to) ? 'bg-surface-2 text-text' : 'text-muted hover:text-text hover:bg-surface-2/60'}`}>
                    <Icon size={15} strokeWidth={1.75} /> {n.label}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="flex items-center gap-3 sm:gap-4 shrink-0">
          <button onClick={toggleTheme} data-testid="theme-toggle"
            className="flex items-center justify-center w-8 h-8 rounded-xl text-muted hover:text-text hover:bg-surface-2/60 transition-all duration-200"
            aria-label="Toggle theme">
            {theme === 'dark' ? <Sun size={15} strokeWidth={1.75} /> : <Moon size={15} strokeWidth={1.75} />}
          </button>
          {active && (
            <button data-testid="active-action-timer" onClick={() => navigate('/app/decisions')} title={active.action}
              className={`flex items-center gap-1.5 text-xs rounded-full px-2.5 py-1 border transition-colors ${active.overdue ? 'border-destructive/40 text-destructive bg-destructive/10' : 'border-hairline text-accent hover:bg-surface-2/60'}`}>
              <Clock size={12} strokeWidth={2} />
              <span className="font-mono-plex">{active.overdue ? 'Action due' : fmtLeft(active.due_at)}</span>
            </button>
          )}
          <button data-testid="credits-balance" onClick={() => navigate('/app/billing')}
            className="group flex items-center gap-1 font-mono-plex text-xs text-muted hover:text-text transition-colors shrink-0" title="Credits">
            <span className="hidden xs:inline">{user?.credits ?? 0} credits</span>
            <span className="xs:hidden">{user?.credits ?? 0}</span>
            <Plus size={12} strokeWidth={2} className="opacity-60 group-hover:opacity-100" />
          </button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" data-testid="account-menu-button" className="rounded-xl">
                <CircleUser size={18} strokeWidth={1.75} />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="rounded-xl w-56">
              <DropdownMenuLabel className="text-xs font-normal text-muted">{user?.email}</DropdownMenuLabel>
              {journeyState && (
                <div className="px-3 py-2 space-y-1 border-b border-hairline mb-1" data-testid="progress-checklist">
                  <p className="text-[10px] uppercase tracking-wider text-muted/70">Your progress</p>
                  {[
                    { done: journeyState.started, label: 'Start your conversation', icon: MessageCircle },
                    { done: journeyState.has_direction, label: 'Get a direction', icon: Target },
                    { done: journeyState.milestones, label: 'Set measurable milestones', icon: Flag },
                    { done: threadCount > 0, label: 'Start daily check-ins', icon: CheckCircle },
                    { done: journeyState.team_plan, label: 'Set up your team', icon: Users },
                  ].map((s) => (
                    <div key={s.label} className="flex items-center gap-2 text-xs">
                      {s.done
                        ? <CheckCircle size={12} className="text-accent shrink-0" />
                        : <div className="w-3 h-3 rounded-full border border-muted/40 shrink-0" />}
                      <span className={s.done ? 'text-muted/70' : 'text-muted'}>{s.label}</span>
                    </div>
                  ))}
                </div>
              )}
              <DropdownMenuSeparator />
              <div className="lg:hidden">
                {NAV_SECTIONS.map(section => (
                  <div key={section.id}>
                    <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted/50 px-3 py-1">{section.label}</DropdownMenuLabel>
                    {section.items.map((n) => (
                      <DropdownMenuItem key={n.to} data-testid={`menu-${n.testid}`} onClick={() => navigate(n.to)} className="text-sm cursor-pointer">
                        <n.icon size={16} strokeWidth={1.75} className="mr-2" /> {n.label}
                      </DropdownMenuItem>
                    ))}
                  </div>
                ))}
                <DropdownMenuSeparator />
              </div>
              <DropdownMenuItem onClick={() => navigate('/app/habits')} className="text-sm cursor-pointer">
                <Flame size={16} strokeWidth={1.75} className="mr-2" /> Habits
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/app/playbooks')} className="text-sm cursor-pointer">
                <BookOpen size={16} strokeWidth={1.75} className="mr-2" /> Playbooks
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/app/founder-profile')} className="text-sm cursor-pointer">
                <UserCog size={16} strokeWidth={1.75} className="mr-2" /> My Profile
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem data-testid="buy-credits-menu" onClick={() => navigate('/app/billing')} className="text-sm cursor-pointer">
                <Plus size={16} strokeWidth={1.75} className="mr-2" /> Subscription & tokens
              </DropdownMenuItem>
              <DropdownMenuItem data-testid="feedback-menu" onClick={() => setFeedbackOpen(true)} className="text-sm cursor-pointer">
                <MessageSquare size={16} strokeWidth={1.75} className="mr-2" /> Share feedback
              </DropdownMenuItem>
              {user?.is_admin && (
                <DropdownMenuItem data-testid="founder-os-menu" onClick={() => navigate('/app/admin')} className="text-sm cursor-pointer">
                  <LayoutDashboard size={16} strokeWidth={1.75} className="mr-2" /> Founder OS
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem data-testid="logout-button" onClick={logout} className="text-sm cursor-pointer">
                <LogOut size={16} strokeWidth={1.75} className="mr-2" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      <FeedbackDialog open={feedbackOpen} onOpenChange={setFeedbackOpen} />
    </header>
  );
};
