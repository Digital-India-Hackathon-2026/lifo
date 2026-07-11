import { useEffect, useRef, lazy, Suspense } from "react";
import { CanvasSlot } from "@/lib/CanvasLifecycle";
import type { SwarmDrivers } from "@/scenes/HoneypotSwarmScene";
import Magnet from "@/components/Magnet";
import SplitText from "@/components/SplitText";
import { gsap } from "@/lib/motion";
import { usePrefersReducedMotion, useIsTouchDevice } from "@/hooks/useMediaQuery";
import { appUrl } from "@/lib/appLinks";

// Dynamic import: three.js + R3F only download once this section is about to
// become the active canvas slot, not on initial page load.
const HoneypotSwarmScene = lazy(() => import("@/scenes/HoneypotSwarmScene"));

const HoneypotPoster = () => (
  <div
    className="h-full w-full"
    style={{
      background:
        "radial-gradient(circle at 78% 62%, rgba(181,73,58,0.10), transparent 45%), #0e0e10",
    }}
  />
);

export default function HoneypotSection() {
  const reducedMotion = usePrefersReducedMotion();
  const isTouch = useIsTouchDevice();
  const canvasWrapRef = useRef<HTMLDivElement>(null);
  const ctaRef = useRef<HTMLButtonElement>(null);
  const driversRef = useRef<SwarmDrivers>({ ctaWorldPos: { x: 260, y: -80 }, pullStrength: 0 });

  useEffect(() => {
    const measure = () => {
      if (!canvasWrapRef.current || !ctaRef.current) return;
      const canvasRect = canvasWrapRef.current.getBoundingClientRect();
      const ctaRect = ctaRef.current.getBoundingClientRect();
      const domX = ctaRect.left + ctaRect.width / 2 - canvasRect.left;
      const domY = ctaRect.top + ctaRect.height / 2 - canvasRect.top;
      driversRef.current.ctaWorldPos.x = domX - canvasRect.width / 2;
      driversRef.current.ctaWorldPos.y = -(domY - canvasRect.height / 2);
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (canvasWrapRef.current) ro.observe(canvasWrapRef.current);
    window.addEventListener("scroll", measure, { passive: true });
    return () => {
      ro.disconnect();
      window.removeEventListener("scroll", measure);
    };
  }, []);

  const handlePull = (strength: number) => {
    driversRef.current.pullStrength = strength;
  };

  const handleTouchTap = () => {
    if (!isTouch) return;
    // no persistent hover on touch — script the "closing net" as a scripted pulse instead
    gsap.fromTo(
      driversRef.current,
      { pullStrength: 0 },
      { pullStrength: 1, duration: 0.5, ease: "kavachSpring", yoyo: true, repeat: 1 }
    );
  };

  // Routing only — handleTouchTap's shader-pulse animation above is untouched and still
  // fires on tap; this just adds the actual navigation the button never had.
  const handleCtaClick = () => {
    handleTouchTap();
    window.location.href = appUrl("/honeypot");
  };

  return (
    <section id="honeypot" className="relative min-h-screen w-full overflow-hidden">
      <div ref={canvasWrapRef} className="absolute inset-0">
        <CanvasSlot id="honeypot" placeholder={<HoneypotPoster />} className="absolute inset-0">
          <Suspense fallback={<HoneypotPoster />}>
            <HoneypotSwarmScene
              particleCount={isTouch ? 2000 : 5000}
              drivers={driversRef.current}
              reducedMotion={reducedMotion}
            />
          </Suspense>
        </CanvasSlot>
      </div>

      {/* scrim: same fix as the hero — the dense particle/line mesh behind the
          copy needs a readable backdrop. Anchored top-left (not a pure left-right
          gradient) so it holds up whether the layout is side-by-side (desktop)
          or stacked (mobile, where text spans full width above the CTA). */}
      <div
        className="pointer-events-none absolute inset-0 z-[5]"
        style={{
          background:
            "radial-gradient(ellipse 90% 90% at 18% 22%, rgba(14,14,16,0.88) 0%, rgba(14,14,16,0.6) 32%, rgba(14,14,16,0.12) 55%, rgba(14,14,16,0) 72%)",
        }}
      />

      <div className="relative z-10 mx-auto flex h-full min-h-screen max-w-6xl flex-col justify-center gap-10 p-5 sm:p-8 lg:flex-row lg:items-center lg:gap-24 lg:p-14">
        <div className="max-w-[46ch] lg:w-2/5">
          <span className="font-mono text-xs uppercase tracking-[0.16em] text-rust">
            02 — honeypot
          </span>
          <SplitText
            text="Let the scammer talk to us instead."
            tag="h2"
            className="mt-3 font-display text-4xl font-extrabold leading-[1.02] tracking-tight text-white sm:text-5xl"
            splitType="words"
            duration={0.8}
            ease="kavachSettle"
            delay={35}
            textAlign="left"
            threshold={0.3}
          />
          <p className="mt-4 leading-relaxed text-white/75">
            Every node in that field is a live signal — a call, a message, a pattern our
            persona is quietly working. Approach the trap and watch it close.
          </p>
        </div>

        <div className="flex flex-1 items-center justify-end lg:justify-center">
          <Magnet
            padding={140}
            magnetStrength={2.2}
            onPull={handlePull}
            wrapperClassName="inline-block"
          >
            <button
              ref={ctaRef}
              onClick={handleCtaClick}
              className="rounded-sm border border-rust/40 bg-rust/10 px-7 py-4 font-mono text-sm uppercase tracking-[0.12em] text-white backdrop-blur-sm hover:bg-rust/20"
            >
              Let AI handle it
            </button>
          </Magnet>
        </div>
      </div>
    </section>
  );
}
