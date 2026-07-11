"""
/scams/ecommerce — Fake e-commerce / delivery / refund scam detector (catalog item 13).

Refund-trap, delivery-fee, and reward-trap phrase patterns and flag-count
risk banding ported from the Track 1 collaborator repo's
app/routers/ecommerce_scam.py — real, tested detection logic, kept as-is,
including its exact-count-of-3 banding (same structure as courier_scam.py
from batch 1 and gov_scheme.py from this batch). No dead/unreachable
branch found in this router (checked per Session 24's task — see AGENTS.md).

Fixed on port: normalized risk_level to lowercase; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
Transcript preferred — these are typically SMS/app-notification style
messages ("your package is held"), matching courier_scam.py's precedent.
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/ecommerce", tags=["Fraud Coverage"])

# Indicators: fake refunds (scan to receive), delivery reschedule fees, and loyalty reward traps
_REFUND_TRAP_RE = re.compile(r"(accidental double charge|click to process refund|refund failure|scan qr to receive refund)", re.IGNORECASE)
_DELIVERY_FEE_RE = re.compile(r"(reschedule delivery fee|address incomplete pay|customs held package)", re.IGNORECASE)
_REWARD_TRAP_RE = re.compile(r"(claim your reward|loyalty reward fee)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_ecommerce_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Refund-trap/delivery-fee/reward-trap phrase scan for fake e-commerce/delivery scams."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _REFUND_TRAP_RE.search(text):
        flags.append("Suspicious refund process (QR code or external link)")
    if _DELIVERY_FEE_RE.search(text):
        flags.append("Request for delivery reschedule fee or address update payment")
    if _REWARD_TRAP_RE.search(text):
        flags.append("Unexpected e-commerce reward requiring payment")

    if len(flags) == 3:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 2:
        risk_level, confidence = "medium", 0.70
    elif len(flags) == 1:
        risk_level, confidence = "low", 0.40
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
