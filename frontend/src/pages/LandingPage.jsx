import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/landing/Navbar';
import HowItWorks from '../components/landing/HowItWorks';
import FeaturesSection from '../components/landing/FeaturesSection';
import TestimonialsCarousel from '../components/landing/TestimonialsCarousel';
import CTASection from '../components/landing/CTASection';
import PricingSection from '../components/landing/PricingSection';
import DemoSection from '../components/landing/DemoSection';
import Footer from '../components/landing/Footer';
import AnimateIn from '../components/AnimateIn';
import { Button } from '../components/ui/button';

// Draw interactive background particle canvas
function ParticleCanvas({ mousePos }) {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId, w, h;
    const resize = () => { w = canvas.width = window.innerWidth; h = canvas.height = window.innerHeight; };
    resize();
    window.addEventListener('resize', resize, { passive: true });
    const COUNT = 90;
    const particles = Array.from({ length: COUNT }, () => ({
      x: Math.random() * w, y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
      r: Math.random() * 2 + 0.5,
      baseVx: (Math.random() - 0.5) * 0.3, baseVy: (Math.random() - 0.5) * 0.3,
    }));
    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      const mx = mousePos?.current?.x ?? -1000;
      const my = mousePos?.current?.y ?? -1000;
      for (const p of particles) {
        const dx = p.x - mx, dy = p.y - my;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 200) {
          const force = (200 - dist) / 200;
          p.vx += (dx / dist) * force * 0.02;
          p.vy += (dy / dist) * force * 0.02;
        }
        p.vx += (p.baseVx - p.vx) * 0.01;
        p.vy += (p.baseVy - p.vy) * 0.01;
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = w; if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h; if (p.y > h) p.y = 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = 'hsl(var(--accent) / 0.15)';
        ctx.fill();
      }
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const a = particles[i], b = particles[j];
          const d = Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
          if (d < 100) {
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.strokeStyle = `hsl(var(--accent) / ${0.06 * (1 - d / 100)})`;
            ctx.stroke();
          }
        }
      }
      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => { cancelAnimationFrame(animId); window.removeEventListener('resize', resize); };
  }, [mousePos]);
  return <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" />;
}

// Show headline stats below the hero
const StatsBar = () => (
  <div className="relative max-w-4xl mx-auto px-6 sm:px-10 pb-20">
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {[
        { value: '100+', label: 'Decision lenses' },
        { value: '1,403', label: 'Tool integrations' },
        { value: '12', label: 'Autonomous agents' },
        { value: '24/7', label: 'Company operations' },
      ].map(s => (
        <div key={s.label} className="text-center">
          <p className="font-display text-3xl text-accent">{s.value}</p>
          <p className="text-xs text-muted mt-1">{s.label}</p>
        </div>
      ))}
    </div>
  </div>
);

// Public marketing landing page
export default function LandingPage() {
  const navigate = useNavigate();
  const mousePos = useRef({ x: -1000, y: -1000 });
  useEffect(() => {
    const onMove = (e) => { mousePos.current = { x: e.clientX, y: e.clientY }; };
    window.addEventListener('mousemove', onMove, { passive: true });
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  return (
    <div className="paper min-h-screen bg-background overflow-x-clip">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-accent/30 to-transparent" />

      <ParticleCanvas mousePos={mousePos} />

      <Navbar />

      {/* Hero */}
      <section className="relative min-h-[90vh] flex flex-col items-center justify-center pt-20 pb-32">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,var(--accent-color,hsla(186,55%,38%,0.06)),transparent_60%)]" style={{'--accent-color':'hsla(186,55%,38%,0.06)'}} />
        <div className="relative max-w-4xl mx-auto px-6 sm:px-10 text-center">
          <div className="inline-flex items-center gap-2 text-xs text-accent mb-8 rounded-full border border-accent/20 px-4 py-1.5">
            Autonomous Executive Organization
          </div>
          <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl text-text tracking-tight leading-[1.1]">
            Your company.<br />
            <span className="text-accent">Running on autopilot</span>.
          </h1>
          <p className="mt-6 text-lg sm:text-xl text-muted max-w-2xl mx-auto leading-relaxed">
            One conversation builds your company model. 12 autonomous agents run it. You steer.
          </p>
          <div className="mt-10 flex flex-col items-center gap-3">
            {import.meta.env.VITE_TARGET === 'web' ? (
              <>
                <a href="https://github.com/arpitsingh40/unified-platform/releases" target="_blank" rel="noreferrer"
                  className="inline-flex items-center justify-center rounded-xl h-12 px-8 text-base font-medium bg-accent hover:bg-accent/90 text-white">
                  Download FORGE for Windows
                </a>
                <p className="text-xs text-muted">Execution runs locally on your machine. Only LLM leaves your device.</p>
                <Button onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}
                  variant="outline" className="rounded-xl h-10 px-6 text-sm">
                  See how it works
                </Button>
              </>
            ) : (
              <div className="flex items-center justify-center gap-4 flex-wrap">
                <Button onClick={() => navigate('/auth')}
                  className="rounded-xl h-12 px-8 text-base font-medium bg-accent hover:bg-accent/90 text-white">
                  Start your company
                </Button>
                <Button onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}
                  variant="outline" className="rounded-xl h-12 px-8 text-base">
                  See how it works
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2">
          <div className="w-5 h-8 rounded-full border-2 border-accent/30 flex items-start justify-center p-1">
            <div className="w-1 h-2 rounded-full bg-accent/60 animate-bounce-y" />
          </div>
        </div>
      </section>

      <AnimateIn><StatsBar /></AnimateIn>
      <AnimateIn delay={0.1}><HowItWorks /></AnimateIn>
      <AnimateIn delay={0.15}><FeaturesSection /></AnimateIn>
      <AnimateIn delay={0.2}><DemoSection /></AnimateIn>
      {import.meta.env.VITE_TARGET !== 'web' && <AnimateIn delay={0.25}><TestimonialsCarousel /></AnimateIn>}
      {import.meta.env.VITE_TARGET !== 'web' && <AnimateIn delay={0.3}><PricingSection /></AnimateIn>}
      <AnimateIn delay={0.35}><CTASection /></AnimateIn>
      <Footer />
    </div>
  );
}
