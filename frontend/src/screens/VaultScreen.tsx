import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, AlertTriangle, Eye, EyeOff, Check, X, RotateCcw } from "lucide-react";
import clsx from "clsx";
import { useApiCall } from "@/hooks/useApiCall";
import { setSafeWord, verifySafeWord, ApiError, NetworkError } from "@/api/client";
import type { VaultSetResponse, VaultVerifyResponse } from "@/api/types";

/**
 * The safe word itself only ever lives in a local `const` captured at submit
 * time — the input's own state is cleared before the network call fires, so
 * it never sits in a rendered field (or React state) after submission, and
 * it never appears in any request the browser logs beyond the one POST body.
 */
export default function VaultScreen() {
  const { t } = useTranslation("vaultScreen");
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-2xl font-bold text-ink">{t("title")}</h1>
      <p className="mt-1 text-ink-dim">{t("description")}</p>

      <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2">
        <SetPanel />
        <VerifyPanel />
      </div>
    </div>
  );
}

function PasswordField({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation("vaultScreen");
  const [revealed, setRevealed] = useState(false);
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-ink-dim">{label}</span>
      <div className="relative">
        <input
          type={revealed ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          autoComplete="off"
          className="w-full rounded-md border border-border bg-surface px-3 py-2 pr-16 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        />
        <button
          type="button"
          onClick={() => setRevealed((v) => !v)}
          tabIndex={-1}
          className="absolute inset-y-0 right-0 flex cursor-pointer items-center gap-1 px-3 text-xs font-medium text-ink-dim hover:text-ink"
        >
          {revealed ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          {revealed ? t("hide") : t("reveal")}
        </button>
      </div>
    </label>
  );
}

function ErrorBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <p className="font-medium">{children}</p>
    </div>
  );
}

// ── Set panel ──────────────────────────────────────────────────────────────

function SetPanel() {
  const { t } = useTranslation("vaultScreen");
  const { t: tc } = useTranslation();
  const [word, setWord] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const { state, run, reset } = useApiCall<VaultSetResponse>();
  const isLoading = state.status === "loading";

  const handleSet = () => {
    if (word.trim().length < 3) {
      setClientError(t("set.errors.tooShort"));
      return;
    }
    setClientError(null);
    const candidate = word;
    setWord(""); // never sits in the field once submission starts
    run(() => setSafeWord({ safe_word: candidate }));
  };

  const handleReset = () => {
    setWord("");
    setClientError(null);
    reset();
  };

  if (state.status === "success") {
    return (
      <div className="glass-card flex flex-col rounded-xl p-6">
        <h2 className="font-display text-lg font-semibold text-ink">{t("set.heading")}</h2>
        <div className="mt-4 rounded-lg bg-risk-low-bg p-3 text-sm text-risk-low">
          <Check className="mb-1 h-5 w-5" aria-hidden="true" />
          <p className="font-medium">{state.data.message}</p>
        </div>
        <div className="mt-3 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">{state.data.note}</div>
        <button
          type="button"
          onClick={handleReset}
          className="mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 font-medium text-ink transition-colors hover:bg-ink/5"
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          {t("set.another")}
        </button>
      </div>
    );
  }

  return (
    <div className="glass-card flex flex-col rounded-xl p-6">
      <h2 className="font-display text-lg font-semibold text-ink">{t("set.heading")}</h2>
      <p className="mt-1 text-sm text-ink-dim">{t("set.body")}</p>

      <div className="mt-4">
        <PasswordField label={t("set.label")} value={word} onChange={setWord} disabled={isLoading} />
      </div>

      {clientError && (
        <p className="mt-2 flex items-center gap-1.5 text-sm text-risk-high">
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
          {clientError}
        </p>
      )}
      {state.status === "error" && (
        <ErrorBox>
          {state.error instanceof NetworkError
            ? tc("errors.network")
            : state.error instanceof ApiError
              ? state.error.body.error
              : tc("errors.generic")}
        </ErrorBox>
      )}

      <button
        type="button"
        onClick={handleSet}
        disabled={isLoading}
        className={clsx(
          "mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity",
          isLoading && "cursor-not-allowed opacity-50"
        )}
      >
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {isLoading ? t("set.loading") : t("set.action")}
      </button>
    </div>
  );
}

// ── Verify panel ───────────────────────────────────────────────────────────

function VerifyPanel() {
  const { t } = useTranslation("vaultScreen");
  const { t: tc } = useTranslation();
  const [word, setWord] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const { state, run, reset } = useApiCall<VaultVerifyResponse>();
  const isLoading = state.status === "loading";

  const handleVerify = () => {
    if (!word.trim()) {
      setClientError(t("verify.errors.empty"));
      return;
    }
    setClientError(null);
    const candidate = word;
    setWord(""); // never sits in the field once submission starts
    run(() => verifySafeWord({ safe_word: candidate }));
  };

  const handleReset = () => {
    setWord("");
    setClientError(null);
    reset();
  };

  const notSetYet = state.status === "error" && state.error instanceof ApiError && state.error.status === 409;

  if (state.status === "success") {
    const r = state.data;
    return (
      <div className="glass-card flex flex-col rounded-xl p-6">
        <h2 className="font-display text-lg font-semibold text-ink">{t("verify.heading")}</h2>
        <div className="mt-4 flex items-center gap-2">
          {r.matches ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-risk-low-bg px-3 py-1 text-sm font-semibold text-risk-low">
              <Check className="h-4 w-4" aria-hidden="true" />
              {t("verify.match")}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-ink/10 px-3 py-1 text-sm font-semibold text-ink-dim">
              <X className="h-4 w-4" aria-hidden="true" />
              {t("verify.noMatch")}
            </span>
          )}
        </div>
        <div className="mt-3 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">{r.note}</div>
        <button
          type="button"
          onClick={handleReset}
          className="mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 font-medium text-ink transition-colors hover:bg-ink/5"
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          {t("verify.another")}
        </button>
      </div>
    );
  }

  return (
    <div className="glass-card flex flex-col rounded-xl p-6">
      <h2 className="font-display text-lg font-semibold text-ink">{t("verify.heading")}</h2>
      <p className="mt-1 text-sm text-ink-dim">{t("verify.body")}</p>

      <div className="mt-4">
        <PasswordField label={t("verify.label")} value={word} onChange={setWord} disabled={isLoading} />
      </div>

      {clientError && (
        <p className="mt-2 flex items-center gap-1.5 text-sm text-risk-high">
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
          {clientError}
        </p>
      )}
      {state.status === "error" && (
        <ErrorBox>
          {notSetYet
            ? t("verify.errors.notSetYet")
            : state.error instanceof NetworkError
              ? tc("errors.network")
              : state.error instanceof ApiError
                ? state.error.body.error
                : tc("errors.generic")}
        </ErrorBox>
      )}

      <button
        type="button"
        onClick={handleVerify}
        disabled={isLoading}
        className={clsx(
          "mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity",
          isLoading && "cursor-not-allowed opacity-50"
        )}
      >
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {isLoading ? t("verify.loading") : t("verify.action")}
      </button>
    </div>
  );
}
