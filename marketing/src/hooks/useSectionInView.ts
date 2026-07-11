import { useEffect, useRef, useState } from "react";

/**
 * Bounds how many small decorative WebGL contexts (ThreatGlyph) can exist at
 * once — mobile Safari caps around 8 live contexts, and 5 glyphs per section ×
 * 3 sections all mounted permanently would sit right at that ceiling before
 * even counting the hero/honeypot scene. Generous rootMargin means glyphs stay
 * mounted through normal scroll, only unmounting (freeing their context) once
 * a section is genuinely far off-screen.
 */
export function useSectionInView<T extends HTMLElement>(rootMargin = "40% 0px 40% 0px") {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(true);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), {
      rootMargin,
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [rootMargin]);

  return [ref, inView] as const;
}
