import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Loader2, Search } from "lucide-react";
import clsx from "clsx";
import RiskBadge from "@/components/RiskBadge";
import { useApiCall } from "@/hooks/useApiCall";
import { ApiError, NetworkError, checkBlocklist } from "@/api/client";
import type { BlocklistCheckResponse } from "@/api/types";

function errorMessage(error: ApiError | NetworkError | Error, tc: (key: string) => string): string {
  if (error instanceof NetworkError) return tc("errors.network");
  if (error instanceof ApiError) return error.body.error;
  return tc("errors.generic");
}

export default function QuickSafetyCheck() {
  const { t } = useTranslation("quickSafetyCheck");
  const { t: tc } = useTranslation();
  const [indicator, setIndicator] = useState("");
  const { state, run } = useApiCall<BlocklistCheckResponse>();

  const handleCheck = () => {
    if (!indicator.trim()) return;
    run(() => checkBlocklist(indicator.trim()));
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-2xl font-bold text-ink">{t("title")}</h1>
      <p className="mt-1 text-ink-dim">{t("description")}</p>

      <div className="glass-card mt-6 rounded-xl p-6">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("inputLabel")}</span>
          <div className="flex gap-2">
            <input
              type="text"
              value={indicator}
              onChange={(e) => setIndicator(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCheck()}
              placeholder={t("inputPlaceholder")}
              className="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
            />
            <button
              type="button"
              onClick={handleCheck}
              disabled={state.status === "loading" || !indicator.trim()}
              className={clsx(
                "flex cursor-pointer items-center gap-2 rounded-md bg-brand px-4 py-2 text-sm font-medium text-white transition-opacity",
                (state.status === "loading" || !indicator.trim()) && "cursor-not-allowed opacity-50"
              )}
            >
              {state.status === "loading" ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Search className="h-4 w-4" aria-hidden="true" />
              )}
              {t("check")}
            </button>
          </div>
        </label>

        {state.status === "error" && (
          <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p>{errorMessage(state.error, tc)}</p>
          </div>
        )}

        {state.status === "success" && (
          <div className="mt-4 flex items-center justify-between rounded-lg bg-ink/5 p-4">
            <span className="text-sm text-ink">
              {state.data.threat_detected ? t("result.flagged") : t("result.clean")}
            </span>
            <RiskBadge level={state.data.threat_detected ? "high" : "low"} />
          </div>
        )}
      </div>
    </div>
  );
}
