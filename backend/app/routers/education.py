"""
/education — Vernacular scam-story video library (item 79) with a
heatmap tie-in (item 80), a `target_audience` filter for elderly-focused
content (item 39), and a real annual public report (item 81). Ported
from the Track 2 collaborator repo's app/routers/education.py — the
hardcoded video list is legitimate scope here per the original brief
(static content, no frontend needed for this item), kept as-is.

FIXED during the port: `heatmap_layer_url` now genuinely points at this
codebase's real /community/heatmap endpoint (item 35, see segments.py),
not a stub/copy of the reference's own URL.

ITEM 39 (video-first awareness content) is legitimately non-engineering
scope per the original brief — actual video production is out of this
session. The one honest backend hook available was added instead: each
`VideoContent` now carries a `target_audience` (`"general"`/`"elderly"`)
tag, filterable via a new query param, so elderly-focused content can be
surfaced once it exists. All 3 current videos are tagged `"general"` —
none of them are actually elderly-specific yet, and this doesn't pretend
otherwise; the filter mechanism is the deliverable, not fabricated content.

ITEM 81 (annual public report) rebuilt for real: the reference hardcoded
every number (`total_prevented_cases`, `top_impersonated_agencies`,
`demographic_most_targeted`, `average_demand_amount_inr`) with no backing
data at all. Fixed: computes real counts from tables that now actually
exist in this backend — total HeatmapPoint rows (item 35) and total
B2BThreatIndicator rows (item 77). `year` is computed from the current
date instead of a hardcoded literal. The three reference stats with no
backing table (top_impersonated_agencies, demographic_most_targeted,
average_demand_amount_inr) are omitted entirely rather than reproduced
as plausible-looking placeholder numbers — `note` states why.

No envelope; response_model= directly.
"""
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.responses import AnnualReportResponse, ContentLibraryResponse, VideoContent
from app.models.track2_db import B2BThreatIndicator, HeatmapPoint

router = APIRouter(prefix="/education", tags=["Awareness & Education"])

_VIDEOS = [
    VideoContent(id="vid_001", lang="hi", title="डिजिटल अरेस्ट से कैसे बचें", url="/assets/hi_arrest_sim.mp4", tags=["digital_arrest", "police"], target_audience="general"),
    VideoContent(id="vid_002", lang="te", title="ఫేక్ పోలీస్ కాల్స్ తో జాగ్రత్త", url="/assets/te_police_sim.mp4", tags=["police_impersonation"], target_audience="general"),
    VideoContent(id="vid_003", lang="en", title="How scammers use KYC panics", url="/assets/en_kyc_sim.mp4", tags=["kyc", "bank"], target_audience="general"),
]

_HEATMAP_LAYER_URL = "/community/heatmap"  # item 35's real endpoint — see segments.py

_ANNUAL_REPORT_NOTE = (
    "Only stats derivable from real, already-collected data are included. The reference's "
    "top_impersonated_agencies, demographic_most_targeted, and average_demand_amount_inr were "
    "hardcoded placeholders with no backing table — omitted here rather than faked with a "
    "plausible-looking number."
)


@router.get("/content-library", response_model=ContentLibraryResponse)
async def get_vernacular_content(
    language: str = Query("en"),
    target_audience: Optional[Literal["general", "elderly"]] = Query(None),
) -> ContentLibraryResponse:
    """Return the awareness-video library, filtered by language ('all' returns everything)
    and optionally by target_audience."""
    filtered = [v for v in _VIDEOS if v.lang == language or language == "all"]
    if target_audience is not None:
        filtered = [v for v in filtered if v.target_audience == target_audience]
    return ContentLibraryResponse(videos=filtered, heatmap_layer_url=_HEATMAP_LAYER_URL)


@router.get("/annual-report", response_model=AnnualReportResponse)
async def get_annual_scam_report(db: Session = Depends(get_db)) -> AnnualReportResponse:
    """Compute real aggregate stats from data already collected by this backend."""
    heatmap_count = db.query(HeatmapPoint).count()
    b2b_count = db.query(B2BThreatIndicator).count()

    return AnnualReportResponse(
        year=datetime.now(timezone.utc).year,
        total_heatmap_incidents_logged=heatmap_count,
        total_b2b_threat_indicators_flagged=b2b_count,
        note=_ANNUAL_REPORT_NOTE,
    )
