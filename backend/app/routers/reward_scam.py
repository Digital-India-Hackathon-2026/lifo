"""
/scams/reward — Fake loyalty/cashback reward scam detector.

UNSCOPED BONUS ITEM: not part of Track 1's assigned 30-item catalog scope
— the collaborator built this on their own initiative. Per the audit
(~/NewProjects/kavach-track1-audit-REPORT.md), verified working as tested,
same quality bar as the scoped items. Ported from
app/routers/reward_scam.py — real, tested detection logic, kept as-is,
including its exact-count-of-3 banding (same structure as courier_scam.py/
gov_scheme.py/ecommerce_scam.py). No dead/unreachable branch found
(checked per Session 25's task — see AGENTS.md).

Fixed on port: dropped the reference's envelope wrapper (this router used
EnvelopeResponse[ScamPatternResponse] — the 3rd confirmed instance found
across this repo, after investment_scam.py in batch 1; not all files have
been individually checked for it, so more may exist in the untouched
remainder of the repo). Normalized risk_level to lowercase; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
Transcript preferred — reward/cashback notifications read as SMS/app
notification style, matching gov_scheme.py's/ecommerce_scam.py's precedent.
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/reward", tags=["Fraud Coverage"])

_REWARD_CLAIM_RE = re.compile(r"(claim your reward|selected for a reward|won a reward|exclusive reward)", re.IGNORECASE)
_CUSTOMS_TAX_RE = re.compile(r"(customs clearance for your reward|pay tax on your reward|reward processing fee|reward release fee)", re.IGNORECASE)
_URGENCY_RE = re.compile(r"(reward expires|claim immediately|before reward is cancelled)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_reward_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Reward-claim/fee-demand/urgency phrase scan for fake loyalty/cashback scams."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _REWARD_CLAIM_RE.search(text):
        flags.append("Unsolicited reward notification detected")
    if _CUSTOMS_TAX_RE.search(text):
        flags.append("Advance fee requested to clear/release reward")
    if _URGENCY_RE.search(text):
        flags.append("Artificial urgency to claim reward")

    if len(flags) == 3:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 2:
        risk_level, confidence = "medium", 0.70
    elif len(flags) == 1:
        risk_level, confidence = "low", 0.40
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
