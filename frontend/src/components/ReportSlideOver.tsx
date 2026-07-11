import { useState } from "react";
import { useTranslation } from "react-i18next";
import { X, Loader2, AlertTriangle, Copy, Check, ArrowLeft } from "lucide-react";
import clsx from "clsx";
import { useReport } from "@/context/ReportContext";
import { useApiCall } from "@/hooks/useApiCall";
import { generateComplaint, ApiError, NetworkError } from "@/api/client";
import type { ComplaintRequest, ComplaintResponse } from "@/api/types";

type FormFields = Omit<ComplaintRequest, "matched_patterns" | "payment_indicators">;

const EMPTY_FORM: FormFields = { complaint_type: "both" };

function Field({
  label,
  value,
  onChange,
  type = "text",
  textarea = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  textarea?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-dim">{label}</span>
      {textarea ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          className="w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        />
      ) : (
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        />
      )}
    </label>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-border pt-4 first:border-0 first:pt-0">
      <h3 className="mb-2 text-sm font-semibold text-ink">{title}</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">{children}</div>
    </div>
  );
}

export default function ReportSlideOver() {
  const { t } = useTranslation("report");
  const { t: tc } = useTranslation();
  const { isOpen, forwardedFields, closeReport } = useReport();
  const [form, setForm] = useState<FormFields>(EMPTY_FORM);
  const { state, run, reset } = useApiCall<ComplaintResponse>();
  const [copied, setCopied] = useState<"ncrp" | "bank" | null>(null);

  const set = <K extends keyof FormFields>(key: K, value: FormFields[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const handleClose = () => {
    closeReport();
    setForm(EMPTY_FORM);
    reset();
  };

  const handleSubmit = () => {
    run(() =>
      generateComplaint({
        ...form,
        matched_patterns: forwardedFields.matched_patterns,
        payment_indicators: forwardedFields.payment_indicators,
      })
    );
  };

  const copyText = async (which: "ncrp" | "bank", text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(which);
    setTimeout(() => setCopied(null), 1500);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-ink/30 backdrop-blur-sm" onClick={handleClose} />
      <div className="glass-card relative flex h-full w-full max-w-lg flex-col overflow-y-auto p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="font-display text-xl font-bold text-ink">{t("title")}</h2>
            {state.status !== "success" && (
              <p className="mt-1 text-sm text-ink-dim">{t("subtitle")}</p>
            )}
          </div>
          <button
            type="button"
            onClick={handleClose}
            aria-label={t("actions.close")}
            className="cursor-pointer rounded-md p-1.5 text-ink-dim hover:bg-ink/5 hover:text-ink"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {state.status === "success" ? (
          <div className="mt-5 flex flex-col gap-4">
            {state.data.ncrp_complaint_text && (
              <ReportText
                label={t("result.ncrpLabel")}
                text={state.data.ncrp_complaint_text}
                copied={copied === "ncrp"}
                onCopy={() => copyText("ncrp", state.data.ncrp_complaint_text!)}
                copyLabel={t("actions.copy")}
                copiedLabel={t("actions.copied")}
              />
            )}
            {state.data.bank_dispute_text && (
              <ReportText
                label={t("result.bankLabel")}
                text={state.data.bank_dispute_text}
                copied={copied === "bank"}
                onCopy={() => copyText("bank", state.data.bank_dispute_text!)}
                copyLabel={t("actions.copy")}
                copiedLabel={t("actions.copied")}
              />
            )}
            <div>
              <h3 className="text-sm font-semibold text-ink">{t("result.nextStepsLabel")}</h3>
              <ul className="mt-1.5 list-disc space-y-1 pl-5 text-sm text-ink-dim">
                {state.data.next_steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ul>
            </div>
            <button
              type="button"
              onClick={reset}
              className="mt-2 flex items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-ink hover:bg-ink/5"
            >
              <ArrowLeft className="h-4 w-4" /> {t("actions.back")}
            </button>
          </div>
        ) : (
          <div className="mt-5 flex flex-1 flex-col gap-4">
            {(forwardedFields.matched_patterns?.length ||
              forwardedFields.payment_indicators?.length) && (
              <div className="rounded-lg bg-brand-dim p-3 text-xs text-ink-dim">
                <p className="font-medium text-ink">{t("detectedPatterns")}</p>
                <p className="mt-1 font-mono">
                  {[
                    ...(forwardedFields.matched_patterns ?? []),
                    ...(forwardedFields.payment_indicators ?? []),
                  ].join(", ")}
                </p>
              </div>
            )}

            <label className="block">
              <span className="mb-1 block text-xs font-medium text-ink-dim">
                {t("fields.complaintType")}
              </span>
              <div className="flex gap-2">
                {(["ncrp", "bank_dispute", "both"] as const).map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => set("complaint_type", opt)}
                    className={clsx(
                      "flex-1 cursor-pointer rounded-md border px-2 py-1.5 text-xs font-medium transition-colors",
                      form.complaint_type === opt
                        ? "border-brand bg-brand-dim text-brand"
                        : "border-border text-ink-dim hover:bg-ink/5"
                    )}
                  >
                    {t(
                      `fields.complaintType${opt === "ncrp" ? "Ncrp" : opt === "bank_dispute" ? "BankDispute" : "Both"}`
                    )}
                  </button>
                ))}
              </div>
            </label>

            <Section title={t("sections.yourDetails")}>
              <Field label={t("fields.complainantName")} value={form.complainant_name ?? ""} onChange={(v) => set("complainant_name", v)} />
              <Field label={t("fields.complainantPhone")} value={form.complainant_phone ?? ""} onChange={(v) => set("complainant_phone", v)} />
              <Field label={t("fields.complainantEmail")} value={form.complainant_email ?? ""} onChange={(v) => set("complainant_email", v)} />
              <Field label={t("fields.complainantAddress")} value={form.complainant_address ?? ""} onChange={(v) => set("complainant_address", v)} />
            </Section>

            <Section title={t("sections.incident")}>
              <Field label={t("fields.incidentDate")} value={form.incident_date ?? ""} onChange={(v) => set("incident_date", v)} />
              <Field label={t("fields.platformUsed")} value={form.platform_used ?? ""} onChange={(v) => set("platform_used", v)} />
              <div className="sm:col-span-2">
                <Field label={t("fields.incidentDescription")} value={form.incident_description ?? ""} onChange={(v) => set("incident_description", v)} textarea />
              </div>
            </Section>

            <Section title={t("sections.financial")}>
              <Field label={t("fields.amountLost")} type="number" value={form.amount_lost?.toString() ?? ""} onChange={(v) => set("amount_lost", v ? Number(v) : null)} />
              <Field label={t("fields.paymentMode")} value={form.payment_mode ?? ""} onChange={(v) => set("payment_mode", v)} />
              <Field label={t("fields.transactionReference")} value={form.transaction_reference ?? ""} onChange={(v) => set("transaction_reference", v)} />
              <Field label={t("fields.transactionDate")} value={form.transaction_date ?? ""} onChange={(v) => set("transaction_date", v)} />
              <Field label={t("fields.recipientAccount")} value={form.recipient_account ?? ""} onChange={(v) => set("recipient_account", v)} />
              <Field label={t("fields.ncrpComplaintNumber")} value={form.ncrp_complaint_number ?? ""} onChange={(v) => set("ncrp_complaint_number", v)} />
            </Section>

            <Section title={t("sections.suspect")}>
              <Field label={t("fields.suspectName")} value={form.suspect_name ?? ""} onChange={(v) => set("suspect_name", v)} />
              <Field label={t("fields.suspectPhone")} value={form.suspect_phone ?? ""} onChange={(v) => set("suspect_phone", v)} />
              <Field label={t("fields.suspectUpiId")} value={form.suspect_upi_id ?? ""} onChange={(v) => set("suspect_upi_id", v)} />
              <Field label={t("fields.suspectClaimedAgency")} value={form.suspect_claimed_agency ?? ""} onChange={(v) => set("suspect_claimed_agency", v)} />
            </Section>

            <Section title={t("sections.bank")}>
              <Field label={t("fields.bankName")} value={form.bank_name ?? ""} onChange={(v) => set("bank_name", v)} />
              <Field label={t("fields.accountNumber")} value={form.account_number ?? ""} onChange={(v) => set("account_number", v)} />
            </Section>

            {state.status === "error" && (
              <div className="flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
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
              onClick={handleSubmit}
              disabled={state.status === "loading"}
              className={clsx(
                "mt-2 flex items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white",
                state.status === "loading" && "cursor-not-allowed opacity-60"
              )}
            >
              {state.status === "loading" && <Loader2 className="h-4 w-4 animate-spin" />}
              {state.status === "loading" ? t("loading") : t("actions.submit")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ReportText({
  label,
  text,
  copied,
  onCopy,
  copyLabel,
  copiedLabel,
}: {
  label: string;
  text: string;
  copied: boolean;
  onCopy: () => void;
  copyLabel: string;
  copiedLabel: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink">{label}</h3>
        <button
          type="button"
          onClick={onCopy}
          className="flex cursor-pointer items-center gap-1 text-xs font-medium text-brand hover:underline"
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? copiedLabel : copyLabel}
        </button>
      </div>
      <pre className="mt-1.5 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg bg-ink/5 p-3 font-mono text-xs text-ink">
        {text}
      </pre>
    </div>
  );
}
