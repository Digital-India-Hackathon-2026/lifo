"""
/scams/recruitment — Fake recruitment portal detector (catalog item 15).

Premium-fee, portal-spoof, and fake-incentive phrase patterns and
flag-count risk banding ported from the Track 1 collaborator repo's
app/routers/recruitment_scam.py — real, tested detection logic, kept
as-is. No dead/unreachable branch found in this router (checked per
Session 24's task — see AGENTS.md).

Fixed on port: normalized risk_level to lowercase; falls back to
transcript when email_body is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
email_body preferred over transcript — recruitment portal messages
("Naukri Premium", "official HR portal update") are notification/email
style, matching exam_scam.py's precedent.
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/recruitment", tags=["Fraud Coverage"])

# Indicators: Advance fees for jobs, fake portal updates, and suspicious joining incentives
_PREMIUM_FEE_RE = re.compile(r"(pay for interview|laptop security deposit|premium processing fee|fast track placement)", re.IGNORECASE)
_PORTAL_SPOOF_RE = re.compile(r"(naukri premium|linkedin fast track|official hr portal update)", re.IGNORECASE)
_FAKE_INCENTIVE_RE = re.compile(r"(guaranteed joining reward|referral reward fee)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_recruitment_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Premium-fee/portal-spoof/fake-incentive phrase scan for fake recruitment portals."""
    text = req.email_body or req.transcript or ""
    flags: list[str] = []

    if _PREMIUM_FEE_RE.search(text):
        flags.append("Advance fee requested for interview or equipment")
    if _PORTAL_SPOOF_RE.search(text):
        flags.append("Suspicious imitation of official recruitment portals")
    if _FAKE_INCENTIVE_RE.search(text):
        flags.append("Suspicious upfront reward requiring payment")

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.65
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
