import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../ui/button';

// Fixed landing nav that solidifies on scroll.
export default function Navbar() {
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${scrolled ? 'bg-background/90 backdrop-blur-md border-b border-hairline' : 'bg-transparent'}`}>
      <div className="max-w-6xl mx-auto px-6 sm:px-10 lg:px-14 flex items-center justify-between h-16">
        <button onClick={() => navigate('/')} className="flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-text text-background font-display text-sm">S</span>
          <span className="font-display text-lg text-text hidden sm:inline">SmartDecigen</span>
        </button>
        <nav className="hidden md:flex items-center gap-6 text-sm text-muted">
          <a href="#how-it-works" className="hover:text-text transition-colors">How it works</a>
          <a href="#features" className="hover:text-text transition-colors">Features</a>
          <a href="#pricing" className="hover:text-text transition-colors">Pricing</a>
          <a href="#testimonials" className="hover:text-text transition-colors">Testimonials</a>
        </nav>
        <div className="flex items-center gap-3">
          <Button variant="ghost" className="rounded-xl text-sm" onClick={() => navigate('/auth')}>Sign in</Button>
          <Button className="rounded-xl text-sm" onClick={() => navigate('/auth')}>Start your company</Button>
        </div>
      </div>
    </header>
  );
}
