import type {
  AddEventRequest,
  AnnualReportResponse,
  AssetHoldRequest,
  AssetTrackerResponse,
  BlocklistCheckResponse,
  CampaignEventResponse,
  CaseFileResponse,
  CaseListResponse,
  CheckPhishingResponse,
  CheckSocialProfileResponse,
  ClassifyAudioResponse,
  ClassifyDocumentResponse,
  ClassifyImageResponse,
  ClassifyVideoResponse,
  ComplaintRequest,
  ComplaintResponse,
  ConsentGrantRequest,
  ConsentRevokeRequest,
  ConsentResponse,
  ContentLibraryResponse,
  ConverseResponse,
  CreateCaseRequest,
  DigitalArrestRequest,
  DigitalArrestResponse,
  DisputeEscalationResponse,
  DisputeStatusResponse,
  DisputeTrackRequest,
  DisputeTrackResponse,
  ErrorResponse,
  EZeroFIRRequest,
  EZeroFIRResponse,
  HeatmapResponse,
  PairDevicesRequest,
  PairDevicesResponse,
  PanicAlertRequest,
  PanicTriggerResponse,
  PhishingRequest,
  ReportResponse,
  ScamCheckResponse,
  ScamReportRequest,
  ScamReportResponse,
  SocialProfileRequest,
  StartSessionResponse,
  TrainingAnswerRequest,
  TrainingAnswerResponse,
  TrainingDrillResponse,
  TranscriptRequest,
  VaultSetRequest,
  VaultSetResponse,
  VaultVerifyRequest,
  VaultVerifyResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/**
 * Thrown for every non-2xx response. Always carries the backend's guaranteed-JSON
 * error contract ({error, status_code, detail}) — main.py's global exception
 * handlers mean this shape is never plain text, even for a 500.
 */
export class ApiError extends Error {
  status: number;
  body: ErrorResponse;

  constructor(body: ErrorResponse) {
    super(body.error);
    this.name = "ApiError";
    this.status = body.status_code;
    this.body = body;
  }
}

/** Thrown when the network request itself fails (backend unreachable, CORS, offline). */
export class NetworkError extends Error {
  cause: unknown;
  constructor(cause: unknown) {
    super("Could not reach the server.");
    this.name = "NetworkError";
    this.cause = cause;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, init);
  } catch (err) {
    throw new NetworkError(err);
  }

  // main.py's exception handlers guarantee every response is JSON, success or error.
  const body = await res.json();

  if (!res.ok) {
    throw new ApiError(body as ErrorResponse);
  }
  return body as T;
}

