import { useTranslation } from "react-i18next";
import { ShieldAlert } from "lucide-react";

/** Always visible on every surface — non-negotiable per ARCHITECTURE.md. */
export default function DisclaimerBar() {
  const { t } = useTranslation();

  return (
    <div className="flex items-center gap-2 border-b border-border bg-brand-dim px-4 py-2 text-xs text-ink-dim sm:px-6">
      <ShieldAlert className="h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
      <p>{t("disclaimer")}</p>
    </div>
  );
}
