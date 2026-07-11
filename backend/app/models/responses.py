from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel

DISCLAIMER = (
    "This tool reduces risk but cannot guarantee 100% accuracy. "
    "Always verify through a second, independent channel before sending money."
)
CONFIDENCE_NOTE = (
    "Raw softmax output for the predicted class (0–1). "
    "Not a calibrated probability — treat as a signal, not a percentage chance."
)

# ── Evidence trail (item 84): normalized parallel view over each endpoint's ──
# existing flags/score_breakdown data. Optional and additive — never replaces
# the response's own fields, and is only populated where source data exists.

class EvidenceItem(BaseModel):
    signal: str
    weight: float
    contributed_to_verdict: bool


class EvidenceTrail(BaseModel):
    items: list[EvidenceItem]


def flat_evidence_trail(signals: list[str]) -> EvidenceTrail:
    """Evidence trail for count-based scam routers where every returned flag has equal weight."""
    return EvidenceTrail(items=[EvidenceItem(signal=s, weight=1.0, contributed_to_verdict=True) for s in signals])


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    error: str
    status_code: int
    detail: Any = None


class SuspiciousFrame(BaseModel):
    frame_index: int
    fake_score: float


class ClassifyImageResponse(BaseModel):
    verdict: Literal["real", "ai_generated"]
    confidence_score: float
    note: str
    model: str
    disclaimer: str


class ClassifyVideoResponse(BaseModel):
    verdict: Literal["real", "ai_generated"]
    confidence_score: float
    note: str
    frames_sampled: int
    most_suspicious_frame: SuspiciousFrame
    model: str
    disclaimer: str


class ClassifyAudioResponse(BaseModel):
    verdict: Literal["genuine", "spoof"]
    confidence_score: float
    note: str
    # Start time (seconds) of the most suspicious audio window.
    # None only when audio is shorter than one analysis window (< 3s).
    anomaly_timestamp: Optional[float] = None
    model: str
    disclaimer: str


class ScamIndicator(BaseModel):
    type: str
    matched_text: str


class PIIMatch(BaseModel):
    type: Literal["aadhaar", "pan"]
    masked_value: str


class ClassifyDocumentResponse(BaseModel):
    ocr_text: str
    pii_detected: list[PIIMatch]
    scam_indicators: list[ScamIndicator]
    risk_level: Literal["low", "medium", "high"]
    note: str
    disclaimer: str
    evidence_trail: Optional[EvidenceTrail] = None


# ── Phishing check model ─────────────────────────────────────────────────────

class CheckPhishingResponse(BaseModel):
    domain: str
    in_blocklist: bool
    blocklist_match: Optional[str] = None    # matched blocklist entry domain; null when not in list
    similarity_score: float            # 0.0–1.0 vs curated Indian gov/bank domain list
    matched_against: Optional[str] = None    # curated domain with highest similarity; null when < threshold
    risk_level: Literal["low", "medium", "high"]
    note: str
    disclaimer: str


# ── Vault ─────────────────────────────────────────────────────────────────────

class VaultSetResponse(BaseModel):
    message: str
    note: str


class VaultVerifyResponse(BaseModel):
    matches: bool
    note: str
    disclaimer: str


# ── Complaint assistant ────────────────────────────────────────────────────────

class ComplaintResponse(BaseModel):
    ncrp_complaint_text: Optional[str] = None
    bank_dispute_text: Optional[str] = None
    next_steps: list[str]
    disclaimer: str


# ── Digital Arrest pattern recognizer ────────────────────────────────────────

class DigitalArrestResponse(BaseModel):
    matched_patterns: list[str]
    payment_indicators_found: list[str]
    severity: Literal["low", "medium", "high"]
    hard_factual_anchor: str
    note: str
    disclaimer: str


# ── Social profile check model ────────────────────────────────────────────────

class ScoreEntry(BaseModel):
    flag: str
    points: int
    reason: str


