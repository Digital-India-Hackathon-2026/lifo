import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, AlertTriangle, RotateCcw, FileWarning } from "lucide-react";
import clsx from "clsx";
import RiskBadge from "@/components/RiskBadge";
import { useApiCall } from "@/hooks/useApiCall";
import { useReport } from "@/context/ReportContext";
import { translateHardFactualAnchor } from "@/lib/format";
import {
  checkPhishing,
  checkSocialProfile,
  checkDigitalArrest,
  ApiError,
  NetworkError,
} from "@/api/client";
import type {
  CheckPhishingResponse,
  CheckSocialProfileResponse,
  DigitalArrestResponse,
  SocialProfileRequest,
} from "@/api/types";

type Tab = "phishing" | "socialProfile" | "digitalArrest";
const TABS: Tab[] = ["phishing", "socialProfile", "digitalArrest"];
const RISKY = new Set(["medium", "high"]);

export default function CheckLinkProfileCall() {
  const { t } = useTranslation("checkLink");
  const [tab, setTab] = useState<Tab>("phishing");

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
            onClick={() => setTab(tKey)}
            className={clsx(
              "flex-1 cursor-pointer rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              tab === tKey ? "bg-surface text-brand shadow-sm" : "text-ink-dim hover:text-ink"
            )}
          >
            {t(`tabs.${tKey}`)}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === "phishing" && <PhishingTab />}
        {tab === "socialProfile" && <SocialProfileTab />}
        {tab === "digitalArrest" && <DigitalArrestTab />}
      </div>
    </div>
  );
}

function ErrorBox({ error }: { error: ApiError | NetworkError | Error }) {
  const { t: tc } = useTranslation();
  return (
    <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div>
        <p className="font-medium">
          {error instanceof NetworkError
            ? tc("errors.network")
            : error instanceof ApiError
              ? error.body.error
              : tc("errors.generic")}
        </p>
        {error instanceof ApiError && typeof error.body.detail === "string" && (
          <p className="mt-0.5 text-risk-high/80">{error.body.detail}</p>
        )}
      </div>
    </div>
  );
}

function ReportPrompt({ show, onFileReport }: { show: boolean; onFileReport: () => void }) {
  const { t } = useTranslation("checkLink");
  if (!show) return null;
  return (
    <div className="mt-4 rounded-lg border border-risk-high/30 bg-risk-high-bg/50 p-3">
      <p className="text-sm text-risk-high">{t("result.reportPrompt")}</p>
      <button
        type="button"
        onClick={onFileReport}
        className="mt-2 w-full cursor-pointer rounded-lg bg-risk-high px-4 py-2 text-sm font-medium text-white"
      >
        {t("actions.fileReport")}
      </button>
    </div>
  );
}

function CheckAnotherButton({ onReset }: { onReset: () => void }) {
  const { t } = useTranslation("checkLink");
  return (
    <button
      type="button"
      onClick={onReset}
      className="mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 font-medium text-ink transition-colors hover:bg-ink/5"
    >
      <RotateCcw className="h-4 w-4" aria-hidden="true" />
      {t("actions.checkAnother")}
    </button>
  );
}

// ── Phishing tab ──────────────────────────────────────────────────────────────

