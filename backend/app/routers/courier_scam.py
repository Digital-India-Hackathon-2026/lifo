"""
/scams/courier — Courier / parcel / customs scam detector (catalog item 5).

Courier-brand-impersonation, contraband-claim, and police-transfer-threat
phrase patterns and flag-count risk banding ported from the Track 1
collaborator repo's app/routers/courier_scam.py — real, tested detection
logic, kept as-is, including its distinct exact-count banding: this
detector requires all 3 signals for "high" (unlike investment/lottery/bec,
which band "high" on >=2) — a deliberately stricter bar since a courier
scam typically needs impersonation + contraband claim + police-transfer
threat together to read as the full Digital Arrest precursor pattern.

Fixed on port: normalized risk_level to lowercase; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/courier", tags=["Fraud Coverage"])

# Real indicators for courier scams (parcels containing illegal items used as leverage for Digital Arrest)
_COURIER_BRAND_RE = re.compile(r"(fedex parcel|dhl courier|customs department|narcotics control|cbic office)", re.IGNORECASE)
_CONTRABAND_RE = re.compile(r"(illegal drugs|mdma|multiple passports|contraband|money laundering package)", re.IGNORECASE)
_POLICE_TRANSFER_RE = re.compile(r"(transferring to cyber cell|skype investigation|cbi clearance|digital arrest process)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_courier_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Courier-impersonation/contraband/police-threat phrase scan."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _COURIER_BRAND_RE.search(text):
        flags.append("Impersonation of courier service or customs officials")
    if _CONTRABAND_RE.search(text):
        flags.append("False claims of illegal contraband inside a parcel")
    if _POLICE_TRANSFER_RE.search(text):
        flags.append("Threat of immediate transfer to law enforcement/CBI")

    if len(flags) == 3:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 2:
        risk_level, confidence = "medium", 0.70
    elif len(flags) == 1:
        risk_level, confidence = "low", 0.40
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
