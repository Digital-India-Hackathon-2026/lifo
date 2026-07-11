import { useTranslation } from "react-i18next";
import { translateVerdict } from "@/lib/format";

const GOOD_VERDICTS = new Set(["real", "genuine"]);

/** Displays the backend's verdict value, translated via the closed enum table (see translateVerdict). */
export default function VerdictBadge({ verdict }: { verdict: string }) {
  const { i18n } = useTranslation();
  const good = GOOD_VERDICTS.has(verdict);
  return (
    <span
      className={
        "inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold " +
        (good ? "bg-risk-low-bg text-risk-low" : "bg-risk-high-bg text-risk-high")
      }
    >
      {translateVerdict(verdict, i18n.language)}
    </span>
  );
}
