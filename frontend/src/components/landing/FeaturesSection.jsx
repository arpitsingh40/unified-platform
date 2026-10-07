import { Brain, Target, Users, BookOpen, Radar, ShieldCheck, ArrowRight, Zap, Wifi, History } from 'lucide-react';

// Feature card content for the six engine highlights.
const FEATURES = [
  {
    icon: Target,
    title: 'Journey Engine',
    desc: 'One conversation builds your company model — industry, constraints, fears, strategic forks. The engine shapes a direction with milestones, trade-offs, and success odds.',
    accent: '#2F8F8A',
    details: ['Digital twin extraction', 'Hypothesis tracking with probability updates', 'Milestone progress auto-detected'],
  },
  {
    icon: Brain,
    title: 'Decision Brain',
    desc: 'Upload your documents. Ask any question. The Brain retrieves from your company\'s own files using RAPTOR tree search — grounded answers with citations, never guesses.',
    accent: '#2F8F8A',
    details: ['Semantic document retrieval', 'Source-cited answers', 'Company-wide knowledge base'],
  },
  {
    icon: Users,
    title: '12 Autonomous Agents',
    desc: 'Strategy, Growth, Ops, Customer Success, Finance, Sales, Marketing — agents run on schedules, detect signals, execute through your tools, escalate to you.',
    accent: '#2F8F8A',
    details: ['L0-L5 authority gradient', 'Budget caps + kill switch', 'Verified execution evidence'],
  },
  {
    icon: Zap,
    title: 'Business OS',
    desc: 'Agents don\'t just detect problems — they fix them. Connected to your actual tools (Gmail, Slack, Stripe, Notion), executing autonomously every 15 minutes.',
    accent: '#2F8F8A',
    details: ['Auto-execute through 1,403 tools', 'Outcome verification', 'Founder approval inbox'],
  },
  {
    icon: BookOpen,
    title: '100+ Book Lenses',
    desc: 'Every turn, the cognition engine selects the most relevant reasoning modules from the best business books — applied silently before the LLM call, zero extra cost.',
    accent: '#2F8F8A',
    details: ['Kahneman · Tetlock · Munger · Taleb', 'Category-specific reasoning algorithms', 'Evidence-first learning'],
  },
  {
    icon: History,
    title: 'Record Room',
    desc: 'Every decision, execution, tool connection, agent action — unified audit trail. Query your company history like a database. Nothing is invisible.',
    accent: '#2F8F8A',
    details: ['25 event types tracked', 'Free-text search', '24h activity summary'],
  },
];

// Grid of feature cards describing the six engines.
export default function FeaturesSection() {
  return (
    <section id="features" className="relative py-28 sm:py-36 bg-surface-2 overflow-x-clip">
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <div className="absolute -top-40 -right-40 w-[800px] h-[800px] rounded-full opacity-25"
          style={{ background: 'radial-gradient(circle, hsl(var(--accent)/0.08) 0%, transparent 65%)' }} />
        <div className="absolute -bottom-40 -left-40 w-[600px] h-[600px] rounded-full opacity-20"
          style={{ background: 'radial-gradient(circle, hsl(var(--accent)/0.06) 0%, transparent 60%)' }} />
      </div>

      <div className="relative max-w-7xl mx-auto px-6 sm:px-10 lg:px-14">
        <div className="text-center max-w-2xl mx-auto mb-16 sm:mb-20">
          <span className="inline-flex items-center gap-2 text-[11px] tracking-[0.26em] uppercase text-accent font-semibold mb-5">
            <span className="h-px bg-accent w-8" />
            Not a chatbot
          </span>
          <h2 className="font-display text-4xl sm:text-5xl lg:text-[4rem] leading-[0.95] text-text tracking-tight">
            An organization<br />that happens to run on AI.
          </h2>
          <p className="mt-4 text-muted text-sm max-w-md mx-auto">
            Six engines. One company. The AI is the means — the organization is the product.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 sm:gap-6">
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div key={f.title}
                className="group relative bg-surface border border-hairline rounded-3xl p-7 transition-all duration-500 cursor-default overflow-hidden hover:-translate-y-1 hover:shadow-elevation-2">
                <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700"
                  style={{ background: `radial-gradient(ellipse at 50% 0%, ${f.accent}10 0%, transparent 70%)` }} />
                <div className="relative">
                  <div className="w-12 h-12 rounded-xl bg-surface-2 border border-hairline flex items-center justify-center mb-5">
                    <Icon size={20} strokeWidth={1.5} style={{ color: f.accent }} />
                  </div>
                  <h3 className="font-display text-xl text-text mb-2.5">{f.title}</h3>
                  <p className="text-sm text-muted leading-relaxed">{f.desc}</p>
                  <div className="overflow-hidden max-h-0 opacity-0 group-hover:max-h-40 group-hover:opacity-100 transition-all duration-300">
                    <div className="pt-4 mt-4 border-t border-hairline space-y-2">
                      {f.details.map((d) => (
                        <div key={d} className="flex items-center gap-2 text-xs text-muted">
                          <div className="w-1 h-1 rounded-full" style={{ backgroundColor: f.accent }} />
                          {d}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs font-medium mt-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                    style={{ color: f.accent }}>
                    <span>Details</span>
                    <ArrowRight size={12} strokeWidth={2} />
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
