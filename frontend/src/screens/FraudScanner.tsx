import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Loader2, Search } from "lucide-react";
import clsx from "clsx";
import RiskBadge from "@/components/RiskBadge";
import { useApiCall } from "@/hooks/useApiCall";
import { ApiError, NetworkError, SCAM_DETECTORS, checkScam, type ScamDetector } from "@/api/client";
import type { ScamCheckResponse } from "@/api/types";

function errorMessage(error: ApiError | NetworkError | Error, tc: (key: string) => string): string {
  if (error instanceof NetworkError) return tc("errors.network");
  if (error instanceof ApiError) return error.body.error;
  return tc("errors.generic");
}

export default function FraudScanner() {
  const { t } = useTranslation("fraudScanner");
  const { t: tc } = useTranslation();
  const [detector, setDetector] = useState<ScamDetector>(SCAM_DETECTORS[0]);
  const [input, setInput] = useState("");
  const { state, run, reset } = useApiCall<ScamCheckResponse>();

  const handleSubmit = () => {
    if (!input.trim()) return;
    run(() => checkScam(detector, { transcript: input, email_body: input }));
  };

  const handleDetectorChange = (value: ScamDetector) => {
    setDetector(value);
    reset();
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-2xl font-bold text-ink">{t("title")}</h1>
      <p className="mt-1 text-ink-dim">{t("description")}</p>

      <div className="glass-card mt-6 rounded-xl p-6">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("detectorLabel")}</span>
          <select
            value={detector}
            onChange={(e) => handleDetectorChange(e.target.value as ScamDetector)}
            className="w-full cursor-pointer rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
          >
            {SCAM_DETECTORS.map((d) => (
              <option key={d} value={d}>
                {t(`detectors.${d}`)}
              </option>
            ))}
          </select>
        </label>

        <label className="mt-4 block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("inputLabel")}</span>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={5}
            placeholder={t("inputPlaceholder")}
            className="w-full resize-none rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
          />
        </label>

        {state.status === "error" && (
          <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p>{errorMessage(state.error, tc)}</p>
          </div>
        )}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={state.status === "loading" || !input.trim()}
          className={clsx(
            "mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity",
            (state.status === "loading" || !input.trim()) && "cursor-not-allowed opacity-50"
          )}
        >
          {state.status === "loading" ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Search className="h-4 w-4" aria-hidden="true" />
          )}
          {state.status === "loading" ? t("scanning") : t("scan")}
        </button>
      </div>

      {state.status === "success" && (
        <div className="glass-card mt-5 rounded-xl p-6">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-ink-dim">{t("result.riskLabel")}</span>
            <RiskBadge level={state.data.risk_level} />
          </div>

          <div className="mt-4">
            <span className="text-sm font-medium text-ink-dim">{t("result.flagsLabel")}</span>
            {state.data.flags.length === 0 ? (
              <p className="mt-1 text-sm text-ink-dim/80">{t("result.noFlags")}</p>
            ) : (
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {state.data.flags.map((flag, i) => (
                  <li key={i} className="rounded-md bg-risk-high-bg px-2 py-1 text-xs text-risk-high">
                    {flag}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {"confidence_score" in state.data && (
            <p className="mt-3 text-xs text-ink-dim">
              {t("result.confidenceLabel")}: {(state.data.confidence_score * 100).toFixed(0)}%
            </p>
          )}

          {"mca_check_note" in state.data && (
            <div className="mt-3 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">{state.data.mca_check_note}</div>
          )}

          {"app_registry_status" in state.data && (
            <p className="mt-3 text-xs text-ink-dim">
              {t("result.appRegistryLabel")}: {state.data.app_registry_status}
            </p>
          )}

          {"escalation_path" in state.data && (
            <>
              <div className="mt-3 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
                {state.data.legal_escalation}
              </div>
              <div className="mt-3">
                <span className="text-sm font-medium text-ink-dim">{t("result.actionsLabel")}</span>
                <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm text-ink">
                  {state.data.immediate_actions.map((action, i) => (
                    <li key={i}>{action}</li>
                  ))}
                </ul>
              </div>
              <p className="mt-3 text-xs text-ink-dim">{state.data.note}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
