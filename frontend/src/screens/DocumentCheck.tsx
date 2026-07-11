import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, AlertTriangle, RotateCcw, FileWarning, ChevronDown, ChevronUp } from "lucide-react";
import clsx from "clsx";
import FileDropzone from "@/components/FileDropzone";
import RiskBadge from "@/components/RiskBadge";
import { useApiCall } from "@/hooks/useApiCall";
import { useReport } from "@/context/ReportContext";
import { classifyDocument, ApiError, NetworkError } from "@/api/client";
import type { ClassifyDocumentResponse } from "@/api/types";
import { humanizeEnum } from "@/lib/format";

const ACCEPT = "image/jpeg,image/png,image/webp,image/bmp";
const MAX_BYTES = 10 * 1024 * 1024;
const RISKY = new Set(["medium", "high"]);

export default function DocumentCheck() {
  const { t } = useTranslation("documentCheck");
  const { t: tc } = useTranslation();
  const { openReport } = useReport();
  const [file, setFile] = useState<File | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [ocrExpanded, setOcrExpanded] = useState(false);
  const { state, run, reset } = useApiCall<ClassifyDocumentResponse>();

  const isLoading = state.status === "loading";

  const handleFileSelected = (selected: File | null) => {
    setClientError(null);
    if (selected && selected.size > MAX_BYTES) {
      setClientError(t("errors.tooLarge"));
      setFile(null);
      return;
    }
    setFile(selected);
  };

  const handleAnalyze = () => {
    if (!file) return;
    run(() => classifyDocument(file));
  };

  const handleReset = () => {
    setFile(null);
    setClientError(null);
    setOcrExpanded(false);
    reset();
  };

  const handleFileReport = () => {
    if (state.status !== "success") return;
    openReport({
      // The backend doesn't expose which indicator types are "scam" vs
      // "payment" via this endpoint (that split is internal), so every
      // detected type is forwarded as matched_patterns — honest given what's
      // actually available here, not a guess at the internal split.
      matched_patterns: state.data.scam_indicators.map((i) => i.type),
    });
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-2xl font-bold text-ink">{t("title")}</h1>
      <p className="mt-1 text-ink-dim">{t("description")}</p>

      <div className="mt-6">
        {state.status !== "success" && (
          <>
            <FileDropzone
              accept={ACCEPT}
              hint={t("dropzone.hint")}
              prompt={t("dropzone.prompt")}
              file={file}
              onFileSelected={handleFileSelected}
              disabled={isLoading}
            />

            {clientError && (
              <p className="mt-2 flex items-center gap-1.5 text-sm text-risk-high">
                <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                {clientError}
              </p>
            )}

            {state.status === "error" && (
              <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <div>
                  <p className="font-medium">
                    {state.error instanceof NetworkError
                      ? tc("errors.network")
                      : state.error instanceof ApiError
                        ? state.error.body.error
                        : tc("errors.generic")}
                  </p>
                  {state.error instanceof ApiError &&
                    typeof state.error.body.detail === "string" && (
                      <p className="mt-0.5 text-risk-high/80">{state.error.body.detail}</p>
                    )}
                </div>
              </div>
            )}

            <button
              type="button"
              onClick={handleAnalyze}
              disabled={!file || isLoading}
              className={clsx(
                "mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity",
                (!file || isLoading) && "cursor-not-allowed opacity-50"
              )}
            >
              {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              {isLoading ? t("loading") : t("actions.analyze")}
            </button>
          </>
        )}

        {state.status === "success" && (
          <div className="glass-card rounded-xl p-6">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-ink-dim">{t("result.riskLabel")}</span>
              <RiskBadge level={state.data.risk_level} />
            </div>

            <div className="mt-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-ink-dim">{t("result.ocrTextLabel")}</span>
                <button
                  type="button"
                  onClick={() => setOcrExpanded((v) => !v)}
                  className="flex cursor-pointer items-center gap-1 text-xs font-medium text-brand hover:underline"
                >
                  {ocrExpanded ? (
                    <>
                      <ChevronUp className="h-3.5 w-3.5" /> {t("result.showLess")}
                    </>
                  ) : (
                    <>
                      <ChevronDown className="h-3.5 w-3.5" /> {t("result.showFullText")}
                    </>
                  )}
                </button>
              </div>
              <pre
                className={clsx(
                  "mt-1.5 overflow-y-auto whitespace-pre-wrap rounded-lg bg-ink/5 p-3 font-mono text-xs text-ink",
                  ocrExpanded ? "max-h-96" : "max-h-24"
                )}
              >
                {state.data.ocr_text}
              </pre>
            </div>

            <div className="mt-4">
              <span className="text-sm font-medium text-ink-dim">{t("result.piiLabel")}</span>
              {state.data.pii_detected.length === 0 ? (
                <p className="mt-1 text-sm text-ink-dim/80">{t("result.noPii")}</p>
              ) : (
                <ul className="mt-1.5 flex flex-wrap gap-1.5">
                  {state.data.pii_detected.map((pii, i) => (
                    <li
                      key={i}
                      className="rounded-md bg-risk-medium-bg px-2 py-1 font-mono text-xs text-risk-medium"
                    >
                      {humanizeEnum(pii.type)}: {pii.masked_value}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="mt-4">
              <span className="text-sm font-medium text-ink-dim">
                {t("result.scamIndicatorsLabel")}
              </span>
              {state.data.scam_indicators.length === 0 ? (
                <p className="mt-1 text-sm text-ink-dim/80">{t("result.noIndicators")}</p>
              ) : (
                <ul className="mt-1.5 space-y-1.5">
                  {state.data.scam_indicators.map((ind, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 rounded-lg bg-risk-high-bg p-2 text-xs text-risk-high"
                    >
                      <FileWarning className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                      <span>
                        <span className="font-semibold">{humanizeEnum(ind.type)}:</span>{" "}
                        <span className="font-mono">"{ind.matched_text}"</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="mt-4 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">
              <span className="font-medium text-ink">{t("result.noteLabel")}: </span>
              {state.data.note}
            </div>

            {RISKY.has(state.data.risk_level) && (
              <div className="mt-4 rounded-lg border border-risk-high/30 bg-risk-high-bg/50 p-3">
                <p className="text-sm text-risk-high">{t("result.reportPrompt")}</p>
                <button
                  type="button"
                  onClick={handleFileReport}
                  className="mt-2 w-full cursor-pointer rounded-lg bg-risk-high px-4 py-2 text-sm font-medium text-white"
                >
                  {t("actions.fileReport")}
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={handleReset}
              className="mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 font-medium text-ink transition-colors hover:bg-ink/5"
            >
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              {t("actions.checkAnother")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
