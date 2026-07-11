import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, FileText, Gavel, Loader2, Scale, Send } from "lucide-react";
import clsx from "clsx";
import { useApiCall } from "@/hooks/useApiCall";
import {
  ApiError,
  NetworkError,
  createAssetHold,
  escalateDispute,
  generateComplaint,
  generateEzeroFir,
  getAssetHold,
  getDisputeStatus,
  trackDispute,
} from "@/api/client";
import type {
  AssetTrackerResponse,
  ComplaintResponse,
  DisputeEscalationResponse,
  DisputeStatusResponse,
  DisputeTrackResponse,
  EZeroFIRResponse,
} from "@/api/types";

function errorMessage(error: ApiError | NetworkError | Error, tc: (key: string) => string): string {
  if (error instanceof NetworkError) return tc("errors.network");
  if (error instanceof ApiError) return error.body.error;
  return tc("errors.generic");
}

const inputCls =
  "w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30";
const buttonCls =
  "mt-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2.5 font-medium text-white transition-opacity";

function ComplaintCard() {
  const { t } = useTranslation("legalRecovery");
  const { t: tc } = useTranslation();
  const [complaintType, setComplaintType] = useState<"ncrp" | "bank_dispute" | "both">("ncrp");
  const [name, setName] = useState("");
  const [incident, setIncident] = useState("");
  const { state, run } = useApiCall<ComplaintResponse>();

  return (
    <div className="glass-card rounded-xl p-6">
      <div className="flex items-center gap-2">
        <FileText className="h-4 w-4 text-brand" aria-hidden="true" />
        <h2 className="font-display text-sm font-semibold text-ink">{t("complaint.heading")}</h2>
      </div>
      <p className="mt-1 text-sm text-ink-dim">{t("complaint.description")}</p>

      <label className="mt-4 block">
        <span className="mb-1 block text-xs font-medium text-ink-dim">{t("complaint.typeLabel")}</span>
        <select
          value={complaintType}
          onChange={(e) => setComplaintType(e.target.value as typeof complaintType)}
          className={clsx(inputCls, "cursor-pointer")}
        >
          <option value="ncrp">{t("complaint.typeNcrp")}</option>
          <option value="bank_dispute">{t("complaint.typeBankDispute")}</option>
          <option value="both">{t("complaint.typeBoth")}</option>
        </select>
      </label>

      <label className="mt-3 block">
        <span className="mb-1 block text-xs font-medium text-ink-dim">{t("complaint.nameLabel")}</span>
        <input type="text" value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
      </label>

      <label className="mt-3 block">
        <span className="mb-1 block text-xs font-medium text-ink-dim">{t("complaint.incidentLabel")}</span>
        <textarea
          value={incident}
          onChange={(e) => setIncident(e.target.value)}
          rows={3}
          className={clsx(inputCls, "resize-none")}
        />
      </label>

      {state.status === "error" && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>{errorMessage(state.error, tc)}</p>
        </div>
      )}

      {state.status === "success" && (
        <div className="mt-3 flex flex-col gap-2">
          {state.data.ncrp_complaint_text && (
            <details className="rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">
              <summary className="cursor-pointer font-medium text-ink">{t("complaint.ncrpTextLabel")}</summary>
              <pre className="mt-2 whitespace-pre-wrap font-sans">{state.data.ncrp_complaint_text}</pre>
            </details>
          )}
          {state.data.bank_dispute_text && (
            <details className="rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">
              <summary className="cursor-pointer font-medium text-ink">{t("complaint.bankTextLabel")}</summary>
              <pre className="mt-2 whitespace-pre-wrap font-sans">{state.data.bank_dispute_text}</pre>
            </details>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={() =>
          run(() =>
            generateComplaint({
              complaint_type: complaintType,
              complainant_name: name || undefined,
              incident_description: incident || undefined,
            })
          )
        }
        disabled={state.status === "loading"}
        className={clsx(buttonCls, state.status === "loading" && "cursor-not-allowed opacity-50")}
      >
        {state.status === "loading" ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <Send className="h-4 w-4" aria-hidden="true" />
        )}
        {t("complaint.submit")}
      </button>
    </div>
  );
}

function EZeroFirCard() {
  const { t } = useTranslation("legalRecovery");
  const { t: tc } = useTranslation();
  const [category, setCategory] = useState("");
  const { state, run } = useApiCall<EZeroFIRResponse>();

  return (
    <div className="glass-card rounded-xl p-6">
      <div className="flex items-center gap-2">
        <Gavel className="h-4 w-4 text-brand" aria-hidden="true" />
        <h2 className="font-display text-sm font-semibold text-ink">{t("ezeroFir.heading")}</h2>
      </div>
      <p className="mt-1 text-sm text-ink-dim">{t("ezeroFir.description")}</p>

      <label className="mt-4 block">
        <span className="mb-1 block text-xs font-medium text-ink-dim">{t("ezeroFir.categoryLabel")}</span>
        <input
          type="text"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          placeholder={t("ezeroFir.categoryPlaceholder")}
          className={inputCls}
        />
      </label>

      {state.status === "error" && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>{errorMessage(state.error, tc)}</p>
        </div>
      )}

      {state.status === "success" && (
        <div className="mt-3 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">
          <p>
            <span className="font-medium text-ink">{t("ezeroFir.hashLabel")}:</span> {state.data.fir_hash}
          </p>
          <p className="mt-1">
            <span className="font-medium text-ink">{t("ezeroFir.statuteLabel")}:</span> {state.data.statute}
          </p>
          <p className="mt-1">
            <span className="font-medium text-ink">{t("ezeroFir.statusLabel")}:</span> {state.data.status}
          </p>
        </div>
      )}

      <button
        type="button"
        onClick={() => run(() => generateEzeroFir({ category }))}
        disabled={state.status === "loading" || !category.trim()}
        className={clsx(
          buttonCls,
          (state.status === "loading" || !category.trim()) && "cursor-not-allowed opacity-50"
        )}
      >
        {state.status === "loading" && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {t("ezeroFir.submit")}
      </button>
    </div>
  );
}

function DisputeCard() {
  const { t } = useTranslation("legalRecovery");
  const { t: tc } = useTranslation();
  const [userId, setUserId] = useState("");
  const [bankName, setBankName] = useState("");
  const [txnRef, setTxnRef] = useState("");
  const trackCall = useApiCall<DisputeTrackResponse>();

  const [statusCaseId, setStatusCaseId] = useState("");
  const statusCall = useApiCall<DisputeStatusResponse>();
  const escalateCall = useApiCall<DisputeEscalationResponse>();

  return (
    <div className="glass-card rounded-xl p-6">
      <div className="flex items-center gap-2">
        <Scale className="h-4 w-4 text-brand" aria-hidden="true" />
        <h2 className="font-display text-sm font-semibold text-ink">{t("dispute.heading")}</h2>
      </div>
      <p className="mt-1 text-sm text-ink-dim">{t("dispute.description")}</p>

      <div className="mt-4">
        <span className="text-xs font-semibold uppercase tracking-wide text-brand">{t("dispute.trackHeading")}</span>
        <label className="mt-2 block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("dispute.userIdLabel")}</span>
          <input type="text" value={userId} onChange={(e) => setUserId(e.target.value)} className={inputCls} />
        </label>
        <label className="mt-3 block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("dispute.bankNameLabel")}</span>
          <input type="text" value={bankName} onChange={(e) => setBankName(e.target.value)} className={inputCls} />
        </label>
        <label className="mt-3 block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("dispute.txnRefLabel")}</span>
          <input type="text" value={txnRef} onChange={(e) => setTxnRef(e.target.value)} className={inputCls} />
        </label>

        {trackCall.state.status === "error" && (
          <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p>{errorMessage(trackCall.state.error, tc)}</p>
          </div>
        )}

        {trackCall.state.status === "success" && (
          <div className="mt-3 rounded-lg bg-brand-dim p-3 text-xs text-brand">
            {t("dispute.trackedAs")}: <span className="font-mono">{trackCall.state.data.case_id}</span>
          </div>
        )}

        <button
          type="button"
          onClick={() =>
            trackCall.run(() =>
              trackDispute({
                complaint_type: "bank_dispute",
                user_id: userId,
                bank_name: bankName,
                transaction_reference: txnRef,
              })
            )
          }
          disabled={trackCall.state.status === "loading" || !userId.trim() || !bankName.trim() || !txnRef.trim()}
          className={clsx(
            buttonCls,
            (trackCall.state.status === "loading" || !userId.trim() || !bankName.trim() || !txnRef.trim()) &&
              "cursor-not-allowed opacity-50"
          )}
        >
          {trackCall.state.status === "loading" && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {t("dispute.trackSubmit")}
        </button>
      </div>

      <div className="mt-6 border-t border-border pt-4">
        <span className="text-xs font-semibold uppercase tracking-wide text-brand">
          {t("dispute.statusHeading")}
        </span>
        <label className="mt-2 block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("dispute.caseIdLabel")}</span>
          <input
            type="text"
            value={statusCaseId}
            onChange={(e) => setStatusCaseId(e.target.value)}
            placeholder="DISP-..."
            className={inputCls}
          />
        </label>

        {statusCall.state.status === "error" && (
          <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p>{errorMessage(statusCall.state.error, tc)}</p>
          </div>
        )}

        {statusCall.state.status === "success" && (
          <div className="mt-3 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">
            <p>
              <span className="font-medium text-ink">{t("dispute.statusLabel")}:</span> {statusCall.state.data.status}
            </p>
            <p className="mt-1">
              <span className="font-medium text-ink">{t("dispute.overdueLabel")}:</span>{" "}
              {statusCall.state.data.is_overdue ? t("dispute.yes") : t("dispute.no")}
            </p>
          </div>
        )}

        {escalateCall.state.status === "error" && (
          <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p>{errorMessage(escalateCall.state.error, tc)}</p>
          </div>
        )}

        {escalateCall.state.status === "success" && (
          <div className="mt-3 rounded-lg bg-risk-high-bg p-3 text-xs text-risk-high">
            {escalateCall.state.data.escalation_text}
          </div>
        )}

        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => statusCall.run(() => getDisputeStatus(statusCaseId))}
            disabled={statusCall.state.status === "loading" || !statusCaseId.trim()}
            className={clsx(
              "flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 font-medium text-ink hover:bg-ink/5",
              (statusCall.state.status === "loading" || !statusCaseId.trim()) && "cursor-not-allowed opacity-50"
            )}
          >
            {statusCall.state.status === "loading" && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
            {t("dispute.checkStatus")}
          </button>
          <button
            type="button"
            onClick={() => escalateCall.run(() => escalateDispute(statusCaseId))}
            disabled={escalateCall.state.status === "loading" || !statusCaseId.trim()}
            className={clsx(
              "flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-lg bg-risk-high px-4 py-2.5 font-medium text-white",
              (escalateCall.state.status === "loading" || !statusCaseId.trim()) && "cursor-not-allowed opacity-50"
            )}
          >
            {escalateCall.state.status === "loading" && (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            )}
            {t("dispute.escalate")}
          </button>
        </div>
      </div>
    </div>
  );
}

function AssetTrackerCard() {
  const { t } = useTranslation("legalRecovery");
  const { t: tc } = useTranslation();
  const [caseId, setCaseId] = useState("");
  const [amount, setAmount] = useState("");
  const [bankNode, setBankNode] = useState("");
  const holdCall = useApiCall<AssetTrackerResponse>();

  const [lookupCaseId, setLookupCaseId] = useState("");
  const lookupCall = useApiCall<AssetTrackerResponse>();

  return (
    <div className="glass-card rounded-xl p-6">
      <h2 className="font-display text-sm font-semibold text-ink">{t("assetTracker.heading")}</h2>
      <p className="mt-1 text-sm text-ink-dim">{t("assetTracker.description")}</p>

      <div className="mt-4">
        <span className="text-xs font-semibold uppercase tracking-wide text-brand">
          {t("assetTracker.createHeading")}
        </span>
        <label className="mt-2 block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("assetTracker.caseIdLabel")}</span>
          <input type="text" value={caseId} onChange={(e) => setCaseId(e.target.value)} className={inputCls} />
        </label>
        <label className="mt-3 block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("assetTracker.amountLabel")}</span>
          <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} className={inputCls} />
        </label>
        <label className="mt-3 block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("assetTracker.bankNodeLabel")}</span>
          <input type="text" value={bankNode} onChange={(e) => setBankNode(e.target.value)} className={inputCls} />
        </label>

        {holdCall.state.status === "error" && (
          <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p>{errorMessage(holdCall.state.error, tc)}</p>
          </div>
        )}

        {holdCall.state.status === "success" && (
          <div className="mt-3 flex items-center justify-between rounded-lg bg-brand-dim p-3 text-xs text-brand">
            <span>{t("assetTracker.holdCreated")}</span>
            <span className="font-semibold">{holdCall.state.data.status}</span>
          </div>
        )}

        <button
          type="button"
          onClick={() =>
            holdCall.run(() =>
              createAssetHold({ case_id: caseId, frozen_amount: Number(amount), bank_node: bankNode })
            )
          }
          disabled={holdCall.state.status === "loading" || !caseId.trim() || !amount.trim() || !bankNode.trim()}
          className={clsx(
            buttonCls,
            (holdCall.state.status === "loading" || !caseId.trim() || !amount.trim() || !bankNode.trim()) &&
              "cursor-not-allowed opacity-50"
          )}
        >
          {holdCall.state.status === "loading" && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {t("assetTracker.createSubmit")}
        </button>
      </div>

      <div className="mt-6 border-t border-border pt-4">
        <span className="text-xs font-semibold uppercase tracking-wide text-brand">
          {t("assetTracker.lookupHeading")}
        </span>
        <label className="mt-2 block">
          <span className="mb-1 block text-xs font-medium text-ink-dim">{t("assetTracker.caseIdLabel")}</span>
          <input
            type="text"
            value={lookupCaseId}
            onChange={(e) => setLookupCaseId(e.target.value)}
            className={inputCls}
          />
        </label>

        {lookupCall.state.status === "error" && (
          <div className="mt-3 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p>{errorMessage(lookupCall.state.error, tc)}</p>
          </div>
        )}

        {lookupCall.state.status === "success" && (
          <div className="mt-3 rounded-lg bg-ink/5 p-3 text-xs text-ink-dim">
            <p>
              <span className="font-medium text-ink">{t("assetTracker.amountLabel")}:</span> ₹
              {lookupCall.state.data.frozen_amount.toLocaleString()}
            </p>
            <p className="mt-1">
              <span className="font-medium text-ink">{t("assetTracker.statusLabel")}:</span>{" "}
              {lookupCall.state.data.status}
            </p>
          </div>
        )}

        <button
          type="button"
          onClick={() => lookupCall.run(() => getAssetHold(lookupCaseId))}
          disabled={lookupCall.state.status === "loading" || !lookupCaseId.trim()}
          className={clsx(
            "mt-3 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 font-medium text-ink hover:bg-ink/5",
            (lookupCall.state.status === "loading" || !lookupCaseId.trim()) && "cursor-not-allowed opacity-50"
          )}
        >
          {lookupCall.state.status === "loading" && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {t("assetTracker.lookupSubmit")}
        </button>
      </div>
    </div>
  );
}

export default function LegalRecovery() {
  const { t } = useTranslation("legalRecovery");

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-2xl font-bold text-ink">{t("title")}</h1>
      <p className="mt-1 text-ink-dim">{t("description")}</p>

      <div className="mt-6 flex flex-col gap-5">
        <ComplaintCard />
        <EZeroFirCard />
        <DisputeCard />
        <AssetTrackerCard />
      </div>
    </div>
  );
}
