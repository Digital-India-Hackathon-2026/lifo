"""
/scams/gov-scheme — Government-scheme/subsidy scam detector (catalog item 10).

Fake-benefit, advance-processing-fee, and urgent-KYC phrase patterns and
flag-count risk banding ported from the Track 1 collaborator repo's
app/routers/gov_scheme.py — real, tested detection logic, kept as-is,
including its exact-count-of-3 banding (same structure as courier_scam.py
from batch 1 — a scheme scam needs fake-benefit + fee-demand + urgency
together to read as "high", not just any 2 of 3). No dead/unreachable
branch found in this router (checked per Session 24's task — see AGENTS.md).

Fixed on port: normalized risk_level to lowercase; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
Transcript preferred — these scams are typically SMS/WhatsApp broadcast
messages, not formal email.
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/gov-scheme", tags=["Fraud Coverage"])

# Real-world Indian government scheme scam indicators (fake subsidies, PM-Kisan registry, advance processing fees)
_FAKE_BENEFIT_RE = re.compile(r"(pm-kisan subsidy|free subsidy registry|free laptop scheme|free solar panel|gov scheme payout)", re.IGNORECASE)
_PROCESSING_FEE_RE = re.compile(r"(registration charge|registration fee|processing fee to release|scheme activation tax)", re.IGNORECASE)
_URGENT_KYC_RE = re.compile(r"(update kyc today|scheme cancellation|immediate verification|immediately to verify)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_gov_scheme_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Fake-benefit/fee-demand/urgent-KYC phrase scan for government scheme scams."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _FAKE_BENEFIT_RE.search(text):
        flags.append("Suspicious claims of fake government scheme or subsidy")
    if _PROCESSING_FEE_RE.search(text):
        flags.append("Advance fee requested for government subsidy activation")
    if _URGENT_KYC_RE.search(text):
        flags.append("Urgency/cancellation threat to force compliance")

    if len(flags) == 3:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 2:
        risk_level, confidence = "medium", 0.70
    elif len(flags) == 1:
        risk_level, confidence = "low", 0.40
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
