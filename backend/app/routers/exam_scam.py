"""
/scams/exam — Exam / scholarship / recruitment-notice fraud detector (catalog item 12).

Guaranteed-pass, fee-trap, and urgency phrase patterns and flag-count risk
banding ported from the Track 1 collaborator repo's app/routers/exam_scam.py
— real, tested detection logic, kept as-is. No dead/unreachable branch
found in this router (checked per Session 24's task — see AGENTS.md).

Fixed on port: normalized risk_level to lowercase; falls back to
transcript when email_body is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
email_body preferred over transcript — exam/scholarship/admit-card
notices are typically email or portal notifications, not spoken calls.
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/exam", tags=["Fraud Coverage"])

# Real-world indicators: fake laptop distribution schemes, guaranteed admissions, and admit card fees
_GUARANTEED_PASS_RE = re.compile(r"(guaranteed pass|leak paper|direct admission|management quota pay)", re.IGNORECASE)
_FEE_TRAP_RE = re.compile(r"(scholarship processing fee|laptop distribution fee|pay for admit card)", re.IGNORECASE)
_URGENCY_RE = re.compile(r"(deadline tonight|cancellation of seat|last chance for scholarship)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_exam_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Guaranteed-pass/fee-trap/urgency phrase scan for exam & scholarship fraud."""
    text = req.email_body or req.transcript or ""
    flags: list[str] = []

    if _GUARANTEED_PASS_RE.search(text):
        flags.append("Illegal offer of guaranteed passing or leaked papers")
    if _FEE_TRAP_RE.search(text):
        flags.append("Advance fee requested for free scholarship or admit card")
    if _URGENCY_RE.search(text):
        flags.append("High-pressure urgency regarding academic seat or funding")

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.70
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
