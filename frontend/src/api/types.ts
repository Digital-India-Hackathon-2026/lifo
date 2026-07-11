/**
 * Mirrors backend/app/models/responses.py exactly — field names, nullability,
 * and literal unions read directly from the Pydantic source, not guessed.
 */

export interface ErrorResponse {
  error: string;
  status_code: number;
  detail: unknown;
}

// ── Media Verdict ────────────────────────────────────────────────────────────

export interface SuspiciousFrame {
  frame_index: number;
  fake_score: number;
}

export interface ClassifyImageResponse {
  verdict: "real" | "ai_generated";
  confidence_score: number;
  note: string;
  model: string;
  disclaimer: string;
}

export interface ClassifyVideoResponse {
  verdict: "real" | "ai_generated";
  confidence_score: number;
  note: string;
  frames_sampled: number;
  most_suspicious_frame: SuspiciousFrame;
  model: string;
  disclaimer: string;
}

export interface ClassifyAudioResponse {
  verdict: "genuine" | "spoof";
  confidence_score: number;
  note: string;
  /** null only when the audio is shorter than one analysis window (< 3s). */
  anomaly_timestamp: number | null;
  model: string;
  disclaimer: string;
}

// ── Document check ───────────────────────────────────────────────────────────

export interface ScamIndicator {
  type: string;
  matched_text: string;
}

export interface PIIMatch {
  type: "aadhaar" | "pan";
  masked_value: string;
}

export interface ClassifyDocumentResponse {
  ocr_text: string;
  pii_detected: PIIMatch[];
  scam_indicators: ScamIndicator[];
  risk_level: "low" | "medium" | "high";
  note: string;
  disclaimer: string;
}

// ── Phishing check ────────────────────────────────────────────────────────────

export interface PhishingRequest {
  url: string;
}

export interface CheckPhishingResponse {
  domain: string;
  in_blocklist: boolean;
  blocklist_match: string | null;
  similarity_score: number;
  matched_against: string | null;
  risk_level: "low" | "medium" | "high";
  note: string;
  disclaimer: string;
}

// ── Vault ─────────────────────────────────────────────────────────────────────

export interface VaultSetRequest {
  safe_word: string;
}

export interface VaultSetResponse {
  message: string;
  note: string;
}

export interface VaultVerifyRequest {
  safe_word: string;
}

export interface VaultVerifyResponse {
  matches: boolean;
  note: string;
  disclaimer: string;
}

// ── Complaint assistant ───────────────────────────────────────────────────────

export interface ComplaintRequest {
  complaint_type: "ncrp" | "bank_dispute" | "both";
  complainant_name?: string | null;
  complainant_phone?: string | null;
  complainant_email?: string | null;
  complainant_address?: string | null;
  incident_date?: string | null;
  incident_description?: string | null;
  platform_used?: string | null;
  suspect_name?: string | null;
  suspect_phone?: string | null;
  suspect_upi_id?: string | null;
  suspect_claimed_agency?: string | null;
  amount_lost?: number | null;
  payment_mode?: string | null;
  transaction_reference?: string | null;
  transaction_date?: string | null;
  recipient_account?: string | null;
  bank_name?: string | null;
  account_number?: string | null;
  ncrp_complaint_number?: string | null;
  matched_patterns?: string[] | null;
  payment_indicators?: string[] | null;
}

export interface ComplaintResponse {
  ncrp_complaint_text: string | null;
  bank_dispute_text: string | null;
  next_steps: string[];
  disclaimer: string;
}

// ── Digital Arrest pattern check ──────────────────────────────────────────────

export interface DigitalArrestRequest {
  /** Provide exactly one of transcript or session_id. */
  transcript?: string | null;
  session_id?: string | null;
}

export interface DigitalArrestResponse {
  matched_patterns: string[];
  payment_indicators_found: string[];
  severity: "low" | "medium" | "high";
  hard_factual_anchor: string;
  note: string;
  disclaimer: string;
}

// ── Social profile check ──────────────────────────────────────────────────────