function PhishingTab() {
  const { t } = useTranslation("checkLink");
  const { openReport } = useReport();
  const [url, setUrl] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const { state, run, reset } = useApiCall<CheckPhishingResponse>();
  const isLoading = state.status === "loading";

  const handleCheck = () => {
    if (!url.trim()) {
      setClientError(t("phishing.errors.empty"));
      return;
    }
    setClientError(null);
    run(() => checkPhishing({ url: url.trim() }));
  };

  const handleReset = () => {
    setUrl("");
    setClientError(null);
    reset();
  };

  const handleFileReport = () => {
    if (state.status !== "success") return;
    const { domain, matched_against } = state.data;
    openReport({
      matched_patterns: [
        matched_against ? `suspicious_domain: ${domain} (resembles ${matched_against})` : `suspicious_domain: ${domain}`,
      ],
    });
  };

  if (state.status === "success") {
    const r = state.data;
    return (
      <div className="glass-card rounded-xl p-6">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-ink-dim">{t("phishing.result.domainLabel")}</span>
          <RiskBadge level={r.risk_level} />
        </div>
        <p className="mt-1 font-mono text-sm text-ink">{r.domain}</p>

        <dl className="mt-4 space-y-2 text-sm">
          <div className="flex items-center justify-between border-b border-border/60 py-1.5">
            <dt className="text-ink-dim">{t("phishing.result.blocklistLabel")}</dt>
            <dd className={clsx("font-medium", r.in_blocklist ? "text-risk-high" : "text-ink")}>
              {r.in_blocklist ? t("phishing.result.onBlocklist") : t("phishing.result.notOnBlocklist")}
            </dd>
          </div>
          <div className="flex items-center justify-between border-b border-border/60 py-1.5">
            <dt className="text-ink-dim">{t("phishing.result.similarityLabel")}</dt>
            <dd className="font-medium text-ink">{(r.similarity_score * 100).toFixed(0)}%</dd>
          </div>
          {r.matched_against && (
            <div className="flex items-center justify-between py-1.5 last:border-0">
              <dt className="text-ink-dim">{t("phishing.result.matchedAgainstLabel")}</dt>
              <dd className="font-mono text-xs font-medium text-ink">{r.matched_against}</dd>
            </div>
          )}
        </dl>

        <div className="mt-4 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">
          <span className="font-medium text-ink">{t("result.noteLabel")}: </span>
          {r.note}
        </div>

        <ReportPrompt show={RISKY.has(r.risk_level)} onFileReport={handleFileReport} />
        <CheckAnotherButton onReset={handleReset} />
      </div>
    );
  }

  return (
    <div className="glass-card rounded-xl p-6">
      <label className="block">
        <span className="mb-1 block text-sm font-medium text-ink-dim">{t("phishing.urlLabel")}</span>
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={t("phishing.urlPlaceholder")}
          disabled={isLoading}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        />
      </label>

      {clientError && (
        <p className="mt-2 flex items-center gap-1.5 text-sm text-risk-high">
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
          {clientError}
        </p>
      )}
      {state.status === "error" && <ErrorBox error={state.error} />}

      <button
        type="button"
        onClick={handleCheck}
        disabled={isLoading}
        className={clsx(
          "mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity",
          isLoading && "cursor-not-allowed opacity-50"
        )}
      >
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {isLoading ? t("loading") : t("actions.check")}
      </button>
    </div>
  );
}

// ── Social profile tab ────────────────────────────────────────────────────────

const PLATFORMS: SocialProfileRequest["platform"][] = [
  "instagram",
  "facebook",
  "twitter",
  "whatsapp",
  "telegram",
  "other",
];

type SocialForm = {
  platform: SocialProfileRequest["platform"];
  has_profile_photo: boolean;
  profile_photo_is_stock: boolean;
  is_verified: boolean;
  account_age_days: string;
  follower_count: string;
  following_count: string;
  post_count: string;
  display_name: string;
  bio_text: string;
};

const EMPTY_SOCIAL_FORM: SocialForm = {
  platform: "instagram",
  has_profile_photo: true,
  profile_photo_is_stock: false,
  is_verified: false,
  account_age_days: "",
  follower_count: "",
  following_count: "",
  post_count: "",
  display_name: "",
  bio_text: "",
};

