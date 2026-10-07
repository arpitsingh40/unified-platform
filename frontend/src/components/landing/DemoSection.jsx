import { MessageCircle, Zap, BarChart3 } from 'lucide-react';

// Mock product screens shown in the demo cards.
const SCREENS = [
  {
    icon: MessageCircle,
    label: 'Situation Pane',
    desc: '4 living fields — current state, easiest path, next action, open question. Updated every turn with one LLM call. Not a chatbot.',
    lines: ['Current state', 'You\'ve validated demand — 3 pilot customers signed.', 'Why this matters', 'Revenue in 30 days if you ship the onboarding flow.', 'Next action (24-48h)', 'Draft the onboarding email sequence. Ship by Thursday.', 'Open question', 'What\'s the one feature those 3 pilots all asked for?'],
  },
  {
    icon: Zap,
    label: 'Business OS',
    desc: '12 autonomous agents running on schedule. Connected to your tools. Executing, verifying, learning. Founder sees dashboard.',
    lines: ['Business OS — Live', '4 tools connected', 'Agents active: 12/12', 'Last cycle: 30 min ago', 'Sales Agent: Followed up 3 leads via Gmail', 'Ops Agent: Flagged 2 overdue tasks', 'Pending approvals: 1'],
  },
  {
    icon: BarChart3,
    label: 'Record Room',
    desc: 'Every decision, execution, and outcome tracked. Unified audit trail. Query your company history like a database.',
    lines: ['Record Room — Last 24h', 'agent_decision: Sales Agent — FOLLOW_UP_LEADS', 'agent_execution: GMAIL_SEND_EMAIL — sent', 'business_cycle: 12 agents, 4 executed, 3 tools', 'task_verified: Onboarding doc created — SUCCESS', 'Total: 47 events in 24h'],
  },
];

// Section showcasing three product surfaces in mock frames.
export default function DemoSection() {
  return (
    <section id="demo" className="relative py-28 sm:py-36 bg-surface-2 overflow-hidden">
      <div className="max-w-6xl mx-auto px-6 sm:px-10 lg:px-14">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <span className="inline-flex items-center gap-2 text-[11px] tracking-[0.26em] uppercase text-accent font-semibold mb-5">
            <span className="h-px bg-accent w-8" />
            See it in action
          </span>
          <h2 className="font-display text-4xl sm:text-5xl text-text tracking-tight">
            Your company, on autopilot.
          </h2>
          <p className="mt-4 text-sm text-muted max-w-md mx-auto">
            Three surfaces. One organization. This is what your team sees.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {SCREENS.map((s) => {
            const Icon = s.icon;
            return (
              <div key={s.label} className="bg-surface rounded-2xl border border-hairline overflow-hidden shadow-elevation-1">
                <div className="flex items-center gap-2 px-4 py-2.5 bg-surface-2 border-b border-hairline">
                  <div className="flex gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-red-300/60" />
                    <div className="w-2.5 h-2.5 rounded-full bg-amber-300/60" />
                    <div className="w-2.5 h-2.5 rounded-full bg-emerald-300/60" />
                  </div>
                  <span className="text-[10px] text-muted ml-2">{s.label}</span>
                </div>
                <div className="p-5 space-y-2.5">
                  <div className="flex items-center gap-2 mb-3">
                    <Icon size={16} strokeWidth={1.5} className="text-accent" />
                    <span className="text-sm font-medium text-text">{s.label}</span>
                  </div>
                  <p className="text-xs text-muted leading-relaxed mb-3">{s.desc}</p>
                  <div className="space-y-1.5">
                    {s.lines.map((line, i) => (
                      <div key={i} className={`text-[11px] ${i % 4 === 0 ? 'text-text font-medium pt-1' : 'text-muted'}`}>
                        {line}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
