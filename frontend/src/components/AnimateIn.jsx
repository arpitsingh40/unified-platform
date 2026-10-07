import { useInView } from '../hooks/useInView';

// Fade-and-slide wrapper that animates children in when scrolled into view.
export default function AnimateIn({ children, className = '', delay = 0 }) {
  const [ref, inView] = useInView(0.1);
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? 'translateY(0)' : 'translateY(30px)',
        transition: `opacity 0.7s ease-out, transform 0.7s ease-out`,
        transitionDelay: `${delay}s`,
      }}
    >
      {children}
    </div>
  );
}
