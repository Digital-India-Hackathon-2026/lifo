"""
/scams/matrimonial — Matrimonial fraud detector (catalog item 8).

Fake-NRI-persona, customs-clearance-trap, and sudden-emergency phrase
patterns and flag-count risk banding ported from the Track 1 collaborator
repo's app/routers/matrimonial_scam.py — real, tested detection logic,
kept as-is. No dead/unreachable branch found in this router (checked per
Session 24's task — see AGENTS.md).

Fixed on port: normalized risk_level to lowercase; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
Transcript preferred over email_body — matrimonial-platform chat is the
natural channel for this scam type.
"""
import re

from fastapi import APIRouter

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/matrimonial", tags=["Fraud Coverage"])

# Indicators based on standard matrimonial scams (NRI persona + customs fee trap)
_NRI_PERSONA_RE = re.compile(r"(nri doctor|uk surgeon|engineer in us|marine engineer|returning to india soon)", re.IGNORECASE)
_CUSTOMS_TRAP_RE = re.compile(r"(stuck at customs|airport clearance|customs duty for parcel|release the package|penalty fee)", re.IGNORECASE)
_SUDDEN_EMERGENCY_RE = re.compile(r"(medical emergency|robbed|lost wallet|need urgent cash before meeting)", re.IGNORECASE)


@router.post("/check", response_model=ScamPatternResponse)
async def check_matrimonial_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Fake-NRI-persona/customs-trap/sudden-emergency phrase scan for matrimonial fraud."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _NRI_PERSONA_RE.search(text):
        flags.append("Common fake NRI persona detected")
    if _CUSTOMS_TRAP_RE.search(text):
        flags.append("Customs clearance / parcel release trap detected")
    if _SUDDEN_EMERGENCY_RE.search(text):
        flags.append("Sudden financial emergency before meeting in person")

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.60
    else:
        risk_level, confidence = "low", 0.10

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=confidence, evidence_trail=flat_evidence_trail(flags))
