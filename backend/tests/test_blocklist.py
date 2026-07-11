"""Tests for /blocklist/report and /blocklist/check — Federated Privacy-Preserving Blocklist."""
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.database as db_module
from app.core.database import Base
from app.main import app
from app.models.network_intel_db import PrivacyPreservingBlocklist  # noqa: F401 — registers table on Base.metadata

client = TestClient(app)

_INDICATOR = "cbi-verify.gov.in.secure-portal.com"


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


def _report(indicator=_INDICATOR, taxonomy="PHISHING_URL"):
    return client.post("/blocklist/report", json={"indicator": indicator, "taxonomy": taxonomy})


def _check(indicator=_INDICATOR):
    return client.get("/blocklist/check", params={"indicator": indicator})


# ── API: ingest ────────────────────────────────────────────────────────────────

def test_ingest_new_indicator_returns_secured():
    resp = _report()
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SECURED"
    assert data["taxonomy"] == "PHISHING_URL"
    assert data["hash_signature"] == hashlib.sha256(_INDICATOR.encode()).hexdigest()
    assert data["reason"] is None


def test_repeat_ingest_returns_rejected():
    first = _report().json()
    second = _report().json()
    assert first["status"] == "SECURED"
    assert second["status"] == "REJECTED"
    assert second["hash_signature"] is None
    assert second["taxonomy"] is None
    assert second["reason"] is not None


# ── API: scan ──────────────────────────────────────────────────────────────────

def test_scan_of_ingested_indicator_detects_threat():
    _report()
    resp = _check()
    assert resp.status_code == 200
    data = resp.json()
    assert data["threat_detected"] is True
    assert data["action"] == "INTERCEPT_AND_LOG"
    assert data["hash"] == hashlib.sha256(_INDICATOR.encode()).hexdigest()


def test_scan_of_unknown_indicator_no_threat():
    resp = _check(indicator="totally-clean-domain.com")
    assert resp.status_code == 200
    data = resp.json()
    assert data["threat_detected"] is False
    assert data["action"] == "ALLOW"


# ── Security regression: raw indicator never stored ───────────────────────────

def test_raw_indicator_never_stored(isolated_db):
    _report(indicator=_INDICATOR)

    session = isolated_db()
    try:
        rows = session.query(PrivacyPreservingBlocklist).all()
    finally:
        session.close()

    assert len(rows) == 1
    stored_hashes = {row.sha256_hash for row in rows}
    assert _INDICATOR not in stored_hashes
    assert hashlib.sha256(_INDICATOR.encode()).hexdigest() in stored_hashes


# ── API: input validation ─────────────────────────────────────────────────────

def test_invalid_taxonomy_rejected_422():
    resp = _report(taxonomy="NOT_A_REAL_TAXONOMY")
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── API: response shape / JSON contract ───────────────────────────────────────

def test_all_responses_are_json():
    resp = _report()
    assert resp.headers["content-type"].startswith("application/json")
    resp.json()

    resp2 = _check()
    assert resp2.headers["content-type"].startswith("application/json")
    resp2.json()


# ── Chakshu/Sanchar Saathi feeder (item 60) ───────────────────────────────────

def test_chakshu_report_tags_voice_spoof_and_hashes_number(isolated_db):
    phone = "+919876543210"
    resp = client.post("/blocklist/chakshu-report", json={"raw_phone_number": phone})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SECURED"
    assert data["taxonomy"] == "VOICE_SPOOF"
    assert data["hash_signature"] == hashlib.sha256(phone.encode()).hexdigest()

    session = isolated_db()
    try:
        stored_values = {row.sha256_hash for row in session.query(PrivacyPreservingBlocklist).all()}
    finally:
        session.close()
    assert phone not in stored_values
    assert hashlib.sha256(phone.encode()).hexdigest() in stored_values
