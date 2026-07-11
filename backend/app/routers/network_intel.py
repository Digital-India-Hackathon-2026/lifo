"""
/network-intel — Campaign Graph: cross-references scam entities (phone numbers,
UPI IDs, domains, APK hashes, ...) into a graph of who's connected to whom.

Entities are SHA256-hashed before storage (Zero-Knowledge) — the raw value never
touches the database. Algorithm ported from the Track 3 prototype
(kavach-track3-scratch); see AGENTS.md for provenance.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import Base, engine, get_db
from app.models.network_intel_db import ScamEntity, ScamRelation  # noqa: F401 — registers tables on Base.metadata
from app.models.responses import LinkResponse, ThreatTaxonomy
from app.services.graph_engine import GraphIntelligenceEngine

router = APIRouter(prefix="/network-intel", tags=["network-intel"])


class _LinkRequest(BaseModel):
    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    taxonomy: ThreatTaxonomy
    relation_type: str = Field(..., min_length=1)


class _MulehunterFeedRequest(BaseModel):
    source_account: str = Field(..., min_length=1)
    target_account: str = Field(..., min_length=1)


def init_db() -> None:
    """Called at startup. Creates network-intel tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


@router.post("/link", response_model=LinkResponse)
async def link_entities(req: _LinkRequest, db: Session = Depends(get_db)) -> LinkResponse:
    """Hash and link two scam entities into the campaign graph, deduping repeat edges."""
    result = GraphIntelligenceEngine.ingest_scam_relation(
        db, req.source, req.target, req.taxonomy, req.relation_type
    )
    return LinkResponse(
        edge_status=result["edge_status"],
        source_node_id=result["source_node_id"],
        target_node_id=result["target_node_id"],
        taxonomy=result["taxonomy_enforced"],
    )


@router.post("/mulehunter-feed", response_model=LinkResponse)
async def mulehunter_feed(req: _MulehunterFeedRequest, db: Session = Depends(get_db)) -> LinkResponse:
    """Feeder for NPCI MuleHunter — links a fund-transfer pair as MULE_ACCOUNT
    through the existing campaign-graph ingest pipeline (item 31)."""
    result = GraphIntelligenceEngine.ingest_scam_relation(
        db, req.source_account, req.target_account, ThreatTaxonomy.MULE_ACCOUNT, "TRANSFERRED_FUNDS"
    )
    return LinkResponse(
        edge_status=result["edge_status"],
        source_node_id=result["source_node_id"],
        target_node_id=result["target_node_id"],
        taxonomy=result["taxonomy_enforced"],
    )