class CheckSocialProfileResponse(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    total_score: int
    red_flags: list[str]
    score_breakdown: list[ScoreEntry]
    note: str
    disclaimer: str
    evidence_trail: Optional[EvidenceTrail] = None


# ── Honeypot models ───────────────────────────────────────────────────────────

class StartSessionResponse(BaseModel):
    session_id: str


class TurnSignals(BaseModel):
    upi_ids: list[str]
    phone_numbers: list[str]
    bank_accounts: list[str]
    scripted_phrases: list[str]


class CumulativeIntel(BaseModel):
    upi_ids: list[str]
    phone_numbers: list[str]
    bank_accounts: list[str]
    scripted_phrases: list[str]


class ConverseResponse(BaseModel):
    session_id: str
    turn: int
    transcript: Optional[str] = None            # null when STT fails
    persona_reply_text: Optional[str] = None    # null when Persona fails or STT fails
    persona_reply_audio: Optional[str] = None   # base64 MP3; null when TTS fails/unavailable
    signals_this_turn: TurnSignals
    cumulative_intel: CumulativeIntel
    stage_log: list[str]                 # 4 entries: STT / Persona / TTS / Extraction


class TurnHistoryItem(BaseModel):
    turn: int
    transcript: Optional[str] = None
    persona_reply: Optional[str] = None


class ReportResponse(BaseModel):
    session_id: str
    turn_count: int
    cumulative_intel: CumulativeIntel
    turn_history: list[TurnHistoryItem]


# ── Network Intelligence / Campaign Graph (Track 3, item 31) ─────────────────

class ThreatTaxonomy(str, Enum):
    PHISHING_URL = "PHISHING_URL"
    MULE_ACCOUNT = "MULE_ACCOUNT"
    VOICE_SPOOF = "VOICE_SPOOF"
    MALICIOUS_APK = "MALICIOUS_APK"


class LinkResponse(BaseModel):
    edge_status: Literal["CREATED", "EXISTS"]
    source_node_id: int
    target_node_id: int
    taxonomy: ThreatTaxonomy


# ── Federated Privacy-Preserving Blocklist (Track 3, item 32) ────────────────

class IngestResponse(BaseModel):
    status: Literal["SECURED", "REJECTED"]
    hash_signature: Optional[str] = None
    taxonomy: Optional[ThreatTaxonomy] = None
    reason: Optional[str] = None


class ScanResponse(BaseModel):
    threat_detected: bool
    action: Literal["INTERCEPT_AND_LOG", "ALLOW"]
    hash: str


# ── DPDP Consent + Retention (Track 3, item 82) ───────────────────────────────

class ConsentResponse(BaseModel):
    user_id: str
    purpose: str
    granted_at: datetime
    expires_at: Optional[datetime] = None
    revoked: bool
    active: bool


class PurgeResponse(BaseModel):
    purged_count: int


# ── Asset-Recovery Status Tracker (Track 3, item 68) ──────────────────────────

class AssetStatus(str, Enum):
    FROZEN = "FROZEN"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    RELEASED = "RELEASED"
    RECOVERED = "RECOVERED"


class AssetTrackerResponse(BaseModel):
    case_id: str
    frozen_amount: float
    bank_node: str
    status: AssetStatus
    hold_timestamp_utc: datetime
    last_updated_utc: datetime


# ── Legal Templates: e-Zero FIR (Track 3, item 65) ────────────────────────────

class EZeroFIRResponse(BaseModel):
    fir_hash: str
    timestamp_utc: datetime
    statute: str
    jurisdiction: str
    threat_category: str
    status: str


# ── Bank Dispute + Ombudsman Auto-Escalation (item 64) ────────────────────────

class DisputeTrackResponse(BaseModel):
    case_id: str
    user_id: str
    bank_name: str
    transaction_reference: str
    dispute_raised_at: datetime
    rbi_deadline_at: datetime
    status: Literal["open", "bank_responded", "escalated", "resolved"]
    dispute_text: str
    note: str


class DisputeStatusResponse(BaseModel):
    case_id: str
    status: Literal["open", "bank_responded", "escalated", "resolved"]
    bank_response: Optional[str] = None
    rbi_deadline_at: datetime
    is_overdue: bool
    note: str


class DisputeEscalationResponse(BaseModel):
    case_id: str
    status: Literal["open", "bank_responded", "escalated", "resolved"]
    escalation_text: str
    rbi_deadline_at: datetime
    note: str


# ── Moonshot PoC: Distributed Honeypot Grid (Track 3, item 87) ───────────────

class MoonshotPoCResponse(BaseModel):
    active_nodes: int
    intercepted_payloads: int
    note: str


# ── Fraud Coverage batch 1 (Track 1, items 1/2/4/5/6) ─────────────────────────

class ScamPatternResponse(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    flags: list[str]
    confidence_score: float
    evidence_trail: Optional[EvidenceTrail] = None


# ── Fraud Coverage: enhanced items 3/7/9 (Track 1) ────────────────────────────
# These 3 items are NOT straight ports — each adds a real capability the
# reference lacked, with its own extra field(s) beyond ScamPatternResponse.

class JobScamResponse(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    flags: list[str]
    confidence_score: float
    mca_check_note: str


class LoanScamResponse(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    flags: list[str]
    confidence_score: float
    app_registry_status: Literal["not_mentioned", "registered", "unregistered"]


class SextortionResponse(BaseModel):
    risk_level: Literal["low", "high"]
    flags: list[str]
    escalation_path: Literal["minor_protection", "adult_standard"]
    immediate_actions: list[str]
    legal_escalation: str
    note: str


# ── Track 2: Community/Heatmap, Panic Alert, Surfaces, Business, Education ────

class ScamReportResponse(BaseModel):
    report_count: int
    contributed_to_heatmap: bool
    message: str


class HeatmapZone(BaseModel):
    lat: float
    lng: float
    scam_type: str
    weight: int


class HeatmapResponse(BaseModel):
    active_zones: list[HeatmapZone]


class SegmentEvaluationResponse(BaseModel):
    segment_type: Literal["NRI", "SME", "KIDS", "MIGRANT", "PENSIONER", "DOMESTIC"]
    risk_level: Literal["low", "medium", "high"]
    flags: list[str]
    confidence_score: float
    note: str


class PanicTriggerResponse(BaseModel):
    broadcast_success: bool
    source_hardware: str
    protector_notified_id: Optional[str] = None
    action_dispatched: Literal["IMMEDIATE_SMS_AND_PUSH_DISPATCH", "BROADCAST_TO_PUBLIC_EMERGENCY"]


class PairDevicesResponse(BaseModel):
    protected_id: str
    protector_id: str


class CallStateResponse(BaseModel):
    session_id: str
    ui_action_required: Literal["FORCE_DEESCALATION_OVERLAY", "NONE"]


class RemoteHangupResponse(BaseModel):
    session_id: str
    current_status: str


class QRScanResponse(BaseModel):
    is_dangerous_collect: bool
    recommendation: Literal["DO NOT SCAN - FORCED DEBIT", "SAFE"]


class ChatWebhookResponse(BaseModel):
    platform: str
    risk_detected: bool
    matched_patterns: list[str]
    auto_reply_action: str


class ExtensionCheckResponse(BaseModel):
    scanned_url: str
    action: Literal["BLOCK_NAVIGATION", "ALLOW"]


class IVRResponse(BaseModel):
    caller: str
    routed_action: Literal["ROUTING_TO_HUMAN_OPERATOR", "TRIGGER_FAMILY_PANIC_ALERT"]


class TVBroadcastResponse(BaseModel):
    household: str
    broadcast_status: str
    note: str


class FeatureGateResponse(BaseModel):
    feature: str
    access_granted: bool
    requires_upgrade: bool


class B2BProfileCheckResponse(BaseModel):
    risk_level: Literal["low", "high"]
    flags_detected: list[str]
    platform: str


class ThreatIntelResponse(BaseModel):
    indicators_count: int
    platforms_represented: list[str]


class VideoContent(BaseModel):
    id: str
    lang: str
    title: str
    url: str
    tags: list[str]
    target_audience: Literal["general", "elderly"] = "general"


class ContentLibraryResponse(BaseModel):
    videos: list[VideoContent]
    heatmap_layer_url: str


class TrainingScoreResponse(BaseModel):
    user_id: str
    drills_completed_count: int
    latest_score: int
    passed: bool
    note: str


class TrainingDrillResponse(BaseModel):
    drill_id: str
    scenario_type: str
    scenario_text: str
    options: list[str]
    note: str


class TrainingAnswerResponse(BaseModel):
    drill_id: str
    correct: bool
    explanation: str
    training_score: TrainingScoreResponse
    note: str


class SmartSpeakerResponse(BaseModel):
    device_id: str
    action_taken: Literal["PANIC_TRIGGERED", "RISK_CHECK"]
    spoken_response: str
    risk_level: Optional[Literal["low", "medium", "high"]] = None


class SDKKeyIssueResponse(BaseModel):
    api_key: str
    tier: Literal["free", "premium"]
    note: str


class SDKKeyValidateResponse(BaseModel):
    valid: bool
    tier: Literal["free", "premium"]


class AnnualReportResponse(BaseModel):
    year: int
    total_heatmap_incidents_logged: int
    total_b2b_threat_indicators_flagged: int
    note: str


# ── Track 1: Scam Campaign Timeline (item 30) ─────────────────────────────────

class CampaignEventResponse(BaseModel):
    event_type: Literal["call", "whatsapp", "upi", "document", "other"]
    description: str
    event_timestamp: datetime
    artifact_id: Optional[str] = None


class CaseFileResponse(BaseModel):
    case_id: str
    user_id: str
    title: str
    status: Literal["open", "closed"]
    created_at: datetime
    events: list[CampaignEventResponse]


class CaseListResponse(BaseModel):
    cases: list[CaseFileResponse]
