import { CanvasLifecycleProvider } from "@/lib/CanvasLifecycle";
import NavRail from "@/components/NavRail";
import HeroSection from "@/sections/HeroSection";
import HoneypotSection from "@/sections/HoneypotSection";
import ProblemSection from "@/sections/ProblemSection";
import FeaturesSection from "@/sections/FeaturesSection";
import HowItWorksSection from "@/sections/HowItWorksSection";

function App() {
  return (
    <CanvasLifecycleProvider>
      <NavRail />
      <main className="bg-ink">
        <HeroSection />
        <HoneypotSection />
        <ProblemSection />
        <FeaturesSection />
        <HowItWorksSection />
        <footer className="border-t border-white/10 px-5 py-10 sm:px-8 lg:px-14">
          <div className="mx-auto flex max-w-6xl flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
            <span className="font-display text-lg font-extrabold tracking-tight text-white">
              Kavach
            </span>
            <p className="max-w-[52ch] font-mono text-[11px] uppercase leading-relaxed tracking-[0.08em] text-dim">
              Reduces risk, doesn't guarantee it. Always verify through a second, independent
              channel before sending money.
            </p>
          </div>
        </footer>
      </main>
    </CanvasLifecycleProvider>
  );
}

export default App;
