import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Link2, Loader2, ShieldAlert } from "lucide-react";
import clsx from "clsx";
import { useApiCall } from "@/hooks/useApiCall";
import {
  ApiError,
  NetworkError,
  answerTrainingDrill,
  getTrainingDrill,
  pairDevices,
  triggerPanic,
} from "@/api/client";
import type {
  PairDevicesResponse,
  PanicTriggerResponse,
  TrainingAnswerResponse,
  TrainingDrillResponse,
} from "@/api/types";

function errorMessage(error: ApiError | NetworkError | Error, tc: (key: string) => string): string {
  if (error instanceof NetworkError) return tc("errors.network");
  if (error instanceof ApiError) return error.body.error;
  return tc("errors.generic");
}

function PairingCard() {
  const { t } = useTranslation("familyProtection");
  const { t: tc } = useTranslation();
  const [protectedId, setProtectedId] = useState("");
  const [protectorId, setProtectorId] = useState("");
  const { state, run } = useApiCall<PairDevicesResponse>();

  const canSubmit = protectedId.trim() && protectorId.trim();

  return (
    <div className="glass-card rounded-xl p-6">
      <h2 className="font-display text-sm font-semibold text-ink">{t("pairing.heading")}</h2>
      <p className="mt-1 text-sm text-ink-dim">{t("pairing.description")}</p>

      <label className="mt-4 block">
        <span className="mb-1 block text-xs font-medium text-ink-dim">{t("pairing.protectedIdLabel")}</span>
        <input
          type="text"
          value={protectedId}
          onChange={(e) => setProtectedId(e.target.value)}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        />
      </label>

      <label className="mt-3 block">
        <span className="mb-1 block text-xs font-medium text-ink-dim">{t("pairing.protectorIdLabel")}</span>
        <input
          type="text"
          value={protectorId}
          onChange={(e) => setProtectorId(e.target.value)}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        />
      </label>

      {state.status === "error" && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>{errorMessage(state.error, tc)}</p>
        </div>
      )}

      {state.status === "success" && (
        <div className="mt-3 rounded-lg bg-brand-dim p-3 text-sm text-brand">
          {t("pairing.success", { protected: state.data.protected_id, protector: state.data.protector_id })}
        </div>
      )}

      <button
        type="button"
        onClick={() => run(() => pairDevices({ protected_id: protectedId, protector_id: protectorId }))}
        disabled={state.status === "loading" || !canSubmit}
        className={clsx(
          "mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity",
          (state.status === "loading" || !canSubmit) && "cursor-not-allowed opacity-50"
        )}
      >
        {state.status === "loading" ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <Link2 className="h-4 w-4" aria-hidden="true" />
        )}
        {t("pairing.submit")}
      </button>
    </div>
  );
}

function PanicCard() {
  const { t } = useTranslation("familyProtection");
  const { t: tc } = useTranslation();
  const [protectedId, setProtectedId] = useState("");
  const [deviceSource, setDeviceSource] = useState("smartwatch");
  const { state, run } = useApiCall<PanicTriggerResponse>();

  return (
    <div className="glass-card rounded-xl p-6">
      <h2 className="font-display text-sm font-semibold text-ink">{t("panic.heading")}</h2>
      <p className="mt-1 text-sm text-ink-dim">{t("panic.description")}</p>

      <label className="mt-4 block">
        <span className="mb-1 block text-xs font-medium text-ink-dim">{t("panic.protectedIdLabel")}</span>
        <input
          type="text"
          value={protectedId}
          onChange={(e) => setProtectedId(e.target.value)}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        />
      </label>

      <label className="mt-3 block">
        <span className="mb-1 block text-xs font-medium text-ink-dim">{t("panic.deviceSourceLabel")}</span>
        <select
          value={deviceSource}
          onChange={(e) => setDeviceSource(e.target.value)}
          className="w-full cursor-pointer rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        >
          <option value="smartwatch">{t("panic.deviceSmartwatch")}</option>
          <option value="panic_button">{t("panic.devicePanicButton")}</option>
        </select>
      </label>

      {state.status === "error" && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>{errorMessage(state.error, tc)}</p>
        </div>
      )}

      {state.status === "success" && (
        <div className="mt-3 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
          {state.data.protector_notified_id
            ? t("panic.notifiedProtector", { id: state.data.protector_notified_id })
            : t("panic.notifiedPublic")}
        </div>
      )}

      <button
        type="button"
        onClick={() => run(() => triggerPanic({ protected_id: protectedId, device_source: deviceSource }))}
        disabled={state.status === "loading" || !protectedId.trim()}
        className={clsx(
          "mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-risk-high px-4 py-2.5 font-medium text-white transition-opacity",
          (state.status === "loading" || !protectedId.trim()) && "cursor-not-allowed opacity-50"
        )}
      >
        {state.status === "loading" ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <ShieldAlert className="h-4 w-4" aria-hidden="true" />
        )}
        {t("panic.submit")}
      </button>
    </div>
  );
}

