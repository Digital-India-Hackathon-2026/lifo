"""
/scams/customercare — Fake customer-care / support-line scam detector.

UNSCOPED BONUS ITEM: not part of Track 1's assigned 30-item catalog scope
— the collaborator built this on their own initiative. Per the audit
(~/NewProjects/kavach-track1-audit-REPORT.md), verified working as tested,
same quality bar as the scoped items. Ported from
app/routers/customercare_scam.py — real, tested detection logic, kept
as-is. No dead/unreachable branch found (checked per Session 25's task —
see AGENTS.md).

Fixed on port: normalized risk_level to lowercase; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
Transcript preferred — a fake support call is inherently a live-call
transcript.
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/customercare", tags=["Fraud Coverage"])

# Indicators: Fake customer care asking for fees for free services or requesting screen sharing
_TOLL_FREE_FEE_RE = re.compile(r"(pay registration fee|customer care processing charge|service activation fee)", re.IGNORECASE)
_REMOTE_ACCESS_RE = re.compile(r"(download quicksupport|install remote app|share screen for support)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_customercare_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Fee-demand/remote-access phrase scan for fake customer-care scams."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _TOLL_FREE_FEE_RE.search(text):
        flags.append("Customer care requesting an unusual fee for standard support")
    if _REMOTE_ACCESS_RE.search(text):
        flags.append("Support agent requesting remote access or screen-sharing software")

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.70
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