export interface SocialProfileRequest {
  platform: "instagram" | "facebook" | "twitter" | "whatsapp" | "telegram" | "other";
  has_profile_photo: boolean;
  profile_photo_is_stock?: boolean | null;
  account_age_days?: number | null;
  follower_count?: number | null;
  following_count?: number | null;
  post_count?: number | null;
  bio_text?: string | null;
  display_name?: string | null;
  is_verified?: boolean;
}

export interface ScoreEntry {
  flag: string;
  points: number;
  reason: string;
}

export interface CheckSocialProfileResponse {
  risk_level: "low" | "medium" | "high";
  total_score: number;
  red_flags: string[];
  score_breakdown: ScoreEntry[];
  note: string;
  disclaimer: string;
}

// ── Honeypot ──────────────────────────────────────────────────────────────────

export interface StartSessionResponse {
  session_id: string;
}

export interface TurnSignals {
  upi_ids: string[];
  phone_numbers: string[];
  bank_accounts: string[];
  scripted_phrases: string[];
}

export interface CumulativeIntel {
  upi_ids: string[];
  phone_numbers: string[];
  bank_accounts: string[];
  scripted_phrases: string[];
}

export interface ConverseResponse {
  session_id: string;
  turn: number;
  /** null when STT fails */
  transcript: string | null;
  /** null when Persona fails or STT fails */
  persona_reply_text: string | null;
  /** base64 MP3; null when TTS fails/unavailable */
  persona_reply_audio: string | null;
  signals_this_turn: TurnSignals;
  cumulative_intel: CumulativeIntel;
  /** 4 entries: STT / Persona / TTS / Extraction */
  stage_log: string[];
}

export interface TurnHistoryItem {
  turn: number;
  transcript: string | null;
  persona_reply: string | null;
}

export interface ReportResponse {
  session_id: string;
  turn_count: number;
  cumulative_intel: CumulativeIntel;
  turn_history: TurnHistoryItem[];
}

// ── News & Awareness ──────────────────────────────────────────────────────────

export interface VideoContent {
  id: string;
  lang: string;
  title: string;
  url: string;
  tags: string[];
  target_audience: "general" | "elderly";
}

export interface ContentLibraryResponse {
  videos: VideoContent[];
  heatmap_layer_url: string;
}

export interface AnnualReportResponse {
  year: number;
  total_heatmap_incidents_logged: number;
  total_b2b_threat_indicators_flagged: number;
  note: string;
}

// ── Fraud Type Scanner (21 real /scams/*/check detectors) ─────────────────────
// 18 of the 21 detectors return the shared ScamPatternResponse shape; the other
// 3 (job/loan/sextortion) were enhanced with an extra field each on the backend
// and get their own response type — see JobScamResponse/LoanScamResponse/
// SextortionResponse below.

export interface TranscriptRequest {
  transcript?: string | null;
  email_body?: string | null;
}

export interface ScamPatternResponse {
  risk_level: "low" | "medium" | "high";
  flags: string[];
  confidence_score: number;
}

export interface JobScamResponse {
  risk_level: "low" | "medium" | "high";
  flags: string[];
  confidence_score: number;
  mca_check_note: string;
}

export interface LoanScamResponse {
  risk_level: "low" | "medium" | "high";
  flags: string[];
  confidence_score: number;
  app_registry_status: "not_mentioned" | "registered" | "unregistered";
}

export interface SextortionResponse {
  risk_level: "low" | "high";
  flags: string[];
  escalation_path: "minor_protection" | "adult_standard";
  immediate_actions: string[];
  legal_escalation: string;
  note: string;
}

export type ScamCheckResponse =
  | ScamPatternResponse
  | JobScamResponse
  | LoanScamResponse
  | SextortionResponse;

// ── Report a Scam (community report + heatmap) ─────────────────────────────────

export interface ScamReportRequest {
  reporter_id: string;
  scam_type: string;
  location_lat: number;
  location_lng: number;
  description: string;
}

export interface ScamReportResponse {
  report_count: number;
  contributed_to_heatmap: boolean;
  message: string;
}

export interface HeatmapZone {
  lat: number;
  lng: number;
  scam_type: string;
  weight: number;
}

export interface HeatmapResponse {
  active_zones: HeatmapZone[];
}

// ── Family Protection ──────────────────────────────────────────────────────────

