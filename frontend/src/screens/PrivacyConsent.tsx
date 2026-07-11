import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Loader2, ShieldCheck } from "lucide-react";
import clsx from "clsx";
import { ApiError, NetworkError, getConsentStatus, grantConsent, revokeConsent } from "@/api/client";

// Purpose keys are free-text on the backend (Field(..., min_length=1), no fixed
// enum) — this is the frontend's own curated list of the actual data flows in
// this app that consent meaningfully governs, not a mirror of a backend enum.
const PURPOSES = [
  "honeypot_session_retention",
  "family_alert_sharing",
  "community_heatmap_reporting",
  "case_timeline_storage",
] as const;

type Purpose = (typeof PURPOSES)[number];
type ToggleState = "unknown" | "loading" | "on" | "off" | "error";

function errorMessage(error: ApiError | NetworkError | Error, tc: (key: string) => string): string {
  if (error instanceof NetworkError) return tc("errors.network");
  if (error instanceof ApiError) return error.body.error;
  return tc("errors.generic");
}

function ToggleSwitch({
  checked,
  disabled,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={onChange}
      className={clsx(
        "relative h-6 w-11 shrink-0 cursor-pointer rounded-full transition-colors",
        checked ? "bg-brand" : "bg-ink/15",
        disabled && "cursor-not-allowed opacity-50"
      )}
    >
      <span
        className={clsx(
          "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
          checked && "translate-x-5"
        )}
      />
    </button>
  );
}

function PurposeRow({ userId, purpose }: { userId: string; purpose: Purpose }) {
  const { t } = useTranslation("privacyConsent");
  const { t: tc } = useTranslation();
  const [state, setState] = useState<ToggleState>("unknown");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setState("loading");
    setError(null);
    try {
      const data = await getConsentStatus({ user_id: userId, purpose });
      setState(data.active ? "on" : "off");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setState("off"); // no record yet == never granted, a real "off", not an error
        return;
      }
      setState("error");
      setError(err instanceof Error ? errorMessage(err, tc) : tc("errors.generic"));
    }
  };

  const toggle = async () => {
    const turningOn = state !== "on";
    setState("loading");
    setError(null);
    try {
      if (turningOn) {
        await grantConsent({ user_id: userId, purpose });
        setState("on");
      } else {
        await revokeConsent({ user_id: userId, purpose });
        setState("off");
      }
    } catch (err) {
      setState("error");
      setError(err instanceof Error ? errorMessage(err, tc) : tc("errors.generic"));
    }
  };

  return (
    <div className="flex items-center justify-between gap-4 border-t border-border py-4 first:border-t-0">
      <div>
        <p className="text-sm font-medium text-ink">{t(`purposes.${purpose}.label`)}</p>
        <p className="mt-0.5 text-xs text-ink-dim">{t(`purposes.${purpose}.description`)}</p>
        {error && (
          <p className="mt-1 flex items-center gap-1 text-xs text-risk-high">
            <AlertTriangle className="h-3 w-3 shrink-0" aria-hidden="true" />
            {error}
          </p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-3">
        {state === "unknown" && (
          <button
            type="button"
            onClick={load}
            className="cursor-pointer rounded-md border border-border px-2.5 py-1 text-xs font-medium text-ink hover:bg-ink/5"
          >
            {t("checkStatus")}
          </button>
        )}
        {state === "loading" && <Loader2 className="h-4 w-4 animate-spin text-ink-dim" aria-hidden="true" />}
        {(state === "on" || state === "off" || state === "error") && (
          <ToggleSwitch checked={state === "on"} disabled={state === "error"} onChange={toggle} />
        )}
      </div>
    </div>
  );
}

export default function PrivacyConsent() {
  const { t } = useTranslation("privacyConsent");
  const [userId, setUserId] = useState("");
  const [activeUserId, setActiveUserId] = useState<string | null>(null);

  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-brand" aria-hidden="true" />
        <h1 className="font-display text-2xl font-bold text-ink">{t("title")}</h1>
      </div>
      <p className="mt-1 text-ink-dim">{t("description")}</p>

      <div className="glass-card mt-6 rounded-xl p-6">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("userIdLabel")}</span>
          <div className="flex gap-2">
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder={t("userIdPlaceholder")}
              className="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
            />
            <button
              type="button"
              onClick={() => setActiveUserId(userId)}
              disabled={!userId.trim()}
              className={clsx(
                "cursor-pointer rounded-md bg-brand px-4 py-2 text-sm font-medium text-white",
                !userId.trim() && "cursor-not-allowed opacity-50"
              )}
            >
              {t("load")}
            </button>
          </div>
        </label>

        {activeUserId && (
          <div className="mt-2">
            {/* key= forces PurposeRow to remount (and reset to "unknown") when
                the active user_id changes — no stale toggle state from a
                previous user's lookup carried over silently. */}
            {PURPOSES.map((p) => (
              <PurposeRow key={`${activeUserId}-${p}`} userId={activeUserId} purpose={p} />
            ))}
          </div>
        )}

        {!activeUserId && <p className="mt-4 text-sm text-ink-dim/80">{t("emptyState")}</p>}
      </div>
    </div>
  );
}
