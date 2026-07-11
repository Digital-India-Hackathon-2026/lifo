import { useEffect, useRef } from "react";
import { gsap } from "@/lib/motion";
import { useScrollSpy } from "@/hooks/useScrollSpy";
import { usePrefersReducedMotion } from "@/hooks/useMediaQuery";

const SECTIONS = [
  { id: "hero", label: "hero" },
  { id: "honeypot", label: "honeypot" },
  { id: "problem", label: "why" },
  { id: "features", label: "surfaces" },
  { id: "how-it-works", label: "how" },
];

export default function NavRail() {
  const ids = SECTIONS.map((s) => s.id);
  const active = useScrollSpy(ids);
  const dotRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    const target = itemRefs.current[active];
    if (!target || !dotRef.current) return;
    gsap.to(dotRef.current, {
      y: target.offsetTop,
      duration: reducedMotion ? 0 : 0.5,
      ease: "kavachSettle",
    });
  }, [active, reducedMotion]);

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth" });
  };

  return (
    <nav
      aria-label="Section navigation"
      className="fixed right-4 top-1/2 z-40 hidden -translate-y-1/2 lg:right-6 lg:block"
    >
      <div className="relative flex flex-col gap-5 border-r border-white/10 pr-4">
        <div
          ref={dotRef}
          className="absolute -right-[calc(1rem+1px)] top-0 h-4 w-px bg-teal"
          aria-hidden="true"
        />
        {SECTIONS.map((s, i) => (
          <button
            key={s.id}
            ref={(el) => {
              itemRefs.current[s.id] = el;
            }}
            onClick={() => scrollTo(s.id)}
            className="group flex items-center justify-end gap-2 text-right"
            aria-current={active === s.id ? "true" : undefined}
          >
            <span
              className={`font-mono text-[10px] uppercase tracking-[0.1em] underline-offset-4 transition-colors duration-300 ${
                active === s.id
                  ? "text-white"
                  : "text-white/35 group-hover:text-white/45 group-hover:underline group-hover:decoration-white/30"
              }`}
            >
              {s.label}
            </span>
            <span
              className={`font-mono text-[10px] ${active === s.id ? "text-teal" : "text-white/25"}`}
            >
              0{i + 1}
            </span>
          </button>
        ))}
      </div>
    </nav>
  );
}
