import { MessageCircle, Target, CheckCircle2, Users, GitCommitHorizontal } from 'lucide-react';

// Timeline steps explaining the five-stage journey.
const STEPS = [
  {
    num: '01', icon: MessageCircle, label: 'One conversation',
    desc: 'Tell us your company vision. The engine builds a living model — your industry, constraints, fears, strategic forks — in one sitting.',
    accent: '#2F8F8A',
    detail: 'The journey engine asks 5-7 sharp questions, not 50. It builds your digital twin, then shapes a direction with trade-offs, milestones, and success probability.',
  },
  {
    num: '02', icon: Target, label: 'One direction',
    desc: 'Your AI Chief of Staff produces a decision package: the call, the trade-offs, the first moves, and what to measure — updated every check-in.',
    accent: '#2F8F8A',
    detail: 'Not generic advice. Specific to your industry, stage, constraints. The engine applies 100+ decision-science lenses from the best founder books ever written.',
  },
  {
    num: '03', icon: CheckCircle2, label: 'Daily action',
    desc: 'Every day, one concrete next move for the next 48 hours. The engine tracks consistency, detects stalling, and re-engages you after silence.',
    accent: '#2F8F8A',
    detail: 'The Situation Pane — 4 living fields updated with a single LLM call. No chat bubbles. Emotion tracking. Pace calibration. The accountability founders actually use.',
  },
  {
    num: '04', icon: Users, label: 'Your team runs',
    desc: 'Deploy agents for every function. They detect signals, execute through your tools, escalate to you — on their own schedule. Your company operates while you sleep.',
    accent: '#2F8F8A',
    detail: '12 autonomous agents with authority levels (L0-L5). Connected to Gmail, Slack, Notion, Stripe, GitHub. Verified execution. Outcome learning.',
  },
  {
    num: '05', icon: GitCommitHorizontal, label: 'Compound clarity',
    desc: 'Every decision, outcome, and file the Decision Brain remembers. Query your company like a database. Track everything in the Record Room.',
    accent: '#2F8F8A',
    detail: 'Business system health scan every week. OKRs auto-updated from execution data. Audit trail of every action. Your company gets smarter every cycle.',
  },
];

// Vertical timeline walking through the five steps.
export default function HowItWorks() {
  return (
    <section id="how-it-works" className="relative py-28 sm:py-36 bg-surface overflow-x-clip">
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1200px] h-[800px] rounded-full opacity-15"
          style={{ background: 'radial-gradient(circle at 50% 0%, hsl(var(--accent)/0.08) 0%, transparent 60%)' }} />
      </div>

      <div className="relative max-w-7xl mx-auto px-6 sm:px-10 lg:px-14">
        <div className="text-center max-w-2xl mx-auto mb-16 sm:mb-20">
          <span className="inline-flex items-center gap-2 text-[11px] tracking-[0.26em] uppercase text-accent font-semibold mb-5">
            <span className="h-px bg-accent w-8" />
            How it works
          </span>
          <h2 className="font-display text-4xl sm:text-5xl lg:text-[4rem] leading-[0.95] text-text tracking-tight">
            You steer.<br />The organization runs.
          </h2>
          <p className="mt-4 text-muted text-sm sm:text-base max-w-sm mx-auto">
            From first conversation to autonomous company — five steps
          </p>
        </div>

        <div className="relative max-w-4xl mx-auto">
          <div className="hidden sm:block absolute left-8 top-0 bottom-0 w-px bg-gradient-to-b from-accent/30 via-accent/20 to-accent/30" />
          <div className="space-y-12 sm:space-y-16">
            {STEPS.map((s) => {
              const Icon = s.icon;
              return (
                <div key={s.label} className="relative flex gap-6 sm:gap-8 items-start">
                  <div className="relative shrink-0">
                    <div className="w-16 h-16 rounded-2xl bg-surface border border-hairline flex items-center justify-center shadow-sm">
                      <Icon size={22} strokeWidth={1.5} style={{ color: s.accent }} />
                    </div>
                  </div>
                  <div className="pt-2">
                    <div className="text-[10px] tracking-[0.3em] font-semibold mb-1 text-accent">{s.num}</div>
                    <h3 className="font-display text-2xl text-text mb-2">{s.label}.</h3>
                    <p className="text-sm text-muted leading-relaxed max-w-lg">{s.desc}</p>
                    <p className="text-xs text-accent/80 leading-relaxed max-w-lg mt-2">{s.detail}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
