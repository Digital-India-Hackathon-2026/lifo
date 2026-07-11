import { useTranslation } from "react-i18next";
import { translateRiskLevel } from "@/lib/format";

const RISK_STYLES: Record<string, string> = {
  low: "bg-risk-low-bg text-risk-low",
  medium: "bg-risk-medium-bg text-risk-medium",
  high: "bg-risk-high-bg text-risk-high",
};

/** Displays the backend's risk_level/severity value, translated via the closed enum table (see translateRiskLevel). */
export default function RiskBadge({ level }: { level: string }) {
  const { i18n } = useTranslation();
  return (
    <span
      className={
        "inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold " +
        (RISK_STYLES[level] ?? "bg-ink/5 text-ink-dim")
      }
    >
      {translateRiskLevel(level, i18n.language)}
    </span>
  );
}
