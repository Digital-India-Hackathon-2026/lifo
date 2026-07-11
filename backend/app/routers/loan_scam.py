"""
/scams/loan — Fake / predatory loan app detector (catalog item 7).

Data-harvesting, 7-day-tenure, and extortion-threat phrase patterns and
flag-count risk banding ported from the Track 1 collaborator repo's
app/routers/loan_scam.py — real, tested detection logic, kept as-is. No
dead/unreachable branch found (checked per Session 26's task — see
AGENTS.md).

ENHANCED, not a pure port: the catalog explicitly asks for a cross-check
against RBI's Digital Lending Apps directory, which the reference has no
equivalent of at all. Added: a hardcoded reference list of real
bank/NBFC-backed digital lending apps, compiled from public knowledge as
of this writing (NOT a live fetch — no internet access in this session).
This data changes rarely enough that a hardcoded snapshot is a defensible
starting point, but it should be cross-checked against RBI's actual
published list (e.g. via sachet.rbi.org.in) before being relied on in
production. When a claimed app name is mentioned that is NOT on this list
AND at least one phrase signal already matched, that's an independent
escalation signal — not just another item folded into the existing
flag-count formula — matching the "real signal boost, not a bigger flag
list" requirement. `app_registry_status` exposes this as a distinct
structured field rather than burying it in `flags` alone.

Fixed on port: normalized risk_level to lowercase; falls back to
email_body when transcript is empty (TranscriptRequest, shared from
romance_scam.py, now requires at least one of the two to be non-empty).
Transcript preferred — loan-app scam pitches are chat/SMS-style.
"""
import re

from fastapi import APIRouter

from app.models.responses import LoanScamResponse
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/loan", tags=["Fraud Coverage"])

# Indicators based on real 7-day loan app extortion tactics and RBI warnings
_DATA_HARVESTING_RE = re.compile(r"(access to contacts|contact list|photo gallery|read sms logs|phone book)", re.IGNORECASE)
_SEVEN_DAY_TRAP_RE = re.compile(r"(7-day loan|7 days tenure|repay in 7 days|short term 7 day)", re.IGNORECASE)
_EXTORTION_RE = re.compile(r"(morph.*photos|contact your family|defame you|send message to contacts|fake fir)", re.IGNORECASE)

# Captures a claimed app name, e.g. "the app called XYZ", "using the XYZ", "via the XYZ".
# Lead-in phrase is case-insensitive; the captured name itself must start with a
# capital letter, since a claimed app/brand name is expected to be a proper noun.
_APP_NAME_RE = re.compile(r"(?:(?i:app (?:called|named)|using the|via the))\s+([A-Z][A-Za-z0-9]+)")

# Bank/NBFC-backed digital lending apps, compiled from public knowledge of RBI-regulated
# entities' lending apps as of this writing. NOT fetched live from RBI — cross-reference
# RBI's actual published Digital Lending Apps list (e.g. sachet.rbi.org.in) before relying
# on this for anything beyond a demo heuristic.
_RBI_REGISTERED_APPS = {
    "hdfc bank", "icici bank", "axis bank", "kotak mahindra bank", "bajaj finserv",
    "tata capital", "idfc first bank", "navi", "kreditbee", "moneyview", "money view",
    "cashe", "mpokket", "paysense", "fibe", "slice",
}


@router.post("/check", response_model=LoanScamResponse)
async def check_loan_scam(req: TranscriptRequest) -> LoanScamResponse:
    """Data-harvesting/7-day-tenure/extortion phrase scan, plus an RBI-registered-apps
    cross-check that escalates risk when a mentioned app name isn't on the known list."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    if _DATA_HARVESTING_RE.search(text):
        flags.append("Predatory data harvesting (contacts/gallery access requested)")
    if _SEVEN_DAY_TRAP_RE.search(text):
        flags.append("Illegal 7-day loan tenure detected")
    if _EXTORTION_RE.search(text):
        flags.append("Extortion threat (morphed photos or contacting family)")

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.65
    else:
        risk_level, confidence = "low", 0.10

    app_registry_status = "not_mentioned"
    match = _APP_NAME_RE.search(text)
    if match:
        app_name = match.group(1).strip()
        if app_name.lower() in _RBI_REGISTERED_APPS:
            app_registry_status = "registered"
        else:
            app_registry_status = "unregistered"
            if flags:
                flags.append(
                    f"Claimed app name '{app_name}' does not match RBI's registered Digital "
                    f"Lending Apps list (as of writing) — unregistered lending apps are a "
                    f"distinct regulatory red flag"
                )
                if risk_level != "high":
                    risk_level, confidence = "high", 0.97

    return LoanScamResponse(
        risk_level=risk_level,
        flags=flags,
        confidence_score=confidence,
        app_registry_status=app_registry_status,
    )
