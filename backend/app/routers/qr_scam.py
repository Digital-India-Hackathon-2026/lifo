"""
/scams/qr — QR-code / "quishing" scanner (catalog item 11).

"Scan to receive" and "PIN to receive" phrase patterns ported from the
Track 1 collaborator repo's app/routers/qr_scam.py — real, tested
detection logic, kept as-is, INCLUDING its deliberately unusual banding:
only 2 patterns are defined, and matching either 1 or 2 of them bands as
"high" — there is no "medium" tier at all for this detector. That's not a
bug (verified — no dead/unreachable branch): both "scan to receive money"
and "enter UPI PIN to receive a refund" are technically false statements
about how UPI works (scanning/PIN-entry can only ever authorize a payment
OUT, never receive one), so the reference treats either one alone as an
immediate high-confidence red flag rather than a partial signal. Ported
faithfully, not normalized to match the other detectors' 3-tier shape.

Fixed on port: normalized risk_level to lowercase; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
Transcript preferred — this is a live chat/message request during a
transaction, not a formal email.
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/qr", tags=["Fraud Coverage"])

# Indicators: UPI "scan to receive" traps and deceptive merchant payments
_SCAN_TO_RECEIVE_RE = re.compile(r"(scan to receive|scan to get money|scan for cashback|receive reward scan)", re.IGNORECASE)
_PIN_TO_RECEIVE_RE = re.compile(r"(enter pin to receive|upi pin for refund|pin to claim)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_qr_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """'Scan/PIN to receive' technical-lie phrase scan — either signal alone is high risk."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _SCAN_TO_RECEIVE_RE.search(text):
        flags.append("Fraudulent claim: scanning a QR code cannot receive money")
    if _PIN_TO_RECEIVE_RE.search(text):
        flags.append("Fraudulent claim: entering UPI PIN is only for sending money, not receiving")

    if len(flags) == 2:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 1:
        risk_level, confidence = "high", 0.90  # any presence of this specific technical lie is immediately high risk
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
