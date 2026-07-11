"""
/scams/kyc — Fake bank KYC-update scam detector.

UNSCOPED BONUS ITEM: not part of Track 1's assigned 30-item catalog scope
— the collaborator built this on their own initiative. Per the audit
(~/NewProjects/kavach-track1-audit-REPORT.md), verified working as tested,
same quality bar as the scoped items. Ported from app/routers/kyc_scam.py
— real, tested detection logic, kept as-is, including its 0.96 high-risk
confidence (not the usual 0.95 — preserved exactly, not rounded). No
dead/unreachable branch found (checked per Session 25's task — see
AGENTS.md).

Fixed on port: normalized risk_level to lowercase; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
Transcript preferred — "account suspended"/"update via SMS link" reads as
an SMS-style message.
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/kyc", tags=["Fraud Coverage"])

# Indicators: Bank account suspension threats and unverified update links
_ACCOUNT_BLOCK_RE = re.compile(r"(pan card blocked|account suspended|kyc pending warning)", re.IGNORECASE)
_UPDATE_LINK_RE = re.compile(r"(click link to update pan|verify kyc immediately|update via sms link)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_kyc_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Account-suspension-threat/update-link phrase scan for fake bank KYC scams."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _ACCOUNT_BLOCK_RE.search(text):
        flags.append("Threat of account suspension due to pending KYC or PAN update")
    if _UPDATE_LINK_RE.search(text):
        flags.append("Suspicious request to update sensitive banking details via unverified link")

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.96
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.70
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
