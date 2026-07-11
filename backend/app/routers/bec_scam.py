"""
/scams/bec — Business Email Compromise / vendor-fraud detector for SMEs (catalog item 6).

Bank-detail-change, executive-impersonation-isolation, and acute-urgency
phrase patterns and flag-count risk banding ported from the Track 1
collaborator repo's app/routers/bec_scam.py — real, tested detection
logic, kept as-is.

Fixed on port: dropped an unreachable second `elif len(flags) == 1` branch
at the end (dead code — the first `elif len(flags) == 1` above it already
claims that condition, so it could never be reached); normalized
risk_level to lowercase to match this codebase's
Literal["low","medium","high"] convention. email_body is still preferred
over transcript (BEC is inherently email-based), but TranscriptRequest
(shared from romance_scam.py) now requires at least one of the two to be
non-empty instead of silently defaulting both to "".
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/bec", tags=["Fraud Coverage"])

# Indicators for BEC targeting SMEs
_BANK_CHANGE_RE = re.compile(r"(updated banking details|new wire instructions|alternative bank account|routing update)", re.IGNORECASE)
_EXEC_IMPERSONATION_RE = re.compile(r"(confidential project|out of the office|discreet payment|do not mention to staff)", re.IGNORECASE)
_ACUTE_URGENCY_RE = re.compile(r"(process immediately|wire transfer today|before end of day|overdue invoice settlement)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_bec_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Bank-change/exec-impersonation/urgency phrase scan for BEC targeting SMEs."""
    text = req.email_body or req.transcript or ""
    flags: list[str] = []

    if _BANK_CHANGE_RE.search(text):
        flags.append("Sudden request to change payee bank details")
    if _EXEC_IMPERSONATION_RE.search(text):
        flags.append("Executive isolation or confidentiality pressure detected")
    if _ACUTE_URGENCY_RE.search(text):
        flags.append("High-pressure temporal urgency for wire transfers")

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.70
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
