"""
/community + /segments — Crowdsourced scam reporting network + heatmap
(catalog items 34/35) and Adjacent User Segments risk evaluation (catalog
items 51-56: NRI remote-guardian, SME/MSME shield, kids/teen protection,
migrant-worker fraud, government-employee/pensioner, domestic-help/
caregiver verification). Ported from the Track 2 collaborator repo's
app/routers/segments.py — re-read in full this session for the
/evaluate section specifically (34/35 were already ported in Session 27).

Router no longer carries a `/community` prefix: `/segments/evaluate`
doesn't share that prefix, so each route now writes its own full path
explicitly instead — same fix `complaint.py` used in Session 22 to add
`/legal/templates/ezero-fir` alongside `/assist/complaint` on one router
object without moving either path. `/community/report` and
`/community/heatmap` are byte-for-byte unchanged in path and behavior.

ITEMS 51-56 (segment risk evaluation): the reference gates all 6 segments
on a single hardcoded endpoint matched against 1-2 keyword phrases each
(e.g. NRI: "urgent transfer" or "accident") — thin, the same shallowness
already fixed for items 44/45 last session. Built a real
`list[tuple[re.Pattern, str]]` per segment (document.py/digital_arrest.py's
established pattern-list shape), 3-4 patterns each, with the same
flag-count risk banding every Track 1 fraud detector already uses
(>=2 flags = high, ==1 = medium, 0 = low). Flags are human-readable
sentences, matching the Track 1 family's convention (romance_scam.py,
bec_scam.py, etc.) rather than document.py's own snake_case labels —
these are newly-authored patterns, not a verbatim import of document.py's
existing tuples the way items 44/45's chat webhook was.

SME (52) deliberately reuses bec_scam.py's `_BANK_CHANGE_RE`/
`_EXEC_IMPERSONATION_RE`/`_ACUTE_URGENCY_RE` instead of redefining
equivalents: SME/MSME vendor fraud IS Business Email Compromise, just
targeting a smaller company — the same phenomenon, not a coincidentally
similar one. Only one segment-specific addition was needed: a fake-GST-
notice pattern, since GST compliance threats aren't a BEC concept.

KIDS (53) frames its response as risk-signal visibility only, per the
original catalog item's explicit instruction ("framed as risk visibility,
not chat monitoring") — its `note` states plainly that this checks
message content already provided to it, and does not monitor, read, or
store a child's chats. Every segment gets a `note`, matching the
never-overclaim-certainty convention used throughout this codebase
(CONFIDENCE_NOTE, the moonshot PoC's note, item 50's honest-stub note).

The reference's ad-hoc `else: raise HTTPException(400, ...)` for an
unrecognized segment_type is gone — `segment_type` is now a real
`Literal[...]` on the request model, so FastAPI/Pydantic reject an
invalid value with a genuine 422 automatically, matching the taxonomy
strictness the reference's own comment ("strict adherence to provided
taxonomy; no new nodes created") asked for but didn't actually enforce
at the validation layer.

FIXED during the port (items 34/35, unchanged from Session 27): the
reference's reputation gate was decorative — reputation always starts at
1 and the gating condition (`reputation > 0`) is therefore always true,
so every single report — including someone's very first — always landed
on the public heatmap. Real gate here: report_count must be >= 2 (i.e.
not the reporter's first-ever report) before a submission contributes to
the heatmap. First reports are still persisted and counted, just don't
influence the public-facing aggregate yet. Needs real persistence
(in-memory state defeats the point of "aggregated" data) — reuses
backend/app/core/database.py, same as every Track 3 item; this repo has
zero tests, confirmed by the audit.

No envelope; response_model= directly; real HTTP status codes throughout
(201 for a newly created report, instead of the reference's decorative
KavachResponse.status_code field riding on a transport that's always
200); segments/evaluate needs no DB — stateless pattern matching, same
as every other fraud-type detector.
"""
import re
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import Base, engine, get_db
from app.models.responses import (
    HeatmapResponse,
    HeatmapZone,
    ScamReportResponse,
    SegmentEvaluationResponse,
)
from app.models.track2_db import HeatmapPoint, ReporterReputation
from app.routers.bec_scam import _ACUTE_URGENCY_RE, _BANK_CHANGE_RE, _EXEC_IMPERSONATION_RE

router = APIRouter(tags=["Community & Segments"])

_REPUTATION_THRESHOLD = 2  # must not be the reporter's first-ever report


