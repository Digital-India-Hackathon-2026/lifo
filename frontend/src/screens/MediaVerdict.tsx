import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, AlertTriangle, RotateCcw } from "lucide-react";
import clsx from "clsx";
import FileDropzone from "@/components/FileDropzone";
import VerdictBadge from "@/components/VerdictBadge";
import { useApiCall } from "@/hooks/useApiCall";
import { classifyAudio, classifyImage, classifyVideo, ApiError, NetworkError } from "@/api/client";
import type { ClassifyAudioResponse, ClassifyImageResponse, ClassifyVideoResponse } from "@/api/types";

type Tab = "image" | "video" | "audio";
type Result = ClassifyImageResponse | ClassifyVideoResponse | ClassifyAudioResponse;

const TAB_CONFIG: Record<
  Tab,
  { accept: string; maxBytes: number; hintKey: string; call: (f: File) => Promise<Result> }
> = {
  image: {
    accept: "image/jpeg,image/png,image/webp,image/bmp",
    maxBytes: 10 * 1024 * 1024,
    hintKey: "imageHint",
    call: classifyImage,
  },
  video: {
    accept: "video/mp4,video/avi,video/quicktime,video/x-msvideo,video/x-matroska",
    maxBytes: 100 * 1024 * 1024,
    hintKey: "videoHint",
    call: classifyVideo,
  },
  audio: {
    accept: "audio/wav,audio/x-wav,audio/wave,audio/flac,audio/x-flac,audio/ogg",
    maxBytes: 25 * 1024 * 1024,
    hintKey: "audioHint",
    call: classifyAudio,
  },
};

const TABS: Tab[] = ["image", "video", "audio"];

function isVideoResult(r: Result): r is ClassifyVideoResponse {
  return "frames_sampled" in r;
}
function isAudioResult(r: Result): r is ClassifyAudioResponse {
  return "anomaly_timestamp" in r;
}

export default function MediaVerdict() {
  const { t } = useTranslation("mediaVerdict");
  const { t: tc } = useTranslation();
  const [tab, setTab] = useState<Tab>("image");
  const [file, setFile] = useState<File | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const { state, run, reset } = useApiCall<Result>();

  const config = TAB_CONFIG[tab];
  const isLoading = state.status === "loading";

  const switchTab = (next: Tab) => {
    setTab(next);
    setFile(null);
    setClientError(null);
    reset();
  };

  const handleFileSelected = (selected: File | null) => {
    setClientError(null);
    if (selected && selected.size > config.maxBytes) {
      setClientError(t("errors.tooLarge"));
      setFile(null);
      return;
    }
    setFile(selected);
  };

  const handleAnalyze = () => {
    if (!file) return;
    run(() => config.call(file));
  };

  const handleReset = () => {
    setFile(null);
    setClientError(null);
    reset();
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-2xl font-bold text-ink">{t("title")}</h1>
      <p className="mt-1 text-ink-dim">{t("description")}</p>

      <div className="mt-6 flex gap-1 rounded-lg bg-ink/5 p-1" role="tablist">
        {TABS.map((tKey) => (
          <button
            key={tKey}
            role="tab"
            aria-selected={tab === tKey}
            disabled={isLoading}
            onClick={() => switchTab(tKey)}
            className={clsx(
              "flex-1 cursor-pointer rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              tab === tKey ? "bg-surface text-brand shadow-sm" : "text-ink-dim hover:text-ink",
              isLoading && "cursor-not-allowed opacity-60"
            )}
          >
            {t(`tabs.${tKey}`)}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {state.status !== "success" && (
          <>
            <FileDropzone
              accept={config.accept}
              hint={t(`dropzone.${config.hintKey}`)}
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
          <ResultCard result={state.data} t={t} onReset={handleReset} />
        )}
      </div>
    </div>
  );
}

function ResultCard({
  result,
  t,
  onReset,
}: {
  result: Result;
  t: (key: string) => string;
  onReset: () => void;
}) {
  return (
    <div className="glass-card rounded-xl p-6">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-ink-dim">{t("result.verdictLabel")}</span>
        <VerdictBadge verdict={result.verdict} />
      </div>

      <dl className="mt-4 space-y-2 text-sm">
        <Row label={t("result.confidenceLabel")} value={`${(result.confidence_score * 100).toFixed(1)}%`} />
        {isVideoResult(result) && (
          <>
            <Row label={t("result.framesSampledLabel")} value={String(result.frames_sampled)} />
            <Row
              label={t("result.mostSuspiciousFrameLabel")}
              value={`#${result.most_suspicious_frame.frame_index} (${(result.most_suspicious_frame.fake_score * 100).toFixed(1)}%)`}
            />
          </>
        )}
        {isAudioResult(result) && result.anomaly_timestamp !== null && (
          <Row
            label={t("result.anomalyTimestampLabel")}
            value={`${result.anomaly_timestamp.toFixed(1)}${t("result.secondsSuffix")}`}
          />
        )}
        <Row label={t("result.modelLabel")} value={result.model} mono />
      </dl>

      <div className="mt-4 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">
        <span className="font-medium text-ink">{t("result.noteLabel")}: </span>
        {result.note}
      </div>

      <button
        type="button"
        onClick={onReset}
        className="mt-5 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 font-medium text-ink transition-colors hover:bg-ink/5"
      >
        <RotateCcw className="h-4 w-4" aria-hidden="true" />
        {t("actions.checkAnother")}
      </button>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-border/60 py-1.5 last:border-0">
      <dt className="text-ink-dim">{label}</dt>
      <dd className={clsx("font-medium text-ink", mono && "font-mono text-xs")}>{value}</dd>
    </div>
  );
}
