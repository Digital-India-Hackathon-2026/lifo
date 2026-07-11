import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Loader2, Send, MapPin } from "lucide-react";
import clsx from "clsx";
import { useApiCall } from "@/hooks/useApiCall";
import { ApiError, NetworkError, getHeatmap, submitScamReport } from "@/api/client";
import type { HeatmapResponse, ScamReportResponse } from "@/api/types";

function errorMessage(error: ApiError | NetworkError | Error, tc: (key: string) => string): string {
  if (error instanceof NetworkError) return tc("errors.network");
  if (error instanceof ApiError) return error.body.error;
  return tc("errors.generic");
}

export default function ReportScam() {
  const { t } = useTranslation("reportScam");
  const { t: tc } = useTranslation();
  const [reporterId, setReporterId] = useState("");
  const [scamType, setScamType] = useState("");
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [description, setDescription] = useState("");

  const { state, run } = useApiCall<ScamReportResponse>();
  const { state: heatmapState, run: runHeatmap } = useApiCall<HeatmapResponse>();

  useEffect(() => {
    runHeatmap(() => getHeatmap());
  }, [runHeatmap]);

  const canSubmit = reporterId.trim() && scamType.trim() && lat.trim() && lng.trim() && description.trim();

  const handleSubmit = async () => {
    if (!canSubmit) return;
    const data = await run(() =>
      submitScamReport({
        reporter_id: reporterId,
        scam_type: scamType,
        location_lat: Number(lat),
        location_lng: Number(lng),
        description,
      })
    );
    if (data) {
      setDescription("");
      runHeatmap(() => getHeatmap());
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-2xl font-bold text-ink">{t("title")}</h1>
      <p className="mt-1 text-ink-dim">{t("description")}</p>

      <div className="glass-card mt-6 rounded-xl p-6">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("form.reporterIdLabel")}</span>
          <input
            type="text"
            value={reporterId}
            onChange={(e) => setReporterId(e.target.value)}
            placeholder={t("form.reporterIdPlaceholder")}
            className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
          />
        </label>

        <label className="mt-4 block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("form.scamTypeLabel")}</span>
          <input
            type="text"
            value={scamType}
            onChange={(e) => setScamType(e.target.value)}
            placeholder={t("form.scamTypePlaceholder")}
            className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
          />
        </label>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-ink-dim">{t("form.latLabel")}</span>
            <input
              type="number"
              value={lat}
              onChange={(e) => setLat(e.target.value)}
              placeholder="12.9716"
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-ink-dim">{t("form.lngLabel")}</span>
            <input
              type="number"
              value={lng}
              onChange={(e) => setLng(e.target.value)}
              placeholder="77.5946"
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
            />
          </label>
        </div>

        <label className="mt-4 block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("form.descriptionLabel")}</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder={t("form.descriptionPlaceholder")}
            className="w-full resize-none rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
          />
        </label>

        {state.status === "error" && (
          <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p>{errorMessage(state.error, tc)}</p>
          </div>
        )}

        {state.status === "success" && (
          <div className="mt-3 rounded-lg bg-brand-dim p-3 text-sm text-brand">{state.data.message}</div>
        )}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={state.status === "loading" || !canSubmit}
          className={clsx(
            "mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity",
            (state.status === "loading" || !canSubmit) && "cursor-not-allowed opacity-50"
          )}
        >
          {state.status === "loading" ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Send className="h-4 w-4" aria-hidden="true" />
          )}
          {state.status === "loading" ? t("form.submitting") : t("form.submit")}
        </button>
      </div>

      <div className="glass-card mt-5 rounded-xl p-6">
        <h2 className="font-display text-sm font-semibold text-ink">{t("heatmap.heading")}</h2>

        {heatmapState.status === "loading" && (
          <p className="mt-2 flex items-center gap-1.5 text-sm text-ink-dim">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            {t("heatmap.loading")}
          </p>
        )}

        {heatmapState.status === "success" && heatmapState.data.active_zones.length === 0 && (
          <p className="mt-2 text-sm text-ink-dim/80">{t("heatmap.empty")}</p>
        )}

        {heatmapState.status === "success" && heatmapState.data.active_zones.length > 0 && (
          <ul className="mt-3 flex flex-col gap-2">
            {heatmapState.data.active_zones.map((zone, i) => (
              <li key={i} className="flex items-center gap-2 rounded-lg bg-ink/5 p-2.5 text-sm">
                <MapPin className="h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
                <span className="font-medium text-ink">{zone.scam_type}</span>
                <span className="text-ink-dim">
                  {zone.lat.toFixed(3)}, {zone.lng.toFixed(3)}
                </span>
                <span className="ml-auto rounded-md bg-brand-dim px-2 py-0.5 text-xs text-brand">
                  {t("heatmap.weightLabel")}: {zone.weight}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
