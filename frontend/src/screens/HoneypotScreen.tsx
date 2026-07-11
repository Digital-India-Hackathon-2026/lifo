import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, AlertTriangle, Mic, Square, Play, FileWarning, RotateCcw } from "lucide-react";
import clsx from "clsx";
import FileDropzone from "@/components/FileDropzone";
import RiskBadge from "@/components/RiskBadge";
import { useApiCall } from "@/hooks/useApiCall";
import { useReport } from "@/context/ReportContext";
import { translateHardFactualAnchor } from "@/lib/format";
import {
  startHoneypotSession,
  honeypotConverse,
  getHoneypotReport,
  checkDigitalArrest,
  ApiError,
  NetworkError,
} from "@/api/client";
import type { ConverseResponse, ReportResponse, DigitalArrestResponse } from "@/api/types";

const UPLOAD_ACCEPT = "audio/wav,audio/x-wav,audio/wave,audio/flac,audio/x-flac,audio/ogg";
const MAX_BYTES = 25 * 1024 * 1024;
const RISKY = new Set(["medium", "high"]);

type Screen = "idle" | "active" | "report";

// MediaRecorder's mimeType often includes a codec suffix (e.g. "audio/webm;codecs=opus"),
// but the backend's allowlist matches on an exact content-type string with no codec suffix.
// Recording with the codec-qualified type but *labeling* the resulting File with the bare
// type keeps the browser's own encoder choice while still passing the backend's exact check.
const CANDIDATE_MIME_TYPES = [
  { recorderType: "audio/webm;codecs=opus", normalizedType: "audio/webm", ext: "webm" },
  { recorderType: "audio/webm", normalizedType: "audio/webm", ext: "webm" },
  { recorderType: "audio/mp4", normalizedType: "audio/mp4", ext: "m4a" },
] as const;

function pickMimeType() {
  if (typeof MediaRecorder === "undefined") return null;
  return CANDIDATE_MIME_TYPES.find((c) => MediaRecorder.isTypeSupported(c.recorderType)) ?? null;
}

function useAudioRecorder(onComplete: (file: File) => void) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<"micDenied" | "micUnsupported" | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const start = async () => {
    setError(null);
    const picked = pickMimeType();
    if (!picked) {
      setError("micUnsupported");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: picked.recorderType });
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: picked.normalizedType });
        onComplete(new File([blob], `recording.${picked.ext}`, { type: picked.normalizedType }));
      };
      recorder.start();
      recorderRef.current = recorder;
      setIsRecording(true);
    } catch {
      setError("micDenied");
    }
  };

  const stop = () => {
    recorderRef.current?.stop();
    setIsRecording(false);
  };

  return { isRecording, start, stop, error };
}

export default function HoneypotScreen() {
  const { t } = useTranslation("honeypot");
  const { t: tc } = useTranslation();
  const [screen, setScreen] = useState<Screen>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ConverseResponse[]>([]);
  const startCall = useApiCall<{ session_id: string }>();

  const handleStart = async () => {
    const data = await startCall.run(() => startHoneypotSession());
    if (data) {
      setSessionId(data.session_id);
      setTurns([]);
      setScreen("active");
    }
  };

  const handleNewSession = () => {
    setSessionId(null);
    setTurns([]);
    startCall.reset();
    setScreen("idle");
  };

  if (screen === "idle") {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="glass-card rounded-xl p-8 text-center">
          <h1 className="font-display text-2xl font-bold text-ink">{t("idle.heading")}</h1>
          <p className="mx-auto mt-2 max-w-md text-ink-dim">{t("idle.body")}</p>

          {startCall.state.status === "error" && (
            <div className="mx-auto mt-4 flex max-w-md items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-left text-sm text-risk-high">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <p>
                {startCall.state.error instanceof NetworkError ? tc("errors.network") : tc("errors.generic")}
              </p>
            </div>
          )}

          <button
            type="button"
            onClick={handleStart}
            disabled={startCall.state.status === "loading"}
            className={clsx(
              "mx-auto mt-6 flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-6 py-2.5 font-medium text-white transition-opacity",
              startCall.state.status === "loading" && "cursor-not-allowed opacity-50"
            )}
          >
            {startCall.state.status === "loading" && (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            )}
            {t("idle.start")}
          </button>
        </div>
      </div>
    );
  }

  if (screen === "active" && sessionId) {
    return (
      <ActiveSession
        sessionId={sessionId}
        turns={turns}
        onTurnComplete={(turn) => setTurns((prev) => [...prev, turn])}
        onEndSession={() => setScreen("report")}
      />
    );
  }

  if (screen === "report" && sessionId) {
    return <ReportView sessionId={sessionId} onNewSession={handleNewSession} />;
  }

  return null;
}

