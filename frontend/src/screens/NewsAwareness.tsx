import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Loader2, PlayCircle } from "lucide-react";
import { SUPPORTED_LANGUAGES } from "@/i18n";
import { useApiCall } from "@/hooks/useApiCall";
import { ApiError, NetworkError, getAnnualReport, getContentLibrary } from "@/api/client";
import type { AnnualReportResponse, ContentLibraryResponse } from "@/api/types";
import { humanizeEnum, translateTargetAudience } from "@/lib/format";

type Audience = "all" | "general" | "elderly";

function errorMessage(error: ApiError | NetworkError | Error, tc: (key: string) => string): string {
  if (error instanceof NetworkError) return tc("errors.network");
  if (error instanceof ApiError) return error.body.error;
  return tc("errors.generic");
}

export default function NewsAwareness() {
  const { t } = useTranslation("newsAwareness");
  const { t: tc, i18n } = useTranslation();
  const [videoLanguage, setVideoLanguage] = useState("all");
  const [audience, setAudience] = useState<Audience>("all");
  const { state: libraryState, run: runLibrary } = useApiCall<ContentLibraryResponse>();
  const { state: statsState, run: runStats } = useApiCall<AnnualReportResponse>();

  useEffect(() => {
    runStats(() => getAnnualReport());
  }, [runStats]);

  useEffect(() => {
    runLibrary(() =>
      getContentLibrary({
        language: videoLanguage,
        target_audience: audience === "all" ? undefined : audience,
      })
    );
  }, [runLibrary, videoLanguage, audience]);

  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-ink">{t("title")}</h1>
      <p className="mt-1 text-ink-dim">{t("description")}</p>

      {/* Item 81 tie-in: real, live network stats — not the video library itself,
          but the same "credibility asset" the News/Awareness brief calls for. */}
      <div className="glass-card mt-6 rounded-xl p-5">
        <h2 className="font-display text-sm font-semibold text-ink">{t("stats.heading")}</h2>

        {statsState.status === "loading" && (
          <p className="mt-2 flex items-center gap-1.5 text-sm text-ink-dim">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            {t("stats.loading")}
          </p>
        )}

        {statsState.status === "error" && (
          <p className="mt-2 flex items-center gap-1.5 text-sm text-risk-high">
            <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
            {errorMessage(statsState.error, tc)}
          </p>
        )}

        {statsState.status === "success" && (
          <>
            <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-lg bg-brand-dim p-3">
                <p className="text-2xl font-bold text-brand">
                  {statsState.data.total_heatmap_incidents_logged}
                </p>
                <p className="text-xs text-ink-dim">{t("stats.heatmapLabel")}</p>
              </div>
              <div className="rounded-lg bg-brand-dim p-3">
                <p className="text-2xl font-bold text-brand">
                  {statsState.data.total_b2b_threat_indicators_flagged}
                </p>
                <p className="text-xs text-ink-dim">{t("stats.b2bLabel")}</p>
              </div>
            </div>
            <p className="mt-3 text-xs text-ink-dim">{statsState.data.note}</p>
          </>
        )}
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("filters.languageLabel")}</span>
          <select
            value={videoLanguage}
            onChange={(e) => setVideoLanguage(e.target.value)}
            className="cursor-pointer rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
          >
            <option value="all">{t("filters.languageAll")}</option>
            {SUPPORTED_LANGUAGES.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("filters.audienceLabel")}</span>
          <select
            value={audience}
            onChange={(e) => setAudience(e.target.value as Audience)}
            className="cursor-pointer rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
          >
            <option value="all">{t("filters.audienceAll")}</option>
            <option value="general">{translateTargetAudience("general", i18n.language)}</option>
            <option value="elderly">{translateTargetAudience("elderly", i18n.language)}</option>
          </select>
        </label>
      </div>

      <div className="mt-4">
        {libraryState.status === "loading" && (
          <p className="flex items-center gap-1.5 text-sm text-ink-dim">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            {t("loading")}
          </p>
        )}

        {libraryState.status === "error" && (
          <p className="flex items-center gap-1.5 text-sm text-risk-high">
            <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
            {errorMessage(libraryState.error, tc)}
          </p>
        )}

        {libraryState.status === "success" && libraryState.data.videos.length === 0 && (
          <p className="text-sm text-ink-dim/80">{t("emptyState")}</p>
        )}

        {libraryState.status === "success" && libraryState.data.videos.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {libraryState.data.videos.map((video) => (
              <div key={video.id} className="glass-card flex flex-col gap-3 rounded-xl p-4">
                <div className="flex h-32 items-center justify-center rounded-lg bg-ink/5 text-ink-dim">
                  <PlayCircle className="h-8 w-8" aria-hidden="true" />
                </div>
                <h3 className="font-display text-sm font-semibold text-ink">{video.title}</h3>
                <div className="flex flex-wrap gap-1.5">
                  <span className="rounded-md bg-brand-dim px-2 py-1 text-xs font-medium text-brand">
                    {SUPPORTED_LANGUAGES.find((l) => l.code === video.lang)?.label ?? video.lang.toUpperCase()}
                  </span>
                  <span className="rounded-md bg-ink/5 px-2 py-1 text-xs text-ink-dim">
                    {translateTargetAudience(video.target_audience, i18n.language)}
                  </span>
                  {video.tags.map((tag) => (
                    <span key={tag} className="rounded-md bg-ink/5 px-2 py-1 text-xs text-ink-dim">
                      #{humanizeEnum(tag)}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