function toOptionalInt(v: string): number | undefined {
  if (v.trim() === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? Math.max(0, Math.floor(n)) : undefined;
}

function SocialProfileTab() {
  const { t } = useTranslation("checkLink");
  const { openReport } = useReport();
  const [form, setForm] = useState<SocialForm>(EMPTY_SOCIAL_FORM);
  const { state, run, reset } = useApiCall<CheckSocialProfileResponse>();
  const isLoading = state.status === "loading";

  const set = <K extends keyof SocialForm>(key: K, value: SocialForm[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const handleCheck = () => {
    run(() =>
      checkSocialProfile({
        platform: form.platform,
        has_profile_photo: form.has_profile_photo,
        profile_photo_is_stock: form.has_profile_photo ? form.profile_photo_is_stock : undefined,
        is_verified: form.is_verified,
        account_age_days: toOptionalInt(form.account_age_days),
        follower_count: toOptionalInt(form.follower_count),
        following_count: toOptionalInt(form.following_count),
        post_count: toOptionalInt(form.post_count),
        display_name: form.display_name.trim() || undefined,
        bio_text: form.bio_text.trim() || undefined,
      })
    );
  };

  const handleReset = () => {
    setForm(EMPTY_SOCIAL_FORM);
    reset();
  };

  const handleFileReport = () => {
    if (state.status !== "success") return;
    openReport({ matched_patterns: state.data.red_flags });
  };

  if (state.status === "success") {
    const r = state.data;
    return (
      <div className="glass-card rounded-xl p-6">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-ink-dim">{t("socialProfile.result.scoreLabel")}</span>
          <RiskBadge level={r.risk_level} />
        </div>
        <p className="mt-1 text-sm text-ink-dim">{r.total_score} pts</p>

        <div className="mt-4">
          <span className="text-sm font-medium text-ink-dim">{t("socialProfile.result.redFlagsLabel")}</span>
          {r.score_breakdown.length === 0 ? (
            <p className="mt-1 text-sm text-ink-dim/80">{t("socialProfile.result.noRedFlags")}</p>
          ) : (
            <ul className="mt-1.5 space-y-1.5">
              {r.score_breakdown.map((entry, i) => (
                <li
                  key={i}
                  className={clsx(
                    "flex items-start gap-2 rounded-lg p-2 text-xs",
                    entry.points > 0 ? "bg-risk-high-bg text-risk-high" : "bg-risk-low-bg text-risk-low"
                  )}
                >
                  <FileWarning className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  <span>
                    <span className="font-semibold">
                      {entry.flag} ({entry.points > 0 ? "+" : ""}
                      {entry.points}):
                    </span>{" "}
                    {entry.reason}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="mt-4 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">
          <span className="font-medium text-ink">{t("result.noteLabel")}: </span>
          {r.note}
        </div>

        <ReportPrompt show={RISKY.has(r.risk_level)} onFileReport={handleFileReport} />
        <CheckAnotherButton onReset={handleReset} />
      </div>
    );
  }

  return (
    <div className="glass-card flex flex-col gap-3 rounded-xl p-6">
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-ink-dim">{t("socialProfile.platformLabel")}</span>
        <select
          value={form.platform}
          onChange={(e) => set("platform", e.target.value as SocialForm["platform"])}
          className="w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        >
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {t(`socialProfile.platforms.${p}`)}
            </option>
          ))}
        </select>
      </label>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <TextField label={t("socialProfile.displayNameLabel")} value={form.display_name} onChange={(v) => set("display_name", v)} />
        <TextField label={t("socialProfile.accountAgeLabel")} type="number" value={form.account_age_days} onChange={(v) => set("account_age_days", v)} />
        <TextField label={t("socialProfile.followerCountLabel")} type="number" value={form.follower_count} onChange={(v) => set("follower_count", v)} />
        <TextField label={t("socialProfile.followingCountLabel")} type="number" value={form.following_count} onChange={(v) => set("following_count", v)} />
        <TextField label={t("socialProfile.postCountLabel")} type="number" value={form.post_count} onChange={(v) => set("post_count", v)} />
      </div>

      <label className="block">
        <span className="mb-1 block text-xs font-medium text-ink-dim">{t("socialProfile.bioTextLabel")}</span>
        <textarea
          value={form.bio_text}
          onChange={(e) => set("bio_text", e.target.value)}
          rows={2}
          className="w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        />
      </label>

      <div className="flex flex-wrap gap-4">
        <Checkbox label={t("socialProfile.hasProfilePhotoLabel")} checked={form.has_profile_photo} onChange={(v) => set("has_profile_photo", v)} />
        {form.has_profile_photo && (
          <Checkbox label={t("socialProfile.profilePhotoIsStockLabel")} checked={form.profile_photo_is_stock} onChange={(v) => set("profile_photo_is_stock", v)} />
        )}
        <Checkbox label={t("socialProfile.isVerifiedLabel")} checked={form.is_verified} onChange={(v) => set("is_verified", v)} />
      </div>

      {state.status === "error" && <ErrorBox error={state.error} />}

      <button
        type="button"
        onClick={handleCheck}
        disabled={isLoading}
        className={clsx(
          "flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity",
          isLoading && "cursor-not-allowed opacity-50"
        )}
      >
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {isLoading ? t("loading") : t("actions.check")}
      </button>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-dim">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        min={type === "number" ? 0 : undefined}
        className="w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
      />
    </label>
  );
}

function Checkbox({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-ink">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-border accent-brand"
      />
      {label}
    </label>
  );
}

// ── Digital arrest tab ────────────────────────────────────────────────────────

function DigitalArrestTab() {
  const { t, i18n } = useTranslation("checkLink");
  const { openReport } = useReport();
  const [transcript, setTranscript] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const { state, run, reset } = useApiCall<DigitalArrestResponse>();
  const isLoading = state.status === "loading";

  const handleCheck = () => {
    if (!transcript.trim()) {
      setClientError(t("digitalArrest.errors.empty"));
      return;
    }
    setClientError(null);
    run(() => checkDigitalArrest({ transcript: transcript.trim() }));
  };

  const handleReset = () => {
    setTranscript("");
    setClientError(null);
    reset();
  };

  const handleFileReport = () => {
    if (state.status !== "success") return;
    openReport({
      matched_patterns: state.data.matched_patterns,
      payment_indicators: state.data.payment_indicators_found,
    });
  };

  if (state.status === "success") {
    const r = state.data;
    return (
      <div className="glass-card rounded-xl p-6">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-ink-dim">{t("digitalArrest.result.severityLabel")}</span>
          <RiskBadge level={r.severity} />
        </div>

        <div className="mt-4">
          <span className="text-sm font-medium text-ink-dim">{t("digitalArrest.result.matchedPatternsLabel")}</span>
          {r.matched_patterns.length === 0 ? (
            <p className="mt-1 text-sm text-ink-dim/80">{t("digitalArrest.result.noPatterns")}</p>
          ) : (
            <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {r.matched_patterns.map((p, i) => (
                <li key={i} className="rounded-md bg-risk-high-bg px-2 py-1 font-mono text-xs text-risk-high">
                  {p}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="mt-4">
          <span className="text-sm font-medium text-ink-dim">{t("digitalArrest.result.paymentIndicatorsLabel")}</span>
          {r.payment_indicators_found.length === 0 ? (
            <p className="mt-1 text-sm text-ink-dim/80">{t("digitalArrest.result.noPaymentIndicators")}</p>
          ) : (
            <ul className="mt-1.5 flex flex-wrap gap-1.5">
              {r.payment_indicators_found.map((p, i) => (
                <li key={i} className="rounded-md bg-risk-medium-bg px-2 py-1 font-mono text-xs text-risk-medium">
                  {p}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="mt-4 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">
          <span className="font-medium text-ink">{t("digitalArrest.result.anchorLabel")}: </span>
          {translateHardFactualAnchor(r.hard_factual_anchor, i18n.language)}
        </div>

        <div className="mt-2 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">
          <span className="font-medium text-ink">{t("result.noteLabel")}: </span>
          {r.note}
        </div>

        <ReportPrompt show={RISKY.has(r.severity)} onFileReport={handleFileReport} />
        <CheckAnotherButton onReset={handleReset} />
      </div>
    );
  }

  return (
    <div className="glass-card rounded-xl p-6">
      <label className="block">
        <span className="mb-1 block text-sm font-medium text-ink-dim">{t("digitalArrest.transcriptLabel")}</span>
        <textarea
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          placeholder={t("digitalArrest.transcriptPlaceholder")}
          disabled={isLoading}
          rows={6}
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        />
      </label>

      {clientError && (
        <p className="mt-2 flex items-center gap-1.5 text-sm text-risk-high">
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
          {clientError}
        </p>
      )}
      {state.status === "error" && <ErrorBox error={state.error} />}

      <button
        type="button"
        onClick={handleCheck}
        disabled={isLoading}
        className={clsx(
          "mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity",
          isLoading && "cursor-not-allowed opacity-50"
        )}
      >
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {isLoading ? t("loading") : t("actions.check")}
      </button>
    </div>
  );
}