export interface PairDevicesRequest {
  protected_id: string;
  protector_id: string;
}

export interface PairDevicesResponse {
  protected_id: string;
  protector_id: string;
}

export interface PanicAlertRequest {
  protected_id: string;
  device_source: string;
}

export interface PanicTriggerResponse {
  broadcast_success: boolean;
  source_hardware: string;
  protector_notified_id: string | null;
  action_dispatched: "IMMEDIATE_SMS_AND_PUSH_DISPATCH" | "BROADCAST_TO_PUBLIC_EMERGENCY";
}

export interface TrainingScoreResponse {
  user_id: string;
  drills_completed_count: number;
  latest_score: number;
  passed: boolean;
  note: string;
}

export interface TrainingDrillResponse {
  drill_id: string;
  scenario_type: string;
  scenario_text: string;
  options: string[];
  note: string;
}

export interface TrainingAnswerRequest {
  user_id: string;
  drill_id: string;
  selected_answer: string;
}

export interface TrainingAnswerResponse {
  drill_id: string;
  correct: boolean;
  explanation: string;
  training_score: TrainingScoreResponse;
  note: string;
}

// ── Legal & Recovery ────────────────────────────────────────────────────────────

export interface EZeroFIRRequest {
  category: string;
}

export interface EZeroFIRResponse {
  fir_hash: string;
  timestamp_utc: string;
  statute: string;
  jurisdiction: string;
  threat_category: string;
  status: string;
}

export interface DisputeTrackRequest extends ComplaintRequest {
  user_id: string;
  bank_name: string;
  transaction_reference: string;
}

export interface DisputeTrackResponse {
  case_id: string;
  user_id: string;
  bank_name: string;
  transaction_reference: string;
  dispute_raised_at: string;
  rbi_deadline_at: string;
  status: "open" | "bank_responded" | "escalated" | "resolved";
  dispute_text: string;
  note: string;
}

export interface DisputeStatusResponse {
  case_id: string;
  status: "open" | "bank_responded" | "escalated" | "resolved";
  bank_response: string | null;
  rbi_deadline_at: string;
  is_overdue: boolean;
  note: string;
}

export interface DisputeEscalationResponse {
  case_id: string;
  status: "open" | "bank_responded" | "escalated" | "resolved";
  escalation_text: string;
  rbi_deadline_at: string;
  note: string;
}

export interface AssetHoldRequest {
  case_id: string;
  frozen_amount: number;
  bank_node: string;
}

export interface AssetTrackerResponse {
  case_id: string;
  frozen_amount: number;
  bank_node: string;
  status: "FROZEN" | "UNDER_INVESTIGATION" | "RELEASED" | "RECOVERED";
  hold_timestamp_utc: string;
  last_updated_utc: string;
}

// ── Privacy & Consent ───────────────────────────────────────────────────────────

export interface ConsentGrantRequest {
  user_id: string;
  purpose: string;
  retention_days?: number | null;
}

export interface ConsentRevokeRequest {
  user_id: string;
  purpose: string;
}

export interface ConsentResponse {
  user_id: string;
  purpose: string;
  granted_at: string;
  expires_at: string | null;
  revoked: boolean;
  active: boolean;
}

// ── Quick Safety Check ──────────────────────────────────────────────────────────

export interface BlocklistCheckResponse {
  threat_detected: boolean;
  action: "INTERCEPT_AND_LOG" | "ALLOW";
  hash: string;
}

// ── My Scam Case Timeline ────────────────────────────────────────────────────────

export interface CreateCaseRequest {
  user_id: string;
  title: string;
}

export interface AddEventRequest {
  event_type: "call" | "whatsapp" | "upi" | "document" | "other";
  description: string;
  event_timestamp: string;
  artifact_id?: string | null;
}

export interface CampaignEventResponse {
  event_type: "call" | "whatsapp" | "upi" | "document" | "other";
  description: string;
  event_timestamp: string;
  artifact_id: string | null;
}

export interface CaseFileResponse {
  case_id: string;
  user_id: string;
  title: string;
  status: "open" | "closed";
  created_at: string;
  events: CampaignEventResponse[];
}

export interface CaseListResponse {
  cases: CaseFileResponse[];
}
