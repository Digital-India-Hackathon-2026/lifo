"""
/timeline — Scam Campaign Timeline (catalog item 30). Genuinely new
work, not a port: Track 1's collaborator repo claimed "Redis-backed
session stitching" for this item, but the audit confirmed zero actual
code behind that claim — nothing to read, nothing to port.

The catalog's own framing for this item: the user manually links a
call, a WhatsApp message, and a payment app they experienced as one
campaign, since true cross-app tracking isn't technically or legally
viable. Built exactly that — user-driven, consented, manual linkage,
never automated cross-app surveillance. This router never reads any
other app/service's data on its own initiative; a user must explicitly
submit each event themselves.

Real SQLite persistence (new track1_db.py: CaseFile/CampaignEvent) —
this is identity-linked case history a user builds up over time, the
same persistence category as item 37 (pairing) and item 42 (training
scores), not transient per-call state like item 38's _call_sessions.

New track1_db.py, not an extension of track2_db.py/network_intel_db.py:
item 30 is the first Track 1 item needing a database at all — every
prior Track 1 port (items 1-29 plus the 6 unscoped bonus detectors) is
stateless regex/pattern matching with no table of its own. A dedicated
per-track models file matches the established convention
(network_intel_db.py for Track 3, track2_db.py for Track 2) rather than
bolting a Track 1 concept onto another track's file.

case_id is server-generated ("CASE-" + a 12-char uuid4 hex, same
prefixed-hash style as legal_templates.py's fir_hash) and is the
public-facing identifier; case_id on CampaignEvent is a plain indexed
string column, not a SQLAlchemy ForeignKey — matches this codebase's
existing flat-table-plus-app-level-lookup convention (e.g.
vulnerable.py's PairedDevice), not ORM relationships, which nothing else
here uses either.

No hashing here: unlike phone numbers (items 76/77) or consent identity
(item 82), nothing in a CaseFile/CampaignEvent is the specific kind of
raw-PII this codebase's hash-before-store convention exists to protect
against — the whole point of this feature is the user's own readable
case history.

No envelope; response_model= directly; real HTTP status codes (201 on
create); proper Pydantic validation.
"""
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import Base, engine, get_db
from app.models.responses import CampaignEventResponse, CaseFileResponse, CaseListResponse
from app.models.track1_db import CampaignEvent, CaseFile

router = APIRouter(prefix="/timeline", tags=["Campaign Timeline"])


class _CreateCaseRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)


class _AddEventRequest(BaseModel):
    event_type: Literal["call", "whatsapp", "upi", "document", "other"]
    description: str = Field(..., min_length=1)
    event_timestamp: datetime
    artifact_id: Optional[str] = None


def init_db() -> None:
    """Called at startup. Creates the campaign-timeline tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


def _to_naive_utc(ts: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip, so everything is stored naive-UTC
    (same convention as consent_service.py's _now_utc()). Applied here to a
    user-supplied timestamp for the first time in this codebase: an aware
    input is converted to UTC before the offset is dropped (never just
    stripped, which would silently shift the wall-clock value); a naive
    input is assumed to already be UTC."""
    if ts.tzinfo is not None:
        return ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts


def _case_to_response(case: CaseFile, events: list[CampaignEvent]) -> CaseFileResponse:
    return CaseFileResponse(
        case_id=case.case_id,
        user_id=case.user_id,
        title=case.title,
        status=case.status,
        created_at=case.created_at,
        events=[
            CampaignEventResponse(
                event_type=e.event_type,
                description=e.description,
                event_timestamp=e.event_timestamp,
                artifact_id=e.artifact_id,
            )
            for e in events
        ],
    )


def _get_case_or_404(case_id: str, db: Session) -> CaseFile:
    case = db.query(CaseFile).filter(CaseFile.case_id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case


def _events_for_case(case_id: str, db: Session) -> list[CampaignEvent]:
    return (
        db.query(CampaignEvent)
        .filter(CampaignEvent.case_id == case_id)
        .order_by(CampaignEvent.event_timestamp.asc())
        .all()
    )


@router.post("/cases", response_model=CaseFileResponse, status_code=201)
async def create_case(req: _CreateCaseRequest, db: Session = Depends(get_db)) -> CaseFileResponse:
    """Create a new, empty case file for a suspected campaign."""
    case = CaseFile(
        case_id=f"CASE-{uuid.uuid4().hex[:12].upper()}",
        user_id=req.user_id,
        title=req.title,
        status="open",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    return _case_to_response(case, [])


@router.post("/cases/{case_id}/events", response_model=CampaignEventResponse, status_code=201)
async def add_event(case_id: str, req: _AddEventRequest, db: Session = Depends(get_db)) -> CampaignEventResponse:
    """Add a user-linked event (call/whatsapp/upi/document/other) to an existing case."""
    _get_case_or_404(case_id, db)

    event = CampaignEvent(
        case_id=case_id,
        event_type=req.event_type,
        description=req.description,
        event_timestamp=_to_naive_utc(req.event_timestamp),
        artifact_id=req.artifact_id,
        logged_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return CampaignEventResponse(
        event_type=event.event_type,
        description=event.description,
        event_timestamp=event.event_timestamp,
        artifact_id=event.artifact_id,
    )


@router.get("/cases/{case_id}", response_model=CaseFileResponse)
async def get_case(case_id: str, db: Session = Depends(get_db)) -> CaseFileResponse:
    """Retrieve a case and its events in chronological order (by event_timestamp, not insertion order)."""
    case = _get_case_or_404(case_id, db)
    events = _events_for_case(case_id, db)
    return _case_to_response(case, events)


@router.get("/cases", response_model=CaseListResponse)
async def list_cases(user_id: str = Query(..., min_length=1), db: Session = Depends(get_db)) -> CaseListResponse:
    """List every case belonging to a user, each with its events in chronological order."""
    cases = db.query(CaseFile).filter(CaseFile.user_id == user_id).all()
    return CaseListResponse(
        cases=[_case_to_response(case, _events_for_case(case.case_id, db)) for case in cases]
    )
