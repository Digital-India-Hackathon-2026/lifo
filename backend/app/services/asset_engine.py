"""Asset-Recovery Status Tracker service (Track 3, item 68).

Built new — the Track 3 prototype's AssetEngine had only a read-only
`track_funds` query and no way to ever create or update a hold record; a
missing case_id silently returned a placeholder "NO_FUNDS_FROZEN" success
dict instead of a real not-found signal. Only the AssetRecoveryEntity field
names were salvaged; create/update/get and the not-found semantics are all
new here. See AGENTS.md Session 20 for the full gap analysis.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.network_intel_db import AssetRecoveryEntity


def _now_utc() -> datetime:
    # ponytail: SQLite's DateTime column silently drops tzinfo on round-trip
    # (a written aware datetime reads back naive) — storing and comparing
    # naive-UTC throughout avoids aware/naive comparison crashes. Same fix
    # as consent_service.py's _now_utc().
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AssetTrackerService:
    @classmethod
    def create_hold(
        cls, db: Session, case_id: str, frozen_amount: float, bank_node: str
    ) -> Optional[AssetRecoveryEntity]:
        """Create a new asset hold. Returns None if case_id already has a
        hold — the router turns that into 409: a second hold on the same
        case is a status/amount update (see .update()), not a new record."""
        existing = db.query(AssetRecoveryEntity).filter(AssetRecoveryEntity.case_id == case_id).first()
        if existing is not None:
            return None
        now = _now_utc()
        row = AssetRecoveryEntity(
            case_id=case_id,
            frozen_amount=frozen_amount,
            bank_node=bank_node,
            status="FROZEN",
            hold_timestamp_utc=now,
            last_updated_utc=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @classmethod
    def update(
        cls,
        db: Session,
        case_id: str,
        status: Optional[str] = None,
        frozen_amount: Optional[float] = None,
    ) -> Optional[AssetRecoveryEntity]:
        """Update whichever fields are given and bump last_updated_utc.
        Returns None if case_id doesn't exist — the router turns that into 404."""
        row = db.query(AssetRecoveryEntity).filter(AssetRecoveryEntity.case_id == case_id).first()
        if row is None:
            return None
        if status is not None:
            row.status = status
        if frozen_amount is not None:
            row.frozen_amount = frozen_amount
        row.last_updated_utc = _now_utc()
        db.commit()
        db.refresh(row)
        return row

    @classmethod
    def get(cls, db: Session, case_id: str) -> Optional[AssetRecoveryEntity]:
        """Return the row or None. The router turns None into 404 — no more
        silent "NO_FUNDS_FROZEN" placeholder masking a missing record."""
        return db.query(AssetRecoveryEntity).filter(AssetRecoveryEntity.case_id == case_id).first()
