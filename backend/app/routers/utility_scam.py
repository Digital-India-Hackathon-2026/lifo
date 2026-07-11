"""
/scams/utility — Fake electricity/gas bill (utility disconnection) scam detector.

UNSCOPED BONUS ITEM: not part of Track 1's assigned 30-item catalog scope
— the collaborator built this on their own initiative. Per the audit
(~/NewProjects/kavach-track1-audit-REPORT.md), verified working as tested,
same quality bar as the scoped items. Ported from
app/routers/utility_scam.py — real, tested detection logic, kept as-is
(3 patterns, but bands on >=2 like investment/exam/ussd — not the
exact-count-of-3 shape reward_scam.py/gov_scheme.py/ecommerce_scam.py use).
No dead/unreachable branch found (checked per Session 25's task — see
AGENTS.md).

Fixed on port: normalized risk_level to lowercase; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
Transcript preferred — disconnection warnings and "call this number"
redirects are SMS/call-style, matching courier_scam.py's precedent.
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/utility", tags=["Fraud Coverage"])

# Indicators: Electricity bill update penalty, call this specific number, and imminent power cuts
_POWER_CUT_RE = re.compile(r"(electricity will be disconnected|power cut tonight|electricity bill unpaid|disconnection warning)", re.IGNORECASE)
_FAKE_OFFICER_RE = re.compile(r"(call electricity officer|contact power department helpline|contact desk officer)", re.IGNORECASE)
_UPDATE_TRAP_RE = re.compile(r"(update your bill app|pay old balance immediately|avoid penalty charge)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_utility_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Disconnection-threat/fake-officer/update-trap phrase scan for fake utility bill scams."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _POWER_CUT_RE.search(text):
        flags.append("Threat of immediate utility service termination")
    if _FAKE_OFFICER_RE.search(text):
        flags.append("Redirecting to a non-official phone number for utility verification")
    if _UPDATE_TRAP_RE.search(text):
        flags.append("Urgent demand for balance updates or downloading external apps")

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.65
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