class _ScamReportRequest(BaseModel):
    reporter_id: str = Field(..., min_length=1)
    scam_type: str = Field(..., min_length=1)
    location_lat: float = Field(..., ge=-90, le=90)
    location_lng: float = Field(..., ge=-180, le=180)
    description: str = Field(..., min_length=1)


class _SegmentEvaluationRequest(BaseModel):
    segment_type: Literal["NRI", "SME", "KIDS", "MIGRANT", "PENSIONER", "DOMESTIC"]
    payload_text: str = Field(..., min_length=1)


# ── Item 51: NRI remote-guardian ──────────────────────────────────────────────
_NRI_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(urgent(ly)?\s+(fund|money)\s+transfer|send\s+money\s+immediately|wire\s+funds\s+now)", re.I),
     "Urgent, time-pressured money transfer request"),
    (re.compile(r"(accident|hospitali[sz]ed|\bicu\b|emergency\s+surgery|critical\s+condition)", re.I),
     "Fabricated medical-emergency framing"),
    (re.compile(r"(can'?t\s+video\s+call|camera\s+(is\s+)?(broken|not\s+working)|no\s+video\s+call|network\s+(too\s+)?(weak|poor)\s+for\s+video)", re.I),
     "Video-call-avoidance excuse (classic impersonation tell)"),
    (re.compile(r"(western\s+union|moneygram|gift\s+cards?|crypto(currency)?\s+wallet|unfamiliar\s+bank\s+account|new\s+account\s+number)", re.I),
     "Request to pay via an unfamiliar/untraceable channel"),
]

# ── Item 52: SME/MSME shield — reuses bec_scam.py's patterns (SME vendor
# fraud IS BEC, just targeting a smaller company) plus a GST-specific addition
_SME_PATTERNS: list[tuple[re.Pattern, str]] = [
    (_BANK_CHANGE_RE, "Sudden request to change vendor/payee bank details"),
    (_EXEC_IMPERSONATION_RE, "Executive isolation or confidentiality pressure detected"),
    (_ACUTE_URGENCY_RE, "High-pressure temporal urgency for wire transfers"),
    (re.compile(r"(gst\s+(notice|penalty|non-?compliance|mismatch)|gstin\s+(suspended|blocked|cancelled)|goods\s+and\s+services\s+tax\s+notice)", re.I),
     "Fake GST notice / GSTIN compliance threat"),
]

# ── Item 53: Kids/teen protection ─────────────────────────────────────────────
_KIDS_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(v-?bucks|robux|free\s+(skins?|coins?|gems?|diamonds?|loot))", re.I),
     "Gaming-currency scam language"),
    (re.compile(r"(free\s+(gift|giveaway|prize)|you'?ve\s+won|secret\s+(admin|mod)\s+code)", re.I),
     "Unsolicited gift/prize offer from a stranger"),
    (re.compile(r"(add\s+me\s+on\s+(discord|snap(chat)?|whatsapp|instagram)|meet\s+(me\s+)?in\s+person|don'?t\s+tell\s+your\s+parents|keep\s+this\s+(a\s+)?secret)", re.I),
     "Stranger requesting off-platform contact or secrecy"),
]

# ── Item 54: Migrant-worker overseas-recruitment fraud ───────────────────────
_MIGRANT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(visa\s+(fee|processing\s+fee)|processing\s+fee)\D{0,20}(advance|upfront|before\s+(you\s+)?(depart|leave))", re.I),
     "Advance visa/processing fee demand"),
    (re.compile(r"(guaranteed\s+(overseas|abroad)\s+job|100%\s+job\s+guarantee|no\s+interview\s+required|visa\s+guaranteed)", re.I),
     "Guaranteed-overseas-job claim (recruitment fraud tell)"),
    (re.compile(r"(passport\s+(will\s+be\s+)?(confiscat\w*|held|kept|taken)|surrender\s+your\s+passport|hand\s+over\s+your\s+passport)", re.I),
     "Passport-confiscation threat"),
]

# ── Item 55: Government-employee/pensioner vertical ──────────────────────────
_PENSIONER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(pension\s+(update|verification|re-?verification)|pension\s+will\s+(stop|be\s+suspended))", re.I),
     "Fake pension-update/verification urgency"),
    (re.compile(r"(life\s+certificate|jeevan\s+pramaan)\D{0,20}(expir\w*|pending|urgent|submit\s+immediately)", re.I),
     "Fake life-certificate submission urgency"),
    (re.compile(r"(pf\s+withdrawal|provident\s+fund\s+withdrawal|epf\s+claim)\D{0,20}(urgent|pending|blocked|rejected)", re.I),
     "Fake PF/EPF-withdrawal urgency"),
]

