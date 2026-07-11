import { useEffect, useRef } from "react";

/** Sets a --proximity CSS var (0→1) on the element based on cursor distance —
 *  for micro-interactions that respond continuously, not just on/off hover. */
export function useProximityGlow<T extends HTMLElement>(maxDist = 240) {
  const ref = useRef<T>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    const handleMove = (e: PointerEvent) => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        const rect = el.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const dist = Math.hypot(e.clientX - cx, e.clientY - cy);
        const proximity = Math.max(0, 1 - dist / maxDist);
        el.style.setProperty("--proximity", proximity.toFixed(3));
      });
    };
    window.addEventListener("pointermove", handleMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", handleMove);
      cancelAnimationFrame(raf);
    };
  }, [maxDist]);

  return ref;
}
