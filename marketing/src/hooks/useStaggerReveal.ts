import { useEffect, useRef, type RefObject } from "react";
import { gsap } from "@/lib/motion";

interface StaggerRevealOptions {
  threshold?: number;
  duration?: number;
  stagger?: number;
  y?: number;
  /** Guarantees full visibility even if the observer never fires, GSAP throws, or a tween gets interrupted. */
  fallbackMs?: number;
}

/**
 * Reveal-on-scroll for a list of children, built so the animation can only ever
 * ADD polish — it can never be the only thing standing between content and
 * visibility. Three independent safety nets:
 *   1. try/catch around the GSAP call — a thrown error still forces full opacity.
 *   2. onComplete clears inline styles back to the CSS default (opacity: 1).
 *   3. A hard setTimeout forces visibility regardless of whether the
 *      IntersectionObserver ever fired, GSAP is broken, or the tab was
 *      throttled mid-animation.
 * prefers-reduced-motion skips the animation and renders at full opacity immediately.
 */
export function useStaggerReveal<T extends HTMLElement>({
  threshold = 0.2,
  duration = 0.75,
  stagger = 0.1,
  y = 28,
  fallbackMs = 2500,
}: StaggerRevealOptions = {}): RefObject<T | null> {
  const containerRef = useRef<T>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const targets = Array.from(container.children) as HTMLElement[];
    if (targets.length === 0) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let revealed = false;
    const forceVisible = () => {
      targets.forEach((el) => {
        el.style.opacity = "1";
        el.style.transform = "none";
      });
    };

    if (reducedMotion) {
      forceVisible();
      return;
    }

    const reveal = () => {
      if (revealed) return;
      revealed = true;
      try {
        gsap.fromTo(
          targets,
          { opacity: 0, y },
          { opacity: 1, y: 0, duration, ease: "kavachSettle", stagger, onComplete: forceVisible }
        );
      } catch (err) {
        console.error("useStaggerReveal: animation failed, forcing visible", err);
        forceVisible();
      }
    };

    let observer: IntersectionObserver | null = null;
    try {
      observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            reveal();
            observer?.disconnect();
          }
        }
      }, { threshold });
      observer.observe(container);
    } catch (err) {
      console.error("useStaggerReveal: IntersectionObserver failed, revealing immediately", err);
      reveal();
    }

    const fallbackTimer = window.setTimeout(() => {
      reveal();
      forceVisible();
    }, fallbackMs);

    return () => {
      observer?.disconnect();
      window.clearTimeout(fallbackTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return containerRef;
}