# ── Item 56: Domestic help/caregiver verification ────────────────────────────
_DOMESTIC_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"police\s+verification\D{0,20}(fee|payment|charge|pay)", re.I),
     "Fake police-verification-fee demand"),
    (re.compile(r"character\s+certificate\D{0,20}(fee|payment|pay)", re.I),
     "Fake character-certificate fee demand"),
    (re.compile(r"verification\s+(portal|link)\D{0,20}(pay|fee|payment)", re.I),
     "Fake verification-portal payment link"),
]

_SEGMENT_PATTERNS: dict[str, list[tuple[re.Pattern, str]]] = {
    "NRI": _NRI_PATTERNS,
    "SME": _SME_PATTERNS,
    "KIDS": _KIDS_PATTERNS,
    "MIGRANT": _MIGRANT_PATTERNS,
    "PENSIONER": _PENSIONER_PATTERNS,
    "DOMESTIC": _DOMESTIC_PATTERNS,
}

_SEGMENT_NOTES: dict[str, str] = {
    "NRI": "Pattern-based risk signal only — always verify via a second channel before transferring funds.",
    "SME": "Pattern-based risk signal only — verify vendor bank-detail changes via a known phone number, not the email/message itself.",
    "KIDS": "Risk visibility only: this flags patterns in message content already provided to it. It does not monitor, read, or store a child's chats.",
    "MIGRANT": "Pattern-based risk signal only — verify any recruiter/agency's registration with the government before paying any fee.",
    "PENSIONER": "Pattern-based risk signal only — pension/PF portals never ask for OTP or fees over a call.",
    "DOMESTIC": "Pattern-based risk signal only — verify police-verification requirements directly with the local police station, not via a forwarded link.",
}


def init_db() -> None:
    """Called at startup. Creates the community/segments tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


@router.post("/community/report", response_model=ScamReportResponse, status_code=201)
async def submit_community_report(req: _ScamReportRequest, db: Session = Depends(get_db)) -> ScamReportResponse:
    """Record a scam report and, once the reporter has some track record, add it to the heatmap."""
    reputation = db.query(ReporterReputation).filter(ReporterReputation.reporter_id == req.reporter_id).first()
    if reputation is None:
        reputation = ReporterReputation(reporter_id=req.reporter_id, report_count=0)
        db.add(reputation)

    reputation.report_count += 1
    contributed = reputation.report_count >= _REPUTATION_THRESHOLD
    if contributed:
        db.add(HeatmapPoint(
            lat=req.location_lat,
            lng=req.location_lng,
            scam_type=req.scam_type,
            weight=reputation.report_count,
        ))
    db.commit()

    return ScamReportResponse(
        report_count=reputation.report_count,
        contributed_to_heatmap=contributed,
        message=(
            "Report ingested and added to the public heatmap."
            if contributed
            else "Report ingested. A reporter's first submission doesn't affect the public "
                 "heatmap yet — submit again to build reporting history."
        ),
    )


@router.get("/community/heatmap", response_model=HeatmapResponse)
async def get_scam_heatmap(db: Session = Depends(get_db)) -> HeatmapResponse:
    """Return every point currently on the public community heatmap."""
    points = db.query(HeatmapPoint).all()
    return HeatmapResponse(
        active_zones=[
            HeatmapZone(lat=p.lat, lng=p.lng, scam_type=p.scam_type, weight=p.weight) for p in points
        ]
    )


@router.post("/segments/evaluate", response_model=SegmentEvaluationResponse)
async def evaluate_segment_risk(req: _SegmentEvaluationRequest) -> SegmentEvaluationResponse:
    """Pattern-match a payload against the requested segment's own rule set (items 51-56)."""
    text = req.payload_text
    flags = [label for pattern, label in _SEGMENT_PATTERNS[req.segment_type] if pattern.search(text)]

    if len(flags) >= 2:
        risk_level, confidence = "high", 0.95
    elif len(flags) == 1:
        risk_level, confidence = "medium", 0.70
    else:
        risk_level, confidence = "low", 0.10

    return SegmentEvaluationResponse(
        segment_type=req.segment_type,
        risk_level=risk_level,
        flags=flags,
        confidence_score=confidence,
        note=_SEGMENT_NOTES[req.segment_type],
    )
