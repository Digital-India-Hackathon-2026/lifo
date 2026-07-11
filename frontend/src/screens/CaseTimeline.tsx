import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, ChevronDown, ChevronUp, FolderPlus, Loader2, Plus } from "lucide-react";
import clsx from "clsx";
import { useApiCall } from "@/hooks/useApiCall";
import { ApiError, NetworkError, addCaseEvent, createCase, listCases } from "@/api/client";
import type { AddEventRequest, CaseFileResponse, CaseListResponse } from "@/api/types";

function errorMessage(error: ApiError | NetworkError | Error, tc: (key: string) => string): string {
  if (error instanceof NetworkError) return tc("errors.network");
  if (error instanceof ApiError) return error.body.error;
  return tc("errors.generic");
}

const EVENT_TYPES: AddEventRequest["event_type"][] = ["call", "whatsapp", "upi", "document", "other"];

function AddEventForm({ caseId, onAdded }: { caseId: string; onAdded: () => void }) {
  const { t } = useTranslation("caseTimeline");
  const { t: tc } = useTranslation();
  const [eventType, setEventType] = useState<AddEventRequest["event_type"]>("call");
  const [description, setDescription] = useState("");
  const { state, run } = useApiCall<unknown>();

  const handleAdd = async () => {
    if (!description.trim()) return;
    const data = await run(() =>
      addCaseEvent(caseId, {
        event_type: eventType,
        description,
        event_timestamp: new Date().toISOString(),
      })
    );
    if (data) {
      setDescription("");
      onAdded();
    }
  };

  return (
    <div className="mt-3 rounded-lg bg-ink/5 p-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <select
          value={eventType}
          onChange={(e) => setEventType(e.target.value as AddEventRequest["event_type"])}
          className="cursor-pointer rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        >
          {EVENT_TYPES.map((et) => (
            <option key={et} value={et}>
              {t(`eventTypes.${et}`)}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder={t("eventDescriptionPlaceholder")}
          className="flex-1 rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
        />
        <button
          type="button"
          onClick={handleAdd}
          disabled={state.status === "loading" || !description.trim()}
          className={clsx(
            "flex shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white",
            (state.status === "loading" || !description.trim()) && "cursor-not-allowed opacity-50"
          )}
        >
          {state.status === "loading" ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {t("addEvent")}
        </button>
      </div>
      {state.status === "error" && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-risk-high">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {errorMessage(state.error, tc)}
        </p>
      )}
    </div>
  );
}

function CaseCard({ caseFile, onChanged }: { caseFile: CaseFileResponse; onChanged: () => void }) {
  const { t } = useTranslation("caseTimeline");
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-border p-4">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full cursor-pointer items-center justify-between text-left"
      >
        <div>
          <p className="text-sm font-semibold text-ink">{caseFile.title}</p>
          <p className="text-xs text-ink-dim">
            {t("caseIdLabel")}: <span className="font-mono">{caseFile.case_id}</span> · {caseFile.events.length}{" "}
            {t("eventsCount")}
          </p>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 shrink-0 text-ink-dim" aria-hidden="true" />
        ) : (
          <ChevronDown className="h-4 w-4 shrink-0 text-ink-dim" aria-hidden="true" />
        )}
      </button>

      {expanded && (
        <div className="mt-3 border-t border-border pt-3">
          {caseFile.events.length === 0 ? (
            <p className="text-xs text-ink-dim/80">{t("noEvents")}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {caseFile.events.map((ev, i) => (
                <li key={i} className="rounded-md bg-ink/5 p-2.5 text-xs">
                  <span className="rounded bg-brand-dim px-1.5 py-0.5 font-medium text-brand">
                    {t(`eventTypes.${ev.event_type}`)}
                  </span>
                  <span className="ml-2 text-ink">{ev.description}</span>
                  <span className="mt-1 block text-ink-dim">
                    {new Date(ev.event_timestamp).toLocaleString()}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <AddEventForm caseId={caseFile.case_id} onAdded={onChanged} />
        </div>
      )}
    </div>
  );
}

export default function CaseTimeline() {
  const { t } = useTranslation("caseTimeline");
  const { t: tc } = useTranslation();
  const [userId, setUserId] = useState("");
  const [activeUserId, setActiveUserId] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const listCall = useApiCall<CaseListResponse>();
  const createCall = useApiCall<CaseFileResponse>();

  const refetch = (uid: string) => listCall.run(() => listCases(uid));

  const handleLoad = () => {
    if (!userId.trim()) return;
    setActiveUserId(userId);
    refetch(userId);
  };

  const handleCreateCase = async () => {
    if (!activeUserId || !newTitle.trim()) return;
    const data = await createCall.run(() => createCase({ user_id: activeUserId, title: newTitle }));
    if (data) {
      setNewTitle("");
      refetch(activeUserId);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-2xl font-bold text-ink">{t("title")}</h1>
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
              onClick={handleLoad}
              disabled={!userId.trim() || listCall.state.status === "loading"}
              className={clsx(
                "cursor-pointer rounded-md bg-brand px-4 py-2 text-sm font-medium text-white",
                (!userId.trim() || listCall.state.status === "loading") && "cursor-not-allowed opacity-50"
              )}
            >
              {t("load")}
            </button>
          </div>
        </label>

        {activeUserId && (
          <div className="mt-4 flex gap-2">
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder={t("newCaseTitlePlaceholder")}
              className="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/30"
            />
            <button
              type="button"
              onClick={handleCreateCase}
              disabled={createCall.state.status === "loading" || !newTitle.trim()}
              className={clsx(
                "flex shrink-0 cursor-pointer items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-ink hover:bg-ink/5",
                (createCall.state.status === "loading" || !newTitle.trim()) && "cursor-not-allowed opacity-50"
              )}
            >
              {createCall.state.status === "loading" ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <FolderPlus className="h-4 w-4" aria-hidden="true" />
              )}
              {t("newCase")}
            </button>
          </div>
        )}
      </div>

      {listCall.state.status === "loading" && (
        <p className="mt-4 flex items-center gap-1.5 text-sm text-ink-dim">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          {t("loading")}
        </p>
      )}

      {listCall.state.status === "error" && (
        <div className="mt-4 flex items-start gap-2 rounded-lg bg-risk-high-bg p-3 text-sm text-risk-high">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p>{errorMessage(listCall.state.error, tc)}</p>
        </div>
      )}

      {listCall.state.status === "success" && listCall.state.data.cases.length === 0 && (
        <p className="mt-4 text-sm text-ink-dim/80">{t("emptyState")}</p>
      )}

      {listCall.state.status === "success" && listCall.state.data.cases.length > 0 && (
        <div className="mt-5 flex flex-col gap-3">
          {listCall.state.data.cases.map((c) => (
            <CaseCard key={c.case_id} caseFile={c} onChanged={() => activeUserId && refetch(activeUserId)} />
          ))}
        </div>
      )}
    </div>
  );
}
