import { useRef, useEffect, useCallback } from 'react';

// Tilts element in 3D based on cursor position
export function useTilt3D(maxTilt = 2.5) {
  const ref = useRef(null);
  const state = useRef({ isHovering: false });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onMove = (e) => {
      if (!state.current.isHovering) return;
      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = (e.clientX - cx) / (rect.width / 2);
      const dy = (e.clientY - cy) / (rect.height / 2);
      el.style.transform = `perspective(1000px) rotateX(${-dy * maxTilt}deg) rotateY(${dx * maxTilt}deg)`;
    };

    const onEnter = () => { state.current.isHovering = true; };
    const onLeave = () => {
      state.current.isHovering = false;
      el.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg)';
    };

    el.addEventListener('mousemove', onMove);
    el.addEventListener('mouseenter', onEnter);
    el.addEventListener('mouseleave', onLeave);
    return () => {
      el.removeEventListener('mousemove', onMove);
      el.removeEventListener('mouseenter', onEnter);
      el.removeEventListener('mouseleave', onLeave);
    };
  }, [maxTilt]);

  return ref;
}
