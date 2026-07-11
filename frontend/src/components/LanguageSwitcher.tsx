import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Languages } from "lucide-react";
import { SUPPORTED_LANGUAGES, type LanguageCode } from "@/i18n";

export default function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  // i18next's resolvedLanguage falls back to English once a language is missing
  // ANY configured namespace (hi/te only ship `common` so far, not `mediaVerdict`
  // yet) — correct for content, but the dropdown should always reflect what the
  // user actually picked, so its value is tracked separately from resolution.
  const [selected, setSelected] = useState<LanguageCode>(
    (i18n.language?.split("-")[0] as LanguageCode) || "en"
  );

  const handleChange = (code: LanguageCode) => {
    setSelected(code);
    i18n.changeLanguage(code);
  };

  return (
    <label className="flex items-center gap-1.5 text-sm text-ink-dim">
      <Languages className="h-4 w-4" aria-hidden="true" />
      <span className="sr-only">{t("language.label")}</span>
      <select
        value={selected}
        onChange={(e) => handleChange(e.target.value as LanguageCode)}
        className="cursor-pointer rounded-md border border-border bg-surface py-1 pl-1.5 pr-6 text-sm text-ink outline-none transition-colors hover:border-brand focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
      >
        {SUPPORTED_LANGUAGES.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.label}
          </option>
        ))}
      </select>
    </label>
  );
}