function postJson<T>(path: string, payload: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function postFile<T>(path: string, file: File, extraFields?: Record<string, string>): Promise<T> {
  const form = new FormData();
  if (extraFields) {
    for (const [key, value] of Object.entries(extraFields)) form.append(key, value);
  }
  form.append("file", file);
  return request<T>(path, { method: "POST", body: form });
}

// ── Media Verdict ────────────────────────────────────────────────────────────

export const classifyImage = (file: File) =>
  postFile<ClassifyImageResponse>("/classify/image", file);

export const classifyVideo = (file: File) =>
  postFile<ClassifyVideoResponse>("/classify/video", file);

export const classifyAudio = (file: File) =>
  postFile<ClassifyAudioResponse>("/classify/audio", file);

// ── Document check ───────────────────────────────────────────────────────────

export const classifyDocument = (file: File) =>
  postFile<ClassifyDocumentResponse>("/classify/document", file);

// ── Check a link, profile, or call ───────────────────────────────────────────

export const checkPhishing = (payload: PhishingRequest) =>
  postJson<CheckPhishingResponse>("/check/phishing", payload);

export const checkSocialProfile = (payload: SocialProfileRequest) =>
  postJson<CheckSocialProfileResponse>("/check/social-profile", payload);

export const checkDigitalArrest = (payload: DigitalArrestRequest) =>
  postJson<DigitalArrestResponse>("/check/digital-arrest", payload);

// ── Complaint assistant ───────────────────────────────────────────────────────

export const generateComplaint = (payload: ComplaintRequest) =>
  postJson<ComplaintResponse>("/assist/complaint", payload);

// ── Safe-word vault ───────────────────────────────────────────────────────────

export const setSafeWord = (payload: VaultSetRequest) =>
  postJson<VaultSetResponse>("/vault/set", payload);

export const verifySafeWord = (payload: VaultVerifyRequest) =>
  postJson<VaultVerifyResponse>("/vault/verify", payload);

// ── Honeypot ──────────────────────────────────────────────────────────────────

export const startHoneypotSession = () =>
  request<StartSessionResponse>("/honeypot/start", { method: "POST" });

export const honeypotConverse = (sessionId: string, file: File) =>
  postFile<ConverseResponse>("/honeypot/converse", file, { session_id: sessionId });

export const getHoneypotReport = (sessionId: string) =>
  request<ReportResponse>(`/honeypot/report/${encodeURIComponent(sessionId)}`);

// ── News & Awareness ──────────────────────────────────────────────────────────

export const getContentLibrary = (params: { language: string; target_audience?: "general" | "elderly" }) => {
  const search = new URLSearchParams({ language: params.language });
  if (params.target_audience) search.set("target_audience", params.target_audience);
  return request<ContentLibraryResponse>(`/education/content-library?${search.toString()}`);
};

export const getAnnualReport = () => request<AnnualReportResponse>("/education/annual-report");

// ── Fraud Type Scanner — all 21 real /scams/*/check detectors ─────────────────
// One source of truth for which detectors actually exist as live backend
// routes (confirmed via `grep -rn 'router = APIRouter(prefix="/scams'
// app/routers/*.py` — 21, not 30) — the screen's dropdown reuses this list
// rather than redefining it.
export const SCAM_DETECTORS = [
  "romance",
  "investment",
  "lottery",
  "courier",
  "bec",
  "matrimonial",
  "gov-scheme",
  "qr",
  "exam",
  "ecommerce",
  "ussd",
  "recruitment",
  "job",
  "loan",
  "sextortion",
  "challan",
  "customercare",
  "kyc",
  "rental",
  "reward",
  "utility",
] as const;

export type ScamDetector = (typeof SCAM_DETECTORS)[number];

export const checkScam = (detector: ScamDetector, payload: TranscriptRequest) =>
  postJson<ScamCheckResponse>(`/scams/${detector}/check`, payload);

// ── Report a Scam ────────────────────────────────────────────────────────────

export const submitScamReport = (payload: ScamReportRequest) =>
  postJson<ScamReportResponse>("/community/report", payload);

export const getHeatmap = () => request<HeatmapResponse>("/community/heatmap");

// ── Family Protection ────────────────────────────────────────────────────────

export const pairDevices = (payload: PairDevicesRequest) =>
  postJson<PairDevicesResponse>("/vulnerable/pair-devices", payload);

export const triggerPanic = (payload: PanicAlertRequest) =>
  postJson<PanicTriggerResponse>("/vulnerable/panic-trigger", payload);

export const getTrainingDrill = () => request<TrainingDrillResponse>("/vulnerable/training/drill");

export const answerTrainingDrill = (payload: TrainingAnswerRequest) =>
  postJson<TrainingAnswerResponse>("/vulnerable/training/answer", payload);

// ── Legal & Recovery ──────────────────────────────────────────────────────────

export const generateEzeroFir = (payload: EZeroFIRRequest) =>
  postJson<EZeroFIRResponse>("/legal/templates/ezero-fir", payload);

export const trackDispute = (payload: DisputeTrackRequest) =>
  postJson<DisputeTrackResponse>("/legal/dispute/track", payload);

export const getDisputeStatus = (caseId: string) =>
  request<DisputeStatusResponse>(`/legal/dispute/${encodeURIComponent(caseId)}/status`);

export const escalateDispute = (caseId: string) =>
  request<DisputeEscalationResponse>(`/legal/dispute/${encodeURIComponent(caseId)}/escalate`, {
    method: "POST",
  });

export const createAssetHold = (payload: AssetHoldRequest) =>
  postJson<AssetTrackerResponse>("/legal/asset-tracker/hold", payload);

export const getAssetHold = (caseId: string) =>
  request<AssetTrackerResponse>(`/legal/asset-tracker/${encodeURIComponent(caseId)}`);

// ── Privacy & Consent ─────────────────────────────────────────────────────────

export const grantConsent = (payload: ConsentGrantRequest) =>
  postJson<ConsentResponse>("/compliance/consent/grant", payload);

export const revokeConsent = (payload: ConsentRevokeRequest) =>
  postJson<ConsentResponse>("/compliance/consent/revoke", payload);

export const getConsentStatus = (params: { user_id: string; purpose: string }) =>
  request<ConsentResponse>(`/compliance/consent/status?${new URLSearchParams(params).toString()}`);

// ── Quick Safety Check ────────────────────────────────────────────────────────

export const checkBlocklist = (indicator: string) =>
  request<BlocklistCheckResponse>(`/blocklist/check?indicator=${encodeURIComponent(indicator)}`);

// ── My Scam Case Timeline ───────────────────────────────────────────────────────

export const createCase = (payload: CreateCaseRequest) =>
  postJson<CaseFileResponse>("/timeline/cases", payload);

export const addCaseEvent = (caseId: string, payload: AddEventRequest) =>
  postJson<CampaignEventResponse>(`/timeline/cases/${encodeURIComponent(caseId)}/events`, payload);

export const getCase = (caseId: string) =>
  request<CaseFileResponse>(`/timeline/cases/${encodeURIComponent(caseId)}`);

export const listCases = (userId: string) =>
  request<CaseListResponse>(`/timeline/cases?user_id=${encodeURIComponent(userId)}`);
