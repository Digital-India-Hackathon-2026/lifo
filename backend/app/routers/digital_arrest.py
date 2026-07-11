"""
/check/digital-arrest — Pattern recognition for Digital Arrest scam call transcripts.

Reuses _SCAM_PATTERNS, _PAYMENT_PATTERNS, and _ANCHOR from document.py (ponytail: import, don't redefine).
Adds 3 call-specific patterns for spoken-register phrasing that never appears in written notices.

Accepts either a raw transcript string or a honeypot session_id (pulls concatenated turn
transcripts from the in-memory session store).
"""
import re
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.models.responses import DISCLAIMER, DigitalArrestResponse
from app.routers.document import (
    _ANCHOR,
    _PAYMENT_PATTERNS,
    _PAYMENT_TYPES,
    _SCAM_PATTERNS,
)

router = APIRouter(prefix="/check", tags=["digital-arrest"])

MAX_TRANSCRIPT_CHARS = 10_000

# Call-specific patterns: spoken-register phrasing that does not appear in written notices.
# Imported document patterns cover the rest — do not redefine them here.
_CALL_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Caller control — keeps victim on the line to prevent consultation
    (re.compile(
        r"(?:don.?t\s+(?:hang\s+up|disconnect|cut\s+the\s+(?:call|line)|end\s+the\s+(?:call|line))"
        r"|stay\s+on\s+(?:the\s+)?(?:line|call))",
        re.I,
    ), "stay_on_line"),
    # False surveillance — intimidation by claiming real-time tracking
    (re.compile(
        r"(?:track(?:ing)?|monitor(?:ing)?)\s+your\s+(?:phone|device|location|ip\b)"
        r"|(?:i\s+can|we\s+can)\s+see\s+your\s+(?:location|screen|activity|phone)",
        re.I,
    ), "surveillance_claim"),
    # Live-countdown pressure — distinct from "within 24 hours" (written deadline)
    (re.compile(
        r"warrant\s+(?:is\s+)?(?:being\s+)?(?:issued|filed|generated)\s+(?:right\s+now|as\s+we\s+speak)"
        r"|you\s+have\s+(?:only\s+)?\d+\s+minutes\s+(?:to\s+comply|before\s+(?:we|the\s+warrant))",
        re.I,
    ), "immediate_warrant_pressure"),
]

_ALL_PATTERNS = _SCAM_PATTERNS + _CALL_PATTERNS


class _DigitalArrestRequest(BaseModel):
    transcript: Optional[str] = Field(None, max_length=MAX_TRANSCRIPT_CHARS)
    session_id: Optional[str] = None

    @model_validator(mode="after")
    def _require_one(self):
        # Check for None explicitly — empty string is caught by the endpoint (→ 400, not 422)
        if self.transcript is None and self.session_id is None:
            raise ValueError("Provide either 'transcript' or 'session_id'.")
        return self


def _resolve_transcript(req: _DigitalArrestRequest) -> str:
    """Return the transcript text, pulling from honeypot session store if needed."""
    if req.transcript is not None:
        return req.transcript
    # session_id path: import _sessions lazily to avoid circular-import at module load
    from app.routers.honeypot import _sessions  # noqa: PLC0415

    if req.session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Honeypot session not found.")
    turns = _sessions[req.session_id].get("turns", [])
    return " ".join(t["transcript"] for t in turns if t.get("transcript"))


def _analyze_transcript(text: str) -> tuple[list[str], list[str]]:
    """Return (matched_scam_labels, matched_payment_labels). Pure, stateless."""
    seen: set[str] = set()
    scam_hits: list[str] = []
    payment_hits: list[str] = []

    for pattern, label in _ALL_PATTERNS:
        if label not in seen and pattern.search(text):
            scam_hits.append(label)
            seen.add(label)

    for pattern, label in _PAYMENT_PATTERNS:
        if label not in seen and pattern.search(text):
            payment_hits.append(label)
            seen.add(label)

    return scam_hits, payment_hits


def _severity(scam_hits: list[str], payment_hits: list[str]) -> Literal["low", "medium", "high"]:
    has_scam = bool(scam_hits)
    has_payment = bool(payment_hits)
    if has_scam and has_payment:
        return "high"
    if has_scam or has_payment:
        return "medium"
    return "low"


@router.post("/digital-arrest", response_model=DigitalArrestResponse)
async def check_digital_arrest(req: _DigitalArrestRequest) -> DigitalArrestResponse:
    """Analyse a call transcript for Digital Arrest scam patterns.

    Accepts a raw transcript string or a honeypot session_id. Reuses the rule set
    from /classify/document plus 3 call-specific spoken-register patterns.
    """
    text = _resolve_transcript(req)

    if not text.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty — nothing to analyse.")

    scam_hits, payment_hits = _analyze_transcript(text)
    sev = _severity(scam_hits, payment_hits)

    if sev == "high":
        note = "Multiple Digital Arrest scam indicators detected — this matches a known active fraud pattern."
    elif sev == "medium":
        note = "Suspicious language detected. Treat any request for payment or personal information with extreme caution."
    else:
        note = "No Digital Arrest patterns detected. If you feel threatened, hang up and call 1930 (National Cyber Crime Helpline)."

    return DigitalArrestResponse(
        matched_patterns=scam_hits,
        payment_indicators_found=payment_hits,
        severity=sev,
        hard_factual_anchor=_ANCHOR.strip(),
        note=note,
        disclaimer=DISCLAIMER,
    )
