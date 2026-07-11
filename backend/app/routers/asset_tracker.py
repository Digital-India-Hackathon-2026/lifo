"""
/legal/asset-tracker — Asset-Recovery Status Tracker (Track 3, item 68).

Built new — the Track 3 prototype had a read-only query with no write path
and a missing case_id returned a fake "NO_FUNDS_FROZEN" success placeholder
instead of a real not-found. Here: a duplicate hold on an existing case_id
is a 409 conflict (use PATCH to update it instead), and a missing case_id
on update/get is a real 404 — never masked. See AGENTS.md for the full
gap analysis.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import Base, engine, get_db
from app.models.network_intel_db import AssetRecoveryEntity  # noqa: F401 — registers table on Base.metadata
from app.models.responses import AssetStatus, AssetTrackerResponse
from app.services.asset_engine import AssetTrackerService

router = APIRouter(prefix="/legal/asset-tracker", tags=["asset-tracker"])


class _HoldRequest(BaseModel):
    case_id: str = Field(..., min_length=1)
    frozen_amount: float = Field(..., gt=0)
    bank_node: str = Field(..., min_length=1)


class _UpdateRequest(BaseModel):
    status: Optional[AssetStatus] = None
    frozen_amount: Optional[float] = Field(None, gt=0)


def init_db() -> None:
    """Called at startup. Creates the asset-recovery table if it doesn't exist yet."""
    Base.metadata.create_all(bind=engine)


def _to_response(row: AssetRecoveryEntity) -> AssetTrackerResponse:
    return AssetTrackerResponse(
        case_id=row.case_id,
        frozen_amount=row.frozen_amount,
        bank_node=row.bank_node,
        status=row.status,
        hold_timestamp_utc=row.hold_timestamp_utc,
        last_updated_utc=row.last_updated_utc,
    )


@router.post("/hold", response_model=AssetTrackerResponse)
async def create_hold(req: _HoldRequest, db: Session = Depends(get_db)) -> AssetTrackerResponse:
    """Create a new asset hold (status=FROZEN). A second hold on the same
    case_id is a conflict — use PATCH to update an existing case instead."""
    row = AssetTrackerService.create_hold(db, req.case_id, req.frozen_amount, req.bank_node)
    if row is None:
        raise HTTPException(status_code=409, detail=f"A hold already exists for case_id '{req.case_id}'.")
    return _to_response(row)


@router.patch("/{case_id}", response_model=AssetTrackerResponse)
async def update_hold(
    case_id: str, req: _UpdateRequest, db: Session = Depends(get_db)
) -> AssetTrackerResponse:
    """Update status and/or frozen_amount on an existing hold."""
    row = AssetTrackerService.update(
        db, case_id, status=req.status.value if req.status else None, frozen_amount=req.frozen_amount
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"No asset hold found for case_id '{case_id}'.")
    return _to_response(row)


@router.get("/{case_id}", response_model=AssetTrackerResponse)
async def get_hold(case_id: str, db: Session = Depends(get_db)) -> AssetTrackerResponse:
    """Return the current status of an asset hold."""
    row = AssetTrackerService.get(db, case_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No asset hold found for case_id '{case_id}'.")
    return _to_response(row)
