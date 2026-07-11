import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  ScanFace,
  FileSearch,
  Link2,
  Search,
  ShieldQuestion,
  KeyRound,
  Bot,
  Users,
  Megaphone,
  Scale,
  History,
  ShieldCheck,
  Newspaper,
} from "lucide-react";

// Same three theme groups as AppShell's nav — detect, protect, respond —
// flattened into one grid here since Dashboard has no divider concept,
// but kept in the same group order for consistency.
const CARDS = [
  { to: "/media-verdict", key: "mediaVerdict", icon: ScanFace },
  { to: "/document-check", key: "documentCheck", icon: FileSearch },
  { to: "/check", key: "checkLinkProfileCall", icon: Link2 },
  { to: "/fraud-scanner", key: "fraudScanner", icon: Search },
  { to: "/quick-safety-check", key: "quickSafetyCheck", icon: ShieldQuestion },
  { to: "/vault", key: "vault", icon: KeyRound },
  { to: "/honeypot", key: "honeypot", icon: Bot },
  { to: "/family-protection", key: "familyProtection", icon: Users },
  { to: "/report-scam", key: "reportScam", icon: Megaphone },
  { to: "/legal-recovery", key: "legalRecovery", icon: Scale },
  { to: "/case-timeline", key: "caseTimeline", icon: History },
  { to: "/privacy-consent", key: "privacyConsent", icon: ShieldCheck },
  { to: "/news", key: "newsAwareness", icon: Newspaper },
] as const;

export default function Dashboard() {
  const { t } = useTranslation();

  return (
    <div>
      <h1 className="font-display text-3xl font-bold text-ink">{t("dashboard.heading")}</h1>
      <p className="mt-2 text-ink-dim">{t("dashboard.subheading")}</p>

      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <Link
              key={card.to}
              to={card.to}
              className="glass-card group relative flex flex-col gap-3 rounded-xl p-5 transition-transform hover:-translate-y-0.5"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-dim text-brand">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </div>
              <h2 className="font-display text-lg font-semibold text-ink">
                {t(`nav.${card.key}`)}
              </h2>
              <p className="text-sm text-ink-dim">{t(`dashboard.cards.${card.key}`)}</p>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
