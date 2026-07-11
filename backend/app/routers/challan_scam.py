"""
/scams/challan — Fake traffic-fine (e-challan) scam detector.

UNSCOPED BONUS ITEM: not part of Track 1's assigned 30-item catalog scope
(items 1–30) — the collaborator built this on their own initiative. Per
the audit (~/NewProjects/kavach-track1-audit-REPORT.md), verified working
as tested, same quality bar as the scoped items. Ported from
app/routers/challan_scam.py — real, tested detection logic, kept as-is.
No dead/unreachable branch found (checked per Session 25's task — see
AGENTS.md).

Fixed on port: normalized risk_level to lowercase; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
Transcript preferred — e-challan scams arrive as SMS/link-style messages.
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/challan", tags=["Fraud Coverage"])

# Indicators: Immediate traffic fine demands and suspicious settlement links
_CHALLAN_URGENCY_RE = re.compile(r"(traffic violation penalty|pay fine immediately|vehicle impound warning)", re.IGNORECASE)
_FAKE_LINK_RE = re.compile(r"(click here to pay challan|echallan-update|settle traffic fine)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_challan_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Urgency/fake-link phrase scan for fake traffic-fine (e-challan) scams."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _CHALLAN_URGENCY_RE.search(text):
        flags.append("Urgent threat regarding traffic violations or vehicle impounding")
    if _FAKE_LINK_RE.search(text):
        flags.append("Suspicious link provided to settle traffic fines")

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.65
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
