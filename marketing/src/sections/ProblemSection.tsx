import { useState } from "react";
import DecryptedText from "@/components/DecryptedText";
import ThreatGlyph from "@/components/ThreatGlyph";
import { useStaggerReveal } from "@/hooks/useStaggerReveal";
import { useSectionInView } from "@/hooks/useSectionInView";

const THREATS = [
  {
    label: "VOICE",
    body: "AI-cloned calls asking for emergency money, tuned to sound like someone you trust.",
  },
  {
    label: "VIDEO",
    body: "Deepfake endorsements and manipulated clips built on real faces.",
  },
  {
    label: "DOCUMENT",
    body: "Forged notices carrying real letterheads and invented urgency.",
  },
  {
    label: "IDENTITY",
    body: "Fake social profiles impersonating relatives, officers, or officials.",
  },
  {
    label: "PRESSURE",
    body: "“Digital arrest” calls built entirely on manufactured panic.",
  },
];

export default function ProblemSection() {
  const listRef = useStaggerReveal<HTMLDivElement>({ y: 24, stagger: 0.09, duration: 0.7 });
  const [hovered, setHovered] = useState<number | null>(null);
  const [sectionRef, glyphsEnabled] = useSectionInView<HTMLElement>();

  return (
    <section
      id="problem"
      ref={sectionRef}
      className="grain relative w-full overflow-hidden bg-ink px-5 py-24 sm:px-8 lg:px-14 lg:py-36"
    >
      {/* giant watermark numeral — the same device Features uses, so the two
          sections read as one system rather than two different sites */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute -left-4 top-8 select-none font-mono text-[13rem] font-light leading-none text-white/[0.03] sm:text-[18rem]"
      >
        03
      </span>

      <div className="relative mx-auto grid max-w-6xl gap-16 lg:grid-cols-[1.1fr_0.9fr] lg:gap-24">
        <div>
          <span className="font-mono text-xs uppercase tracking-[0.16em] text-amber">
            03 — why this exists
          </span>
          <h2 className="mt-4 font-display text-4xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-5xl">
            <DecryptedText
              text="It doesn't look like a scam anymore."
              animateOn="view"
              sequential
              revealDirection="start"
              speed={28}
              maxIterations={14}
              className="text-white"
              encryptedClassName="text-white/30"
            />
          </h2>
          <p className="mt-6 max-w-[52ch] text-base leading-relaxed text-white/75">
            Voice clones ask for money in a familiar tone. Videos put real faces on fake
            endorsements. Notices carry real government letterheads and fake deadlines. The
            senior in your family is the target — not the person reading this page.
          </p>
        </div>

        <div className="lg:pt-14">
          <div ref={listRef} className="flex flex-col">
            {THREATS.map((t, i) => (
              <div
                key={t.label}
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered((h) => (h === i ? null : h))}
                className={`flex items-center gap-4 border-t border-white/10 py-5 transition-colors duration-300 hover:bg-white/[0.02] ${
                  i === THREATS.length - 1 ? "border-b" : ""
                }`}
              >
                {glyphsEnabled ? (
                  <ThreatGlyph variant={i} active={hovered === i} />
                ) : (
                  <div className="h-14 w-14 shrink-0 rounded-sm bg-ink-2" />
                )}
                <div>
                  <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-rust">
                    {t.label}
                  </span>
                  <p className="mt-1.5 text-sm leading-relaxed text-white/70">{t.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
