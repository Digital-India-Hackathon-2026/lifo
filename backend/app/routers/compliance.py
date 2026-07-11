"""
/compliance/consent — DPDP-compliant consent + retention management (Track 3, item 82).

Built new — the Track 3 prototype's compliance.py had no working granular
consent logic to port (its single /consent endpoint ignored `purpose`
entirely and never touched the database). Purpose-scoped consent,
upsert-by-(user_id, purpose), retention-based expiry, and on-demand
hard-delete purge are all new here; see AGENTS.md for the full gap analysis.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import Base, engine, get_db
from app.models.network_intel_db import DPDPConsent  # noqa: F401 — registers table on Base.metadata
from app.models.responses import ConsentResponse, PurgeResponse
from app.services.consent_service import ConsentService

router = APIRouter(prefix="/compliance/consent", tags=["compliance"])


class _GrantRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)
    retention_days: Optional[int] = Field(None, gt=0)


class _RevokeRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)


def init_db() -> None:
    """Called at startup. Creates the consent table if it doesn't exist yet."""
    Base.metadata.create_all(bind=engine)


def _to_response(row: DPDPConsent) -> ConsentResponse:
    return ConsentResponse(
        user_id=row.user_id,
        purpose=row.purpose,
        granted_at=row.granted_at,
        expires_at=row.expires_at,
        revoked=row.revoked,
        active=ConsentService.is_active(row),
    )


@router.post("/grant", response_model=ConsentResponse)
async def grant_consent(req: _GrantRequest, db: Session = Depends(get_db)) -> ConsentResponse:
    """Grant (or re-grant) consent for a purpose. Re-granting an existing
    (user_id, purpose) updates the row in place — never duplicates."""
    row = ConsentService.grant(db, req.user_id, req.purpose, req.retention_days)
    return _to_response(row)


@router.post("/revoke", response_model=ConsentResponse)
async def revoke_consent(req: _RevokeRequest, db: Session = Depends(get_db)) -> ConsentResponse:
    """Revoke an existing consent grant."""
    row = ConsentService.revoke(db, req.user_id, req.purpose)
    if row is None:
        raise HTTPException(status_code=404, detail="No consent record found for this user_id/purpose.")
    return _to_response(row)


@router.get("/status", response_model=ConsentResponse)
async def consent_status(
    user_id: str = Query(..., min_length=1),
    purpose: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> ConsentResponse:
    """Return current consent status. `active` is false if revoked or expired,
    even if the row hasn't been purged yet — purge is a separate on-demand step."""
    row = ConsentService.get_status(db, user_id, purpose)
    if row is None:
        raise HTTPException(status_code=404, detail="No consent record found for this user_id/purpose.")
    return _to_response(row)


@router.post("/purge-expired", response_model=PurgeResponse)
async def purge_expired(db: Session = Depends(get_db)) -> PurgeResponse:
    """Hard-delete all consent rows past their expires_at. On-demand sweep —
    no scheduler exists in this stack; call this manually or wire a cron later."""
    count = ConsentService.purge_expired(db)
    return PurgeResponse(purged_count=count)
