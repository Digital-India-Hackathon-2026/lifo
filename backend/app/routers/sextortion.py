"""
/scams/sextortion — Sextortion fast-path support flow (catalog item 9).

Scoped by the catalog as "routing/escalation, not content analysis." The
reference (app/routers/sextortion.py — NOT sextortion_scam.py, which is
dead/unmounted in the reference, confirmed by the audit) has a single
content-analysis keyword regex and its "routing" is one static block of
text regardless of input. Content regex kept as-is (it's a legitimate
first signal), but the escalation dimension is new: `escalation_path` is
computed from a separate minor-indicator regex (age/school/grade-level
language) rather than hardcoded, and routes to a distinct,
minor-appropriate escalation string (POCSO Act 2012, Childline 1098)
instead of the reference's single adult-oriented block regardless of who
the text actually describes.

This remains a backend service returning structured guidance, NOT a live
handoff to a counselor, helpline queue, or ticketing system — building
real routing/ticketing infra is out of scope. `note` says so explicitly
in every response, same never-overclaim convention as the moonshot PoC.

Fixed on port: dropped the reference's envelope wrapper; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
Transcript preferred — this is inherently a chat/DM-style disclosure, not
an email. risk_level stays the reference's genuine binary low/high (no
"medium" tier exists in the source content regex — a single keyword
match, not a flag count — so a 3-tier enum here would misrepresent it).
"""
import re

from fastapi import APIRouter

from app.models.responses import SextortionResponse
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/sextortion", tags=["Fraud Coverage"])

_SEXTORTION_KEYWORDS_RE = re.compile(
    r"(viral video|leak your video|send to your friends|morphed video|screen recording|pay money or upload)",
    re.IGNORECASE,
)

# Age/school/grade-level language suggesting the person described is a minor.
_MINOR_INDICATOR_RE = re.compile(
    r"\b(?:i am|i'm)?\s*1[0-7]\s*(?:years old|yo|yrs old)\b"
    r"|\bclass\s+(?:[1-9]|1[0-2])\b"
    r"|\bgrade\s+(?:[1-9]|1[0-2])\b"
    r"|\bschool student\b|\bminor\b|\bunder\s*18\b|\bboard exam\b",
    re.IGNORECASE,
)

_NOTE = (
    "This endpoint returns structured guidance only — it is not a live handoff to a "
    "counselor, helpline queue, or ticketing system. A human must still act on this guidance."
)

_ADULT_ESCALATION = (
    "File an urgent report at cybercrime.gov.in or call national helpline 1930. Inform them "
    "this is a sextortion case to trigger immediate platform takedown requests."
)

_MINOR_ESCALATION = (
    "This appears to involve a minor. File an urgent report at cybercrime.gov.in (POCSO e-Box) "
    "or call Childline 1098 immediately, in addition to the National Cyber Crime Helpline 1930. "
    "Cases involving minors trigger mandatory reporting obligations under the POCSO Act, 2012 — "
    "do not delay escalating to a trusted adult or law enforcement."
)


@router.post("/check", response_model=SextortionResponse)
async def check_sextortion(req: TranscriptRequest) -> SextortionResponse:
    """Blackmail-keyword content scan, routed to a minor- or adult-appropriate escalation path."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    keyword_hit = bool(_SEXTORTION_KEYWORDS_RE.search(text))
    if keyword_hit:
        flags.append("Blackmail threat involving video/image exposure detected")

    minor_indicated = bool(_MINOR_INDICATOR_RE.search(text))
    if minor_indicated:
        flags.append("Age/school-context language suggesting a minor detected")

    escalation_path = "minor_protection" if minor_indicated else "adult_standard"

    if keyword_hit:
        immediate_actions = [
            "Deactivate or lock your social media profiles immediately to stop scammers from gathering your friend list.",
            "Do NOT pay any money. Extortionists always demand more after the first payment.",
            "Take screenshots of the chat history, the profile URL, and the payment handles used by the scammer.",
        ]
        if minor_indicated:
            immediate_actions.insert(0, "Involve a trusted parent, guardian, or teacher immediately.")
        legal_escalation = _MINOR_ESCALATION if minor_indicated else _ADULT_ESCALATION
        risk_level = "high"
    else:
        immediate_actions = ["No immediate threats detected. Maintain general digital hygiene."]
        legal_escalation = "None required."
        risk_level = "low"

    return SextortionResponse(
        risk_level=risk_level,
        flags=flags,
        escalation_path=escalation_path,
        immediate_actions=immediate_actions,
        legal_escalation=legal_escalation,
        note=_NOTE,
    )
