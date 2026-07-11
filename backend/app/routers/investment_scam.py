"""
/scams/investment — Investment / trading scam shield (catalog item 2).

Ponzi-language, fake-SEBI-registration, and urgency phrase patterns and
flag-count risk banding ported from the Track 1 collaborator repo's
app/routers/investment_scam.py — real, tested detection logic, kept as-is.

Fixed on port: dropped the reference's envelope wrapper (uses
response_model= directly, matching every router in this codebase, not
their {status,data,error} shape); dropped an unreachable second
`elif len(flags) == 1` branch at the end (dead code — the first
`elif len(flags) == 1` above it already claims that condition, so the
second could never execute); normalized risk_level to lowercase to match
this codebase's Literal["low","medium","high"] convention; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/investment", tags=["Fraud Coverage"])

# Real-world Indian investment scam indicators (Ponzi schemes, fake SEBI backing, forced urgency)
_PONZI_LANG_RE = re.compile(r"(guaranteed returns|double your money|risk-free profit|100% profit|high yield)", re.IGNORECASE)
_FAKE_REGULATORY_RE = re.compile(r"(sebi approved|registered with sebi|government backed fund|sebi certificate)", re.IGNORECASE)
_URGENCY_RE = re.compile(r"(limited slots|close trading group|insider info|join the group now|transfer today)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_investment_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Ponzi/fake-regulatory/urgency phrase scan for investment & trading scams."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _PONZI_LANG_RE.search(text):
        flags.append("Ponzi scheme or unrealistic return language detected")
    if _FAKE_REGULATORY_RE.search(text):
        flags.append("Suspicious SEBI or regulatory compliance claim")
    if _URGENCY_RE.search(text):
        flags.append("High-pressure urgency to join trading group/invest")

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.70
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
