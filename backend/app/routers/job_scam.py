"""
/scams/job — Fake job / work-from-home scam detector (catalog item 3).

Advance-fee, unrealistic-earnings, and platform-pivot phrase patterns and
exact-count risk banding ported from the Track 1 collaborator repo's
app/routers/job_scam.py — real, tested detection logic, kept as-is. No
dead/unreachable branch found (checked per Session 26's task — see
AGENTS.md).

ENHANCED, not a pure port: the catalog explicitly asks for an "MCA
registry cross-check" (item 3), which does not exist in the reference at
all. A live Ministry of Corporate Affairs registry API integration is out
of scope — no such public API exists reliably. Instead: a clearly-labeled
heuristic proxy — when advance-fee language is present alongside a
capitalized company-name mention that isn't on a small hardcoded allowlist
of well-known legitimate employers, that's treated as an independent
escalation signal on top of the base phrase-count risk, not just another
item folded into the flag count (which would break the reference's
exact-count-of-3 banding — it was built for exactly 3 possible flags).
`mca_check_note` is always present and explicitly states this is a
heuristic proxy, not a live registry lookup — same never-overclaim
convention as the moonshot PoC's `note` field.

Fixed on port: dropped the reference's envelope wrapper; normalized
risk_level to lowercase; falls back to email_body when transcript is
empty (TranscriptRequest, shared from romance_scam.py, now requires at
least one of the two to be non-empty). Transcript preferred — WFH scam
pitches typically arrive as chat/message text.
"""
import re

from fastapi import APIRouter

from app.models.responses import JobScamResponse
from app.routers.romance_scam import TranscriptRequest

router = APIRouter(prefix="/scams/job", tags=["Fraud Coverage"])

# Real-world Indian fake job indicators: advance fees, unrealistic task-based pay, and platform pivots
_ADVANCE_FEE_RE = re.compile(r"(registration fee|training fee|security deposit|refundable deposit|starter kit)", re.IGNORECASE)
_UNREALISTIC_EARNINGS_RE = re.compile(r"(earn .* per day|no experience needed|liking videos|rating hotels|captcha solving|vip task tier)", re.IGNORECASE)
_PLATFORM_PIVOT_RE = re.compile(r"(join.*telegram|download custom app|whatsapp group)", re.IGNORECASE)

_MCA_CHECK_NOTE = (
    "Company name check is a heuristic proxy against a small hardcoded allowlist of "
    "well-known legitimate employers — it is NOT a live Ministry of Corporate Affairs "
    "(MCA) registry lookup. A company not being on this list does not itself prove fraud."
)

# Small allowlist of well-known legitimate Indian/multinational employers — heuristic only.
_KNOWN_LEGIT_EMPLOYERS = {
    "tcs", "tata consultancy services", "infosys", "wipro", "accenture",
    "amazon", "flipkart", "hcl", "hcltech", "cognizant", "ibm", "google",
    "microsoft", "tech mahindra", "capgemini", "deloitte", "reliance",
}

# Captures a capitalized company-like phrase following common lead-in words.
# Lead-in phrase is case-insensitive; the captured name itself must start with a
# capital letter, since a claimed employer name is expected to be a proper noun.
_COMPANY_MENTION_RE = re.compile(
    r"(?:(?i:at|from|on behalf of|representing))\s+([A-Z][A-Za-z&.\-]+(?:\s+[A-Z][A-Za-z&.\-]+){0,3})"
)

_RISK_TIERS = ["low", "medium", "high"]


def _escalate(risk_level: str) -> str:
    idx = _RISK_TIERS.index(risk_level)
    return _RISK_TIERS[min(idx + 1, len(_RISK_TIERS) - 1)]


@router.post("/check", response_model=JobScamResponse)
async def check_job_scam(req: TranscriptRequest) -> JobScamResponse:
    """Advance-fee/unrealistic-earnings/platform-pivot phrase scan, plus an
    MCA-registry-proxy escalation signal for unverified employer names."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []

    advance_fee_hit = bool(_ADVANCE_FEE_RE.search(text))
    if advance_fee_hit:
        flags.append("Advance fee or security deposit requested")
    if _UNREALISTIC_EARNINGS_RE.search(text):
        flags.append("Unrealistic earnings promised for trivial tasks")
    if _PLATFORM_PIVOT_RE.search(text):
        flags.append("Pivot to unmonitored platform (Telegram/WhatsApp)")

    phrase_hits = len(flags)
    if phrase_hits == 3:
        risk_level, confidence = "high", 0.95
    elif phrase_hits == 2:
        risk_level, confidence = "medium", 0.70
    elif phrase_hits == 1:
        risk_level, confidence = "low", 0.40
    else:
        risk_level, confidence = "low", 0.10

    if advance_fee_hit:
        match = _COMPANY_MENTION_RE.search(text)
        if match:
            company = match.group(1).strip()
            if company.lower() not in _KNOWN_LEGIT_EMPLOYERS:
                flags.append(
                    f"Company '{company}' mentioned alongside an advance-fee request is not "
                    f"on the known-legitimate employer list (heuristic check only — not a "
                    f"live MCA registry lookup)"
                )
                new_level = _escalate(risk_level)
                if new_level != risk_level:
                    risk_level = new_level
                    confidence = {"medium": 0.75, "high": 0.97}[risk_level]

    return JobScamResponse(
        risk_level=risk_level,
        flags=flags,
        confidence_score=confidence,
        mca_check_note=_MCA_CHECK_NOTE,
    )
