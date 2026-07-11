"""
/scams/ussd — USSD call-forwarding trap detector (catalog item 14).

Malicious-code, social-engineering, and OTP-interception phrase patterns
and flag-count risk banding ported from the Track 1 collaborator repo's
app/routers/ussd_scam.py — real, tested detection logic, kept as-is
(including the literal `*401*`/`**67*`/`*21*` code regex). No
dead/unreachable branch found in this router (checked per Session 24's
task — see AGENTS.md).

Fixed on port: normalized risk_level to lowercase; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
Transcript preferred — this is social engineering during a live call.
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/ussd", tags=["Fraud Coverage"])

# Indicators: Call forwarding codes and social engineering attempts
_USSD_CODE_RE = re.compile(r"(\*401\*|\*\*67\*|\*21\*)", re.IGNORECASE)
_SOCIAL_ENGINEERING_RE = re.compile(r"(dial this number|network check|upgrade your sim|jio network update)", re.IGNORECASE)
_OTP_STEAL_RE = re.compile(r"(receive a code|do not disconnect|forwarding activated)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_ussd_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """USSD-code/social-engineering/OTP-interception phrase scan."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _USSD_CODE_RE.search(text):
        flags.append("Malicious USSD call-forwarding code detected")
    if _SOCIAL_ENGINEERING_RE.search(text):
        flags.append("Social engineering attempt to force dialpad entry")
    if _OTP_STEAL_RE.search(text):
        flags.append("Indicators of OTP interception or silent forwarding")

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.65
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
