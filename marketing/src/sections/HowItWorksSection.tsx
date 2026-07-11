import { useEffect, useRef, useState } from "react";
import Magnet from "@/components/Magnet";
import ThreatGlyph from "@/components/ThreatGlyph";
import { gsap } from "@/lib/motion";
import { usePrefersReducedMotion } from "@/hooks/useMediaQuery";
import { useSectionInView } from "@/hooks/useSectionInView";
import { appUrl } from "@/lib/appLinks";

const STEPS = [
  {
    n: "01",
    variant: 0,
    label: "Send",
    body: "Upload a file, paste a transcript, or just talk to the honeypot.",
  },
  {
    n: "02",
    variant: 2,
    label: "Check",
    body: "Purpose-built models and rule-based checks run — locally where possible, GCP where it matters.",
  },
  {
    n: "03",
    variant: 4,
    label: "Decide",
    body: "A confidence score and a plain-language reason. The same disclaimer, every single time.",
  },
];

export default function HowItWorksSection() {
  const rowRef = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const [sectionRef, glyphsEnabled] = useSectionInView<HTMLElement>();
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    const row = rowRef.current;
    if (!row) return;
    const stepEls = row.querySelectorAll<HTMLElement>(".flow-step");
    const fills = row.querySelectorAll<HTMLElement>(".connector-fill");
    const pulses = row.querySelectorAll<HTMLElement>(".connector-pulse");

    const forceVisible = () => {
      stepEls.forEach((el) => {
        el.style.opacity = "1";
        el.style.transform = "none";
      });
      fills.forEach((el) => (el.style.transform = "scaleX(1)"));
    };

    if (reducedMotion) {
      forceVisible();
      return;
    }

    let revealed = false;
    const reveal = () => {
      if (revealed) return;
      revealed = true;
      try {
        const tl = gsap.timeline();
        tl.fromTo(
          stepEls,
          { opacity: 0, y: 20 },
          { opacity: 1, y: 0, duration: 0.65, ease: "kavachSettle", stagger: 0.16 }
        )
          .fromTo(
            fills,
            { scaleX: 0 },
            { scaleX: 1, duration: 0.5, ease: "kavachSettle", stagger: 0.16 },
            "-=0.35"
          )
          .call(() => {
            pulses.forEach((el, i) => {
              gsap.fromTo(
                el,
                { left: "0%", opacity: 0 },
                {
                  left: "100%",
                  opacity: 1,
                  duration: 1.3,
                  ease: "kavachDrift",
                  repeat: -1,
                  delay: i * 0.5,
                  onRepeat: () => gsap.set(el, { opacity: 0 }),
                  onStart: () => gsap.to(el, { opacity: 1, duration: 0.15 }),
                }
              );
            });
          });
      } catch (err) {
        console.error("HowItWorksSection: reveal animation failed, forcing visible", err);
        forceVisible();
      }
    };

    let observer: IntersectionObserver | null = null;
    try {
      observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.isIntersecting) {
              reveal();
              observer?.disconnect();
            }
          }
        },
        { threshold: 0.2 }
      );
      observer.observe(row);
    } catch {
      reveal();
    }

    const fallback = window.setTimeout(() => {
      reveal();
      forceVisible();
    }, 2500);

    return () => {
      observer?.disconnect();
      window.clearTimeout(fallback);
    };
  }, [reducedMotion]);

  const goToHoneypotDemo = () => {
    window.location.href = appUrl("/honeypot");
  };

  return (
    <section
      id="how-it-works"
      ref={sectionRef}
      className="grain relative w-full bg-ink px-5 py-24 sm:px-8 lg:px-14 lg:py-36"
    >
      <div className="mx-auto max-w-6xl">
        <span className="font-mono text-xs uppercase tracking-[0.16em] text-amber">
          05 — how it works
        </span>
        <h2 className="mt-4 max-w-[20ch] font-display text-4xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-5xl">
          Verdict, not vibes.
        </h2>

        <div ref={rowRef} className="mt-14 flex flex-col sm:flex-row sm:items-start">
          {STEPS.map((s, i) => (
            <div
              key={s.n}
              className="flex flex-1 sm:items-start"
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered((h) => (h === i ? null : h))}
            >
              <div className="group flow-step w-full border-t border-white/10 pt-6 transition-colors duration-300 hover:border-teal/40 sm:pr-6">
                <div className="flex items-center gap-3">
                  {glyphsEnabled ? (
                    <ThreatGlyph
                      variant={s.variant}
                      active={hovered === i}
                      restValue={0.4}
                      activeValue={0.05}
                      size={36}
                    />
                  ) : (
                    <div className="h-9 w-9 shrink-0 rounded-sm bg-ink-2" />
                  )}
                  <span className="font-mono text-xs uppercase tracking-[0.14em] text-teal transition-[text-shadow] duration-300 group-hover:[text-shadow:0_0_12px_rgba(143,230,218,0.7)]">
                    {s.n}
                  </span>
                </div>
                <h3 className="mt-2 font-display text-xl font-bold text-white transition-transform duration-300 group-hover:translate-x-1">
                  {s.label}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-white/70">{s.body}</p>
              </div>
              {i < STEPS.length - 1 && (
                <div className="relative mt-[9px] hidden h-px w-12 shrink-0 bg-white/10 sm:block lg:w-20">
                  <div className="connector-fill absolute inset-y-0 left-0 w-full origin-left scale-x-0 bg-teal/50" />
                  <div className="connector-pulse absolute -top-[3px] left-0 h-[7px] w-[7px] -translate-x-1/2 rounded-full bg-teal opacity-0 shadow-[0_0_8px_2px_rgba(143,230,218,0.55)]" />
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="mt-24 flex flex-col items-start gap-8 border-t border-white/10 pt-16 lg:flex-row lg:items-end lg:justify-between">
          <p className="max-w-[36ch] font-display text-3xl font-extrabold leading-tight tracking-tight text-white sm:text-4xl">
            Built for the moment someone almost sends the money.
          </p>

          <Magnet padding={90} magnetStrength={2.5} wrapperClassName="inline-block shrink-0">
            <button
              onClick={goToHoneypotDemo}
              className="rounded-sm border border-teal/40 bg-teal/10 px-7 py-4 font-mono text-sm uppercase tracking-[0.12em] text-white hover:bg-teal/20"
            >
              ↑ try the honeypot demo
            </button>
          </Magnet>
        </div>
      </div>
    </section>
  );
}
