import { useState } from "react";
import DecryptedText from "@/components/DecryptedText";
import ThreatGlyph from "@/components/ThreatGlyph";
import { useStaggerReveal } from "@/hooks/useStaggerReveal";
import { useProximityGlow } from "@/hooks/useProximityGlow";
import { useSectionInView } from "@/hooks/useSectionInView";

const SURFACES = [
  {
    index: "00",
    variant: 0,
    title: "Media verdict",
    body: "Upload a video, photo, or voice clip. Get a confidence score and an anomaly marker — not a bare yes or no.",
    note: "ViT image/video model + wav2vec2-XLSR audio model, run locally",
  },
  {
    index: "01",
    variant: 2,
    title: "Document & notice checker",
    body: "OCR reads the notice, then checks it against real scam-phrase and payment-demand patterns.",
    note: "Cloud Vision OCR + rule-based scam/PII analysis",
  },
  {
    index: "02",
    variant: 4,
    title: "Digital arrest pattern check",
    body: "Paste a transcript or describe the call. Rule-based and explainable — every flag traces to a matched pattern.",
    note: "No model, no black box — deterministic pattern matcher",
  },
  {
    index: "03",
    variant: 3,
    title: "Family safe-word vault",
    body: "One household word, checked instantly. The word itself is never returned in any response, ever.",
    note: "PBKDF2-SHA256 salted hash, constant-time compare",
  },
  {
    index: "04",
    variant: 1,
    title: "Let AI handle it",
    body: "The honeypot above, in one line: keep the scammer talking while a persona extracts evidence in real time.",
    note: "faster-whisper → Gemini persona → Cloud TTS",
  },
];

function FeatureRow({
  s,
  indexOnRight,
  hovered,
  onEnter,
  onLeave,
  glyphsEnabled,
}: {
  s: (typeof SURFACES)[number];
  indexOnRight: boolean;
  hovered: boolean;
  onEnter: () => void;
  onLeave: () => void;
  glyphsEnabled: boolean;
}) {
  // Big index numeral brightens continuously as the cursor approaches, not just on hover —
  // a proximity-driven micro-interaction rather than a binary state.
  const numberRef = useProximityGlow<HTMLSpanElement>(260);

  return (
    <div
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      className="grid grid-cols-[1fr] items-baseline gap-x-8 border-t border-white/10 py-8 transition-colors duration-300 last:border-b hover:bg-white/[0.02] sm:grid-cols-[auto_1fr]"
    >
      <span
        ref={numberRef}
        style={{
          color: "color-mix(in srgb, var(--color-teal) calc(var(--proximity, 0) * 55%), rgba(255,255,255,0.1))",
          textShadow: "0 0 28px rgba(143,230,218, calc(var(--proximity, 0) * 0.55))",
        }}
        className={`font-mono text-6xl font-light sm:text-7xl ${
          indexOnRight ? "sm:order-2 sm:text-right" : "sm:order-1"
        }`}
      >
        {s.index}
      </span>
      <div className={indexOnRight ? "sm:order-1" : "sm:order-2"}>
        <div className="flex items-center gap-4">
          {glyphsEnabled ? (
            <ThreatGlyph
              variant={s.variant}
              active={hovered}
              restValue={0.45}
              activeValue={0.08}
              size={48}
            />
          ) : (
            <div className="h-12 w-12 shrink-0 rounded-sm bg-ink-2" />
          )}
          <h3 className="font-display text-2xl font-bold text-white sm:text-3xl">
            <DecryptedText
              text={s.title}
              animateOn="hover"
              speed={22}
              maxIterations={8}
              className="text-white"
              encryptedClassName="text-teal/60"
            />
          </h3>
        </div>
        <p className="mt-3 max-w-[56ch] text-[0.95rem] leading-relaxed text-white/70">{s.body}</p>
        <span className="mt-3 inline-block font-mono text-[11px] uppercase tracking-[0.1em] text-dim">
          {s.note}
        </span>
      </div>
    </div>
  );
}

export default function FeaturesSection() {
  const listRef = useStaggerReveal<HTMLDivElement>({ threshold: 0.15 });
  const [hovered, setHovered] = useState<number | null>(null);
  const [sectionRef, glyphsEnabled] = useSectionInView<HTMLElement>();

  return (
    <section
      id="features"
      ref={sectionRef}
      className="grain relative w-full bg-ink px-5 py-24 sm:px-8 lg:px-14 lg:py-36"
    >
      <div className="mx-auto max-w-6xl">
        <span className="font-mono text-xs uppercase tracking-[0.16em] text-teal">
          04 — the five surfaces
        </span>
        <h2 className="mt-4 max-w-[28ch] font-display text-4xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-5xl">
          One tool, five ways to check.
        </h2>

        <div className="mt-16">
          <div ref={listRef} className="flex flex-col">
            {SURFACES.map((s, i) => (
              <FeatureRow
                key={s.index}
                s={s}
                indexOnRight={i % 2 === 1}
                hovered={hovered === i}
                onEnter={() => setHovered(i)}
                onLeave={() => setHovered((h) => (h === i ? null : h))}
                glyphsEnabled={glyphsEnabled}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
