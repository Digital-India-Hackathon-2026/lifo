"""
/scams/lottery — Lottery / prize / customs-gift scam detector (catalog item 4).

Lottery-win, advance-fee, and KBC-impersonation phrase patterns and
flag-count risk banding ported from the Track 1 collaborator repo's
app/routers/lottery_scam.py — real, tested detection logic, kept as-is
(the reference never used the envelope wrapper here, unlike investment_scam.py).

Fixed on port: normalized risk_level to lowercase to match this codebase's
Literal["low","medium","high"] convention; falls back to email_body when
transcript is empty (TranscriptRequest, shared from romance_scam.py, now
requires at least one of the two to be non-empty).
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/lottery", tags=["Fraud Coverage"])

# Indicators: Lucky draw wins, tax/processing fee demands, KBC impersonation
_LOTTERY_WIN_RE = re.compile(r"(you won the lottery|lucky draw winner|congratulations you won|prize money of)", re.IGNORECASE)
_FEE_DEMAND_RE = re.compile(r"(pay income tax fee|pay the income tax fee|processing charge for prize|transfer fee to claim)", re.IGNORECASE)
_KBC_IMPERSONATION_RE = re.compile(r"(kbc lucky draw|kon banega crorepati|amitabh bachchan lucky draw)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_lottery_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Lottery-win/fee-demand/KBC-impersonation phrase scan."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _LOTTERY_WIN_RE.search(text):
        flags.append("Suspicious notification of a lottery win")
    if _FEE_DEMAND_RE.search(text):
        flags.append("Request for advance fee to claim prize money")
    if _KBC_IMPERSONATION_RE.search(text):
        flags.append("High-risk impersonation of KBC/TV show lottery")

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.97
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.60
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