// ── Active session ────────────────────────────────────────────────────────────

function ActiveSession({
  sessionId,
  turns,
  onTurnComplete,
  onEndSession,
}: {
  sessionId: string;
  turns: ConverseResponse[];
  onTurnComplete: (turn: ConverseResponse) => void;
  onEndSession: () => void;
}) {
  const { t } = useTranslation("honeypot");
  const { t: tc } = useTranslation();
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const { state, run, reset } = useApiCall<ConverseResponse>();
  const isSubmitting = state.status === "loading";
  const recorder = useAudioRecorder((file) => setPendingFile(file));

  const latestIntel = turns.length > 0 ? turns[turns.length - 1].cumulative_intel : null;

  const handleFileSelected = (selected: File | null) => {
    setClientError(null);
    if (selected && selected.size > MAX_BYTES) {
      setClientError(tc("errors.generic"));
      setPendingFile(null);
      return;
    }
    setPendingFile(selected);
  };

  const handleSend = async () => {
    if (!pendingFile) {
      setClientError(t("errors.noFile"));
      return;
    }
    setClientError(null);
    const file = pendingFile;
    setPendingFile(null);
    const data = await run(() => honeypotConverse(sessionId, file));
    if (data) {
      onTurnComplete(data);
      reset();
    }
  };

  return (
    <div className="mx-auto max-w-5xl">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0">
          <div className="flex flex-col gap-4">
            {turns.map((turn) => (
              <TurnCard key={turn.turn} turn={turn} />
            ))}
          </div>

          <div className="glass-card mt-4 rounded-xl p-5">
            {recorder.error && (
              <p className="mb-3 flex items-center gap-1.5 text-sm text-risk-high">
                <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                {t(`errors.${recorder.error}`)}
              </p>
            )}

            <FileDropzone
              accept={UPLOAD_ACCEPT}
              hint={t("active.uploadHint")}
              prompt={t("active.uploadPrompt")}
              file={pendingFile}
              onFileSelected={handleFileSelected}
              disabled={isSubmitting || recorder.isRecording}
            />

            <div className="mt-3 flex items-center gap-3">
              <span className="text-xs font-medium uppercase tracking-wide text-ink-dim">
                {t("active.or")}
              </span>
              {!recorder.isRecording ? (
                <button
                  type="button"
                  onClick={recorder.start}
                  disabled={isSubmitting}
                  className="flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-ink hover:bg-ink/5"
                >
                  <Mic className="h-3.5 w-3.5" aria-hidden="true" />
                  {t("active.record")}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={recorder.stop}
                  className="flex cursor-pointer items-center gap-1.5 rounded-md border border-risk-high bg-risk-high-bg px-3 py-1.5 text-sm font-medium text-risk-high"
                >
                  <Square className="h-3.5 w-3.5" aria-hidden="true" />
                  {t("active.stopRecording")}
                </button>
              )}
              {recorder.isRecording && (
                <span className="text-xs text-risk-high">{t("active.recording")}</span>
              )}
            </div>

            {clientError && (
              <p className="mt-3 flex items-center gap-1.5 text-sm text-risk-high">
                <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                {clientError}
              </p>
            )}
            {state.status === "error" && (
              <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <p>
                  {state.error instanceof NetworkError
                    ? tc("errors.network")
                    : state.error instanceof ApiError
                      ? state.error.body.error
                      : tc("errors.generic")}
                </p>
              </div>
            )}

            <button
              type="button"
              onClick={handleSend}
              disabled={isSubmitting || !pendingFile}
              className={clsx(
                "mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity",
                (isSubmitting || !pendingFile) && "cursor-not-allowed opacity-50"
              )}
            >
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              {isSubmitting ? t("active.sending") : t("active.send")}
            </button>
          </div>

          <button
            type="button"
            onClick={onEndSession}
            disabled={turns.length === 0}
            className={clsx(
              "mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 font-medium text-ink transition-colors hover:bg-ink/5",
              turns.length === 0 && "cursor-not-allowed opacity-50"
            )}
          >
            {t("active.endSession")}
          </button>
        </div>

        <IntelSidebar intel={latestIntel} />
      </div>
    </div>
  );
}