function TrainingCard() {
  const { t } = useTranslation("familyProtection");
  const { t: tc } = useTranslation();
  const [userId, setUserId] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const drillCall = useApiCall<TrainingDrillResponse>();
  const answerCall = useApiCall<TrainingAnswerResponse>();

  const handleGetDrill = () => {
    setSelected(null);
    answerCall.reset();
    drillCall.run(() => getTrainingDrill());
  };

  const handleAnswer = () => {
    if (drillCall.state.status !== "success" || !selected || !userId.trim()) return;
    const drillId = drillCall.state.data.drill_id;
    answerCall.run(() => answerTrainingDrill({ user_id: userId, drill_id: drillId, selected_answer: selected }));
  };

  return (
    <div className="glass-card rounded-xl p-6">
      <h2 className="font-display text-sm font-semibold text-ink">{t("training.heading")}</h2>
      <p className="mt-1 text-sm text-ink-dim">{t("training.description")}</p>

      <label className="mt-4 block">
        <span className="mb-1 block text-xs font-medium text-ink-dim">{t("training.userIdLabel")}</span>
        <input
          type="text"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        />
      </label>

      {drillCall.state.status !== "success" && (
        <button
          type="button"
          onClick={handleGetDrill}
          disabled={drillCall.state.status === "loading"}
          className={clsx(
            "mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity",
            drillCall.state.status === "loading" && "cursor-not-allowed opacity-50"
          )}
        >
          {drillCall.state.status === "loading" && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {t("training.getDrill")}
        </button>
      )}

      {drillCall.state.status === "success" && answerCall.state.status !== "success" && (
        <div className="mt-4">
          <p className="text-sm text-ink">{drillCall.state.data.scenario_text}</p>
          <div className="mt-3 flex flex-col gap-2">
            {drillCall.state.data.options.map((opt, i) => (
              <label
                key={i}
                className={clsx(
                  "flex cursor-pointer items-start gap-2 rounded-lg border p-3 text-sm transition-colors",
                  selected === opt ? "border-brand bg-brand-dim" : "border-border hover:bg-ink/5"
                )}
              >
                <input
                  type="radio"
                  name="drill-option"
                  checked={selected === opt}
                  onChange={() => setSelected(opt)}
                  className="mt-0.5"
                />
                <span className="text-ink">{opt}</span>
              </label>
            ))}
          </div>

          {answerCall.state.status === "error" && (
            <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <p>{errorMessage(answerCall.state.error, tc)}</p>
            </div>
          )}

          <button
            type="button"
            onClick={handleAnswer}
            disabled={answerCall.state.status === "loading" || !selected || !userId.trim()}
            className={clsx(
              "mt-3 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity",
              (answerCall.state.status === "loading" || !selected || !userId.trim()) &&
                "cursor-not-allowed opacity-50"
            )}
          >
            {answerCall.state.status === "loading" && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
            {t("training.submitAnswer")}
          </button>
        </div>
      )}

      {answerCall.state.status === "success" && (
        <div className="mt-4">
          <div
            className={clsx(
              "rounded-lg p-3 text-sm",
              answerCall.state.data.correct ? "bg-risk-low-bg text-risk-low" : "bg-risk-high-bg text-risk-high"
            )}
          >
            {answerCall.state.data.correct ? t("training.correct") : t("training.incorrect")}
          </div>
          <p className="mt-2 text-sm text-ink-dim">{answerCall.state.data.explanation}</p>
          <p className="mt-2 text-xs text-ink-dim">
            {t("training.scoreLabel")}: {answerCall.state.data.training_score.drills_completed_count}
          </p>
          <button
            type="button"
            onClick={handleGetDrill}
            className="mt-3 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 font-medium text-ink hover:bg-ink/5"
          >
            {t("training.nextDrill")}
          </button>
        </div>
      )}
    </div>
  );
}

export default function FamilyProtection() {
  const { t } = useTranslation("familyProtection");

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-2xl font-bold text-ink">{t("title")}</h1>
      <p className="mt-1 text-ink-dim">{t("description")}</p>

      <div className="mt-6 flex flex-col gap-5">
        <PairingCard />
        <PanicCard />
        <TrainingCard />
      </div>
    </div>
  );
}
