import { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight, Star } from 'lucide-react';

// Rotating customer quotes for the carousel.
const TESTIMONIALS = [
  {
    quote: 'SmartDecigen replaced my executive coach. The engine remembers my business better than I do — every check-in builds on the last one. My follow-through rate went from 30% to 80%.',
    author: 'Rahul M.',
    role: 'Founder, D2C skincare brand',
    result: 'Launched in 3 months instead of 9',
  },
  {
    quote: 'I was stuck in analysis paralysis for 6 months. One conversation with the journey engine gave me a direction, milestones, and a clear next action. Two weeks later, I had my first paying customer.',
    author: 'Priya K.',
    role: 'Solo founder, B2B SaaS',
    result: 'First customer in 14 days',
  },
  {
    quote: 'The autonomous agents are the real deal. I connected Gmail, Notion, and Slack. Now my sales agent follows up leads, my ops agent flags overdue tasks, and I wake up to a morning brief. It\'s like having a COO.',
    author: 'Vikram S.',
    role: 'CEO, 15-person agency',
    result: 'Saved 20 hours/week on ops',
  },
  {
    quote: 'The Record Room is what sold my investors. Every decision, every outcome, every dollar tracked. When they asked for due diligence, I exported the audit trail. They closed in 2 weeks.',
    author: 'Ananya D.',
    role: 'Founder, fintech startup',
    result: 'Seed round closed in 14 days',
  },
];

// Auto-advancing carousel of founder testimonials.
export default function TestimonialsCarousel() {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setIdx(i => (i + 1) % TESTIMONIALS.length), 5000);
    return () => clearInterval(id);
  }, []);

  const t = TESTIMONIALS[idx];
  return (
    <section id="testimonials" className="relative py-28 sm:py-36 bg-surface overflow-hidden">
      <div className="max-w-4xl mx-auto px-6 sm:px-10 text-center">
        <span className="inline-flex items-center gap-2 text-[11px] tracking-[0.26em] uppercase text-accent font-semibold mb-5">
          <span className="h-px w-8 bg-accent" />
          Testimonials
        </span>
        <h2 className="font-display text-4xl sm:text-5xl text-text tracking-tight mb-12">
          Founders who stopped guessing.
        </h2>

        <div className="relative bg-surface-2 rounded-3xl border border-hairline p-8 sm:p-12">
          <div className="flex justify-center gap-0.5 mb-6">
            {[...Array(5)].map((_, i) => <Star key={i} size={16} fill="#2F8F8A" stroke="#2F8F8A" />)}
          </div>
          <blockquote className="font-display text-xl sm:text-2xl text-text leading-relaxed max-w-2xl mx-auto">
            "{t.quote}"
          </blockquote>
          <div className="mt-8">
            <p className="text-sm font-medium text-text">{t.author}</p>
            <p className="text-xs text-muted">{t.role}</p>
          </div>
          <div className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-accent bg-accent/5 rounded-full px-3 py-1 border border-accent/10">
            {t.result}
          </div>
        </div>

        <div className="flex items-center justify-center gap-3 mt-8">
          <button onClick={() => setIdx(i => (i - 1 + TESTIMONIALS.length) % TESTIMONIALS.length)}
            className="w-10 h-10 rounded-xl border border-hairline flex items-center justify-center hover:bg-surface-2 transition-colors">
            <ChevronLeft size={16} />
          </button>
          <div className="flex gap-1.5">
            {TESTIMONIALS.map((_, i) => (
              <button key={i} onClick={() => setIdx(i)}
                className={`w-2 h-2 rounded-full transition-all ${i === idx ? 'bg-accent w-4' : 'bg-hairline'}`} />
            ))}
          </div>
          <button onClick={() => setIdx(i => (i + 1) % TESTIMONIALS.length)}
            className="w-10 h-10 rounded-xl border border-hairline flex items-center justify-center hover:bg-surface-2 transition-colors">
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </section>
  );
}
