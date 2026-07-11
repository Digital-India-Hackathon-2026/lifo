"""
/blocklist — Federated Privacy-Preserving Blocklist: report and check threat
indicators (phishing URLs, mule accounts, spoofed voices, malicious APKs) by
hash only.

Indicators are SHA256-hashed before storage or lookup — the raw value never
touches the database. Algorithm ported from the Track 3 prototype
(kavach-track3-scratch); see AGENTS.md for provenance.
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import Base, engine, get_db
from app.models.network_intel_db import PrivacyPreservingBlocklist  # noqa: F401 — registers table on Base.metadata
from app.models.responses import IngestResponse, ScanResponse, ThreatTaxonomy
from app.services.blocklist_engine import PrivacyBlocklistEngine

router = APIRouter(prefix="/blocklist", tags=["blocklist"])


class _ReportRequest(BaseModel):
    indicator: str = Field(..., min_length=1)
    taxonomy: ThreatTaxonomy


class _ChakshuReportRequest(BaseModel):
    raw_phone_number: str = Field(..., min_length=1)


def init_db() -> None:
    """Called at startup. Creates blocklist tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


@router.post("/report", response_model=IngestResponse)
async def report_indicator(req: _ReportRequest, db: Session = Depends(get_db)) -> IngestResponse:
    """Hash and store a threat indicator, rejecting repeat reports of the same indicator."""
    result = PrivacyBlocklistEngine.ingest_threat(db, req.indicator, req.taxonomy)
    return IngestResponse(
        status=result["status"],
        hash_signature=result.get("hash_signature"),
        taxonomy=result.get("taxonomy"),
        reason=result.get("reason"),
    )


@router.get("/check", response_model=ScanResponse)
async def check_indicator(
    indicator: str = Query(..., min_length=1), db: Session = Depends(get_db)
) -> ScanResponse:
    """Hash-match an indicator against the blocklist."""
    result = PrivacyBlocklistEngine.scan_network_traffic(db, indicator)
    return ScanResponse(**result)


@router.post("/chakshu-report", response_model=IngestResponse)
async def chakshu_report(req: _ChakshuReportRequest, db: Session = Depends(get_db)) -> IngestResponse:
    """Feeder for Chakshu/Sanchar Saathi (DoT) — reports a raw phone number as
    VOICE_SPOOF through the existing blocklist ingest pipeline (item 32)."""
    result = PrivacyBlocklistEngine.ingest_threat(db, req.raw_phone_number, ThreatTaxonomy.VOICE_SPOOF)
    return IngestResponse(
        status=result["status"],
        hash_signature=result.get("hash_signature"),
        taxonomy=result.get("taxonomy"),
        reason=result.get("reason"),
    )
