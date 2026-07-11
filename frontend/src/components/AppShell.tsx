import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ShieldCheck } from "lucide-react";
import clsx from "clsx";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import DisclaimerBar from "@/components/DisclaimerBar";

// Grouped by theme, not appended in build order — detection tools first
// (things you check), then protection tools (things that watch out for
// you), then respond/follow-up tools (what you do once something's
// confirmed). A thin divider marks each group boundary in the rendered nav.
const NAV_GROUPS = [
  {
    items: [
      { to: "/media-verdict", key: "nav.mediaVerdict" },
      { to: "/document-check", key: "nav.documentCheck" },
      { to: "/check", key: "nav.checkLinkProfileCall" },
      { to: "/fraud-scanner", key: "nav.fraudScanner" },
      { to: "/quick-safety-check", key: "nav.quickSafetyCheck" },
    ],
  },
  {
    items: [
      { to: "/vault", key: "nav.vault" },
      { to: "/honeypot", key: "nav.honeypot" },
      { to: "/family-protection", key: "nav.familyProtection" },
    ],
  },
  {
    items: [
      { to: "/report-scam", key: "nav.reportScam" },
      { to: "/legal-recovery", key: "nav.legalRecovery" },
      { to: "/case-timeline", key: "nav.caseTimeline" },
      { to: "/privacy-consent", key: "nav.privacyConsent" },
      { to: "/news", key: "nav.newsAwareness" },
    ],
  },
] as const;

export default function AppShell() {
  const { t } = useTranslation();

  return (
    <div className="flex min-h-svh flex-col bg-canvas">
      <header className="glass-card sticky top-0 z-30 border-b border-border">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2 font-display text-lg font-bold text-ink">
            <ShieldCheck className="h-6 w-6 text-brand" aria-hidden="true" />
            {t("app.name")}
          </NavLink>

          <nav className="flex flex-wrap items-center gap-1" aria-label="Main">
            {NAV_GROUPS.map((group, groupIndex) => (
              <div key={groupIndex} className="flex flex-wrap items-center gap-1">
                {groupIndex > 0 && <span className="mx-1.5 h-4 w-px bg-border" aria-hidden="true" />}
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      clsx(
                        "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                        isActive
                          ? "bg-brand-dim text-brand"
                          : "text-ink-dim hover:bg-brand-dim/60 hover:text-ink"
                      )
                    }
                  >
                    {t(item.key)}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>

          <LanguageSwitcher />
        </div>
      </header>

      <DisclaimerBar />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}
