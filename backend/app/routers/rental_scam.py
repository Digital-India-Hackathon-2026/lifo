"""
/scams/rental — Fake rental-listing scam detector.

UNSCOPED BONUS ITEM: not part of Track 1's assigned 30-item catalog scope
— the collaborator built this on their own initiative. Per the audit
(~/NewProjects/kavach-track1-audit-REPORT.md), verified working as tested,
same quality bar as the scoped items. Ported from
app/routers/rental_scam.py — real, tested detection logic, kept as-is,
including its 0.98 high-risk confidence (not the usual 0.95 — preserved
exactly, not rounded). No dead/unreachable branch found (checked per
Session 25's task — see AGENTS.md).

Fixed on port: normalized risk_level to lowercase; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
Transcript preferred — rental negotiations over "token amount"/"gate
pass" fees are chat/message-style, not formal listing emails.
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/rental", tags=["Fraud Coverage"])

# Indicators: Army officer impersonation for rentals, advance token money without seeing the property
_ARMY_IMPERSONATION_RE = re.compile(r"(army officer transfer|cisf posting|cantonment area rule)", re.IGNORECASE)
_TOKEN_ADVANCE_RE = re.compile(r"(token amount to lock|pay advance before visit|gate pass fee)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_rental_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Army-impersonation/advance-token phrase scan for fake rental-listing scams."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _ARMY_IMPERSONATION_RE.search(text):
        flags.append("High-risk military impersonation pattern commonly used in rental fraud")
    if _TOKEN_ADVANCE_RE.search(text):
        flags.append("Request for token advance or gate pass fee before a physical visit")

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.98
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.65
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
