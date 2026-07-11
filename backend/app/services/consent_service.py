"""Consent + retention service for DPDP compliance (Track 3, item 82).

Built new — the Track 3 prototype had no working granular-consent or
retention logic to port (its /consent endpoint ignored `purpose` entirely
and never touched the DB; see AGENTS.md Session 19 for the full gap
analysis). Purpose-scoped upsert, expiry-aware active check, and on-demand
hard-delete purge are all implemented here from scratch.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.network_intel_db import DPDPConsent

_DEFAULT_RETENTION_DAYS = 365


def _now_utc() -> datetime:
    # ponytail: SQLite's DateTime column silently drops tzinfo on round-trip
    # (a written aware datetime reads back naive) — storing and comparing
    # naive-UTC throughout avoids aware/naive comparison crashes.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ConsentService:
    @staticmethod
    def is_active(row: DPDPConsent) -> bool:
        """A row is active only if not revoked and not past its expiry —
        independent of whether it has actually been purged yet."""
        if row.revoked:
            return False
        if row.expires_at is not None and row.expires_at < _now_utc():
            return False
        return True

    @classmethod
    def grant(
        cls, db: Session, user_id: str, purpose: str, retention_days: Optional[int] = None
    ) -> DPDPConsent:
        """Grant (or re-grant) consent for a user_id+purpose pair.

        Upserts on the (user_id, purpose) unique constraint: re-granting an
        already-consented purpose updates the existing row's granted_at/
        expires_at/revoked in place rather than creating a duplicate.
        """
        days = retention_days if retention_days is not None else _DEFAULT_RETENTION_DAYS
        now = _now_utc()
        row = (
            db.query(DPDPConsent)
            .filter(DPDPConsent.user_id == user_id, DPDPConsent.purpose == purpose)
            .first()
        )
        if row is None:
            row = DPDPConsent(user_id=user_id, purpose=purpose)
            db.add(row)
        row.granted_at = now
        row.expires_at = now + timedelta(days=days)
        row.revoked = False
        db.commit()
        db.refresh(row)
        return row

    @classmethod
    def revoke(cls, db: Session, user_id: str, purpose: str) -> Optional[DPDPConsent]:
        """Mark an existing consent row as revoked. Returns None if no row
        exists for this (user_id, purpose) — the router turns that into 404."""
        row = (
            db.query(DPDPConsent)
            .filter(DPDPConsent.user_id == user_id, DPDPConsent.purpose == purpose)
            .first()
        )
        if row is None:
            return None
        row.revoked = True
        db.commit()
        db.refresh(row)
        return row

    @classmethod
    def get_status(cls, db: Session, user_id: str, purpose: str) -> Optional[DPDPConsent]:
        """Return the raw consent row. Callers must check is_active() — an
        expired or revoked row is reported as inactive here, not purged."""
        return (
            db.query(DPDPConsent)
            .filter(DPDPConsent.user_id == user_id, DPDPConsent.purpose == purpose)
            .first()
        )

    @classmethod
    def purge_expired(cls, db: Session) -> int:
        """Hard-delete every consent row whose expires_at has passed.

        This is an on-demand sweep, not a scheduled job — no task scheduler
        exists in this stack. Call this endpoint manually, or wire a cron
        trigger (e.g. Cloud Scheduler → this endpoint) later; see
        ARCHITECTURE.md Known Technical Debt.
        """
        now = _now_utc()
        expired = (
            db.query(DPDPConsent)
            .filter(DPDPConsent.expires_at.isnot(None), DPDPConsent.expires_at < now)
            .all()
        )
        count = len(expired)
        for row in expired:
            db.delete(row)
        db.commit()
        return count
