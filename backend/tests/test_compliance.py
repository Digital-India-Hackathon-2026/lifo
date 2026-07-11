"""Tests for /compliance/consent/* — DPDP consent + retention management."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.database as db_module
from app.core.database import Base
from app.main import app
from app.models.network_intel_db import DPDPConsent  # noqa: F401 — registers table on Base.metadata

client = TestClient(app)


# ── Fixture: isolate DB per test ───────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect the DB session factory to a temp SQLite file so tests don't share state."""
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'test_kavach.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=test_engine)
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(db_module, "SessionLocal", test_session_local)
    yield test_session_local


def _grant(user_id="user1", purpose="marketing", retention_days=None):
    body = {"user_id": user_id, "purpose": purpose}
    if retention_days is not None:
        body["retention_days"] = retention_days
    return client.post("/compliance/consent/grant", json=body)


def _revoke(user_id="user1", purpose="marketing"):
    return client.post("/compliance/consent/revoke", json={"user_id": user_id, "purpose": purpose})


def _status(user_id="user1", purpose="marketing"):
    return client.get("/compliance/consent/status", params={"user_id": user_id, "purpose": purpose})


def _expire_row(isolated_db, user_id="user1", purpose="marketing"):
    """Directly backdate a row's expires_at — the public API can't produce
    an already-expired grant (retention_days must be > 0)."""
    session = isolated_db()
    try:
        row = session.query(DPDPConsent).filter_by(user_id=user_id, purpose=purpose).first()
        row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        session.commit()
    finally:
        session.close()


# ── API: grant ─────────────────────────────────────────────────────────────────

def test_grant_creates_active_consent():
    resp = _grant()
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is True
    assert data["revoked"] is False
    assert data["user_id"] == "user1"
    assert data["purpose"] == "marketing"


def test_regrant_same_purpose_updates_not_duplicates(isolated_db):
    _grant()
    _grant()

    session = isolated_db()
    try:
        rows = session.query(DPDPConsent).filter_by(user_id="user1", purpose="marketing").all()
    finally:
        session.close()
    assert len(rows) == 1


# ── API: revoke ────────────────────────────────────────────────────────────────

def test_revoke_makes_consent_inactive():
    _grant()
    resp = _revoke()
    assert resp.status_code == 200
    data = resp.json()
    assert data["revoked"] is True
    assert data["active"] is False


def test_revoke_unknown_returns_404():
    resp = _revoke(user_id="ghost", purpose="ghost_purpose")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


# ── API: status ────────────────────────────────────────────────────────────────

def test_expired_but_not_purged_shows_inactive(isolated_db):
    _grant()
    _expire_row(isolated_db)

    resp = _status()
    assert resp.status_code == 200
    assert resp.json()["active"] is False

    session = isolated_db()
    try:
        # still present — status doesn't purge
        assert session.query(DPDPConsent).filter_by(user_id="user1", purpose="marketing").count() == 1
    finally:
        session.close()


def test_status_unknown_returns_404():
    resp = _status(user_id="ghost", purpose="ghost_purpose")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


# ── API: purge-expired ─────────────────────────────────────────────────────────

def test_purge_expired_removes_expired_leaves_active(isolated_db):
    _grant(purpose="expired_purpose")
    _grant(purpose="active_purpose")
    _expire_row(isolated_db, purpose="expired_purpose")

    resp = client.post("/compliance/consent/purge-expired")
    assert resp.status_code == 200
    assert resp.json()["purged_count"] == 1

    session = isolated_db()
    try:
        remaining = session.query(DPDPConsent).all()
    finally:
        session.close()
    assert len(remaining) == 1
    assert remaining[0].purpose == "active_purpose"


# ── API: input validation ─────────────────────────────────────────────────────

def test_grant_missing_fields_rejected_422():
    resp = client.post("/compliance/consent/grant", json={"user_id": "user1"})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── API: response shape / JSON contract ───────────────────────────────────────

def test_all_responses_are_json():
    resp = _grant()
    assert resp.headers["content-type"].startswith("application/json")
    resp.json()
