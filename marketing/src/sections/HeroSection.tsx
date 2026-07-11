import { useEffect, useRef, lazy, Suspense } from "react";
import { CanvasSlot } from "@/lib/CanvasLifecycle";
import SplitText from "@/components/SplitText";
import { gsap, ScrollTrigger } from "@/lib/motion";
import { usePrefersReducedMotion, useIsTouchDevice } from "@/hooks/useMediaQuery";

// Dynamic import: three.js + R3F + postprocessing only download once this
// section is about to become the active canvas slot, not on initial page load.
const SignalScannerScene = lazy(() => import("@/scenes/SignalScannerScene"));

const HeroPoster = () => (
  <div
    className="h-full w-full"
    style={{
      background:
        "radial-gradient(circle at 72% 55%, rgba(143,230,218,0.10), transparent 45%), #0e0e10",
    }}
  />
);

export default function HeroSection() {
  const reducedMotion = usePrefersReducedMotion();
  const isTouch = useIsTouchDevice();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!rootRef.current) return;
    const ctx = gsap.context(() => {
      gsap.fromTo(
        ".hero-footrow",
        { opacity: 0, y: 14 },
        { opacity: 1, y: 0, duration: 0.9, ease: "kavachSettle", delay: 0.15, stagger: 0.08 }
      );
    }, rootRef);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={rootRef} id="hero" className="relative h-screen w-full overflow-hidden">
      <CanvasSlot id="hero" placeholder={<HeroPoster />} className="absolute inset-0">
        <Suspense fallback={<HeroPoster />}>
          <SignalScannerScene reducedMotion={reducedMotion} />
        </Suspense>
      </CanvasSlot>

      {/* scrim: the shader is genuinely chaotic underneath — copy needs a readable backdrop
          regardless of what the noise field is doing at any given frame */}
      <div
        className="pointer-events-none absolute inset-0 z-10"
        style={{
          background:
            "linear-gradient(to top, rgba(14,14,16,0.92) 0%, rgba(14,14,16,0.68) 34%, rgba(14,14,16,0.08) 62%, rgba(14,14,16,0) 78%)",
        }}
      />

      <div className="pointer-events-none absolute inset-0 z-20 flex flex-col justify-between p-5 sm:p-8 lg:p-14">
        <div className="hero-footrow flex items-start justify-between gap-4">
          <span className="font-mono text-xs uppercase tracking-[0.16em] text-amber">
            Kavach / signal integrity
          </span>
          <span className="rounded-sm border border-white/15 bg-ink/60 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.1em] text-white/70">
            deepfake &amp; scam detection
          </span>
        </div>

        <div className="mt-auto max-w-[min(680px,62vw)]">
          <SplitText
            text="The noise lies. Your cursor doesn't."
            tag="h1"
            className="font-display text-[2.4rem] font-extrabold leading-[0.98] tracking-tight text-white sm:text-6xl lg:text-7xl"
            splitType="words"
            duration={0.9}
            ease="kavachSettle"
            delay={40}
            textAlign="left"
          />
          <p className="mt-4 max-w-[46ch] text-base leading-relaxed text-white/75">
            Kavach cuts through deepfakes, scam calls, and forged notices the same way this
            page does: {isTouch ? "drag" : "move your cursor"} to see through the static.
          </p>
        </div>

        <div className="hero-footrow flex items-end justify-between gap-4">
          <span className="font-mono text-xs uppercase tracking-[0.16em] text-white/60">
            01 — hero
          </span>
          <span className="text-right font-mono text-[11px] uppercase leading-tight tracking-[0.06em] text-white/60">
            {isTouch ? "drag to reveal signal" : "move cursor to reveal signal"}
          </span>
        </div>
      </div>
    </section>
  );
}

export function registerHeroScrollExit() {
  ScrollTrigger.create({
    trigger: "#hero",
    start: "top top",
    end: "bottom top",
    scrub: true,
    onUpdate: (self) => {
      gsap.set("#hero .hero-footrow", { opacity: 1 - self.progress * 0.8 });
    },
  });
}