function TurnCard({ turn }: { turn: ConverseResponse }) {
  const { t } = useTranslation("honeypot");
  const audioRef = useRef<HTMLAudioElement>(null);

  return (
    <div className="glass-card rounded-xl p-5">
      <span className="text-xs font-semibold uppercase tracking-wide text-brand">
        {t("active.turnLabel", { turn: turn.turn })}
      </span>

      <div className="mt-2">
        <span className="text-xs font-medium text-ink-dim">{t("active.transcriptLabel")}</span>
        <p className="mt-0.5 text-sm text-ink">
          {turn.transcript ?? <em className="text-ink-dim">{t("active.couldNotTranscribe")}</em>}
        </p>
      </div>

      <div className="mt-3">
        <span className="text-xs font-medium text-ink-dim">{t("active.personaReplyLabel")}</span>
        <p className="mt-0.5 text-sm text-ink">
          {turn.persona_reply_text ?? <em className="text-ink-dim">{t("active.noPersonaReply")}</em>}
        </p>
      </div>

      {turn.persona_reply_audio && (
        <div className="mt-3 flex items-center gap-2">
          <audio ref={audioRef} autoPlay src={`data:audio/mpeg;base64,${turn.persona_reply_audio}`} />
          <button
            type="button"
            onClick={() => audioRef.current?.play()}
            className="flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-ink hover:bg-ink/5"
          >
            <Play className="h-3 w-3" aria-hidden="true" />
            {t("active.replayAudio")}
          </button>
        </div>
      )}

      <details className="mt-3 text-xs text-ink-dim">
        <summary className="cursor-pointer font-medium hover:text-ink">{t("active.traceLabel")}</summary>
        <ul className="mt-1.5 space-y-0.5 font-mono">
          {turn.stage_log.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function IntelSidebar({ intel }: { intel: ConverseResponse["cumulative_intel"] | null }) {
  const { t } = useTranslation("honeypot");
  const rows: { label: string; values: string[] }[] = intel
    ? [
        { label: t("active.sidebar.upiIds"), values: intel.upi_ids },
        { label: t("active.sidebar.phoneNumbers"), values: intel.phone_numbers },
        { label: t("active.sidebar.bankAccounts"), values: intel.bank_accounts },
        { label: t("active.sidebar.scriptedPhrases"), values: intel.scripted_phrases },
      ]
    : [];
  const isEmpty = rows.every((r) => r.values.length === 0);

  return (
    <div className="glass-card h-fit rounded-xl p-5 lg:sticky lg:top-4">
      <h2 className="font-display text-sm font-semibold text-ink">{t("active.sidebar.heading")}</h2>
      {isEmpty ? (
        <p className="mt-2 text-sm text-ink-dim">{t("active.sidebar.empty")}</p>
      ) : (
        <div className="mt-3 flex flex-col gap-3">
          {rows.map(
            (row) =>
              row.values.length > 0 && (
                <div key={row.label}>
                  <span className="text-xs font-medium text-ink-dim">{row.label}</span>
                  <ul className="mt-1 flex flex-wrap gap-1.5">
                    {row.values.map((v) => (
                      <li key={v} className="rounded-md bg-risk-high-bg px-2 py-1 font-mono text-xs text-risk-high">
                        {v}
                      </li>
                    ))}
                  </ul>
                </div>
              )
          )}
        </div>
      )}
    </div>
  );
}

// ── Report view ───────────────────────────────────────────────────────────────

function ReportView({ sessionId, onNewSession }: { sessionId: string; onNewSession: () => void }) {
  const { t, i18n } = useTranslation("honeypot");
  const { t: tc } = useTranslation();
  const { openReport } = useReport();
  const reportCall = useApiCall<ReportResponse>();
  const daCall = useApiCall<DigitalArrestResponse>();

  useEffect(() => {
    reportCall.run(() => getHoneypotReport(sessionId));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const handleRunDigitalArrest = () => {
    daCall.run(() => checkDigitalArrest({ session_id: sessionId }));
  };

  const handleFileReport = () => {
    if (daCall.state.status !== "success") return;
    openReport({
      matched_patterns: daCall.state.data.matched_patterns,
      payment_indicators: daCall.state.data.payment_indicators_found,
    });
  };

  if (reportCall.state.status === "loading" || reportCall.state.status === "idle") {
    return (
      <div className="mx-auto flex max-w-2xl items-center justify-center gap-2 p-10 text-ink-dim">
        <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
      </div>
    );
  }

  if (reportCall.state.status === "error") {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>{tc("errors.generic")}</p>
        </div>
      </div>
    );
  }

  const report = reportCall.state.data;

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-2xl font-bold text-ink">{t("report.heading")}</h1>
      <p className="mt-1 text-ink-dim">
        {t("report.turnCountLabel")}: {report.turn_count}
      </p>

      <div className="glass-card mt-5 rounded-xl p-6">
        <h2 className="font-display text-sm font-semibold text-ink">{t("report.intelHeading")}</h2>
        <IntelSidebar intel={report.cumulative_intel} />
      </div>

      <div className="glass-card mt-5 rounded-xl p-6">
        <h2 className="font-display text-sm font-semibold text-ink">{t("report.historyHeading")}</h2>
        <div className="mt-3 flex flex-col gap-3">
          {report.turn_history.map((item) => (
            <div key={item.turn} className="border-b border-border/60 pb-3 last:border-0 last:pb-0">
              <span className="text-xs font-semibold uppercase tracking-wide text-brand">
                {t("active.turnLabel", { turn: item.turn })}
              </span>
              <p className="mt-1 text-sm text-ink">
                {item.transcript ?? <em className="text-ink-dim">{t("active.couldNotTranscribe")}</em>}
              </p>
              <p className="mt-1 text-sm text-ink-dim">
                {item.persona_reply ?? <em>{t("active.noPersonaReply")}</em>}
              </p>
            </div>
          ))}
        </div>
      </div>

      {daCall.state.status !== "success" && (
        <button
          type="button"
          onClick={handleRunDigitalArrest}
          disabled={daCall.state.status === "loading"}
          className={clsx(
            "mt-5 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity",
            daCall.state.status === "loading" && "cursor-not-allowed opacity-50"
          )}
        >
          {daCall.state.status === "loading" && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {daCall.state.status === "loading" ? t("report.checking") : t("report.runDigitalArrest")}
        </button>
      )}

      {daCall.state.status === "success" && (
        <div className="glass-card mt-5 rounded-xl p-6">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-ink-dim">{t("report.digitalArrest.severityLabel")}</span>
            <RiskBadge level={daCall.state.data.severity} />
          </div>

          <div className="mt-4">
            <span className="text-sm font-medium text-ink-dim">
              {t("report.digitalArrest.matchedPatternsLabel")}
            </span>
            {daCall.state.data.matched_patterns.length === 0 ? (
              <p className="mt-1 text-sm text-ink-dim/80">{t("report.digitalArrest.noPatterns")}</p>
            ) : (
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {daCall.state.data.matched_patterns.map((p, i) => (
                  <li key={i} className="rounded-md bg-risk-high-bg px-2 py-1 font-mono text-xs text-risk-high">
                    <FileWarning className="mr-1 inline h-3 w-3" aria-hidden="true" />
                    {p}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="mt-4">
            <span className="text-sm font-medium text-ink-dim">
              {t("report.digitalArrest.paymentIndicatorsLabel")}
            </span>
            {daCall.state.data.payment_indicators_found.length === 0 ? (
              <p className="mt-1 text-sm text-ink-dim/80">{t("report.digitalArrest.noPaymentIndicators")}</p>
            ) : (
              <ul className="mt-1.5 flex flex-wrap gap-1.5">
                {daCall.state.data.payment_indicators_found.map((p, i) => (
                  <li key={i} className="rounded-md bg-risk-medium-bg px-2 py-1 font-mono text-xs text-risk-medium">
                    {p}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="mt-4 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">
            <span className="font-medium text-ink">{t("report.digitalArrest.anchorLabel")}: </span>
            {translateHardFactualAnchor(daCall.state.data.hard_factual_anchor, i18n.language)}
          </div>
          <div className="mt-2 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">
            <span className="font-medium text-ink">{t("report.digitalArrest.noteLabel")}: </span>
            {daCall.state.data.note}
          </div>

          {RISKY.has(daCall.state.data.severity) && (
            <div className="mt-4 rounded-lg border border-risk-high/30 bg-risk-high-bg/50 p-3">
              <p className="text-sm text-risk-high">{t("report.digitalArrest.reportPrompt")}</p>
              <button
                type="button"
                onClick={handleFileReport}
                className="mt-2 w-full cursor-pointer rounded-lg bg-risk-high px-4 py-2 text-sm font-medium text-white"
              >
                {t("report.digitalArrest.fileReport")}
              </button>
            </div>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={onNewSession}
        className="mt-5 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 font-medium text-ink transition-colors hover:bg-ink/5"
      >
        <RotateCcw className="h-4 w-4" aria-hidden="true" />
        {t("report.newSession")}
      </button>
    </div>
  );
}
