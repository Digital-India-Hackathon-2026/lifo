"""Tests for /legal/dispute/* — Bank Dispute + Ombudsman Auto-Escalation (item 64)."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.database as db_module
from app.core.database import Base
from app.main import app
from app.models.legal_db import DisputeCase  # noqa: F401 — registers table on Base.metadata

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


def _track(user_id="user1", bank_name="HDFC Bank", transaction_reference="UTR123456789", **extra):
    body = {"user_id": user_id, "bank_name": bank_name, "transaction_reference": transaction_reference}
    body.update(extra)
    return client.post("/legal/dispute/track", json=body)


def _bank_response(case_id, response_text="We are investigating the transaction."):
    return client.post(f"/legal/dispute/{case_id}/bank-response", json={"response_text": response_text})


def _status(case_id):
    return client.get(f"/legal/dispute/{case_id}/status")


def _escalate(case_id):
    return client.post(f"/legal/dispute/{case_id}/escalate")


def _make_overdue(isolated_db, case_id):
    """Directly backdate a row's rbi_deadline_at — the public API can't produce
    an already-overdue case (the RBI window is a fixed 90 days from creation).
    Same technique test_compliance.py uses for expires_at."""
    session = isolated_db()
    try:
        row = session.query(DisputeCase).filter_by(case_id=case_id).first()
        row.rbi_deadline_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        session.commit()
    finally:
        session.close()


# ── API: track dispute ──────────────────────────────────────────────────────────

def test_track_dispute_creates_case_with_90_day_deadline():
    resp = _track()
    assert resp.status_code == 201
    data = resp.json()
    assert data["case_id"].startswith("DISP-")
    assert data["user_id"] == "user1"
    assert data["bank_name"] == "HDFC Bank"
    assert data["transaction_reference"] == "UTR123456789"
    assert data["status"] == "open"
    assert "RBI/2017-18/15" in data["dispute_text"]
    assert "Dear Sir / Madam" in data["dispute_text"]

    raised = datetime.fromisoformat(data["dispute_raised_at"])
    deadline = datetime.fromisoformat(data["rbi_deadline_at"])
    assert (deadline - raised).days == 90


def test_track_dispute_missing_field_422():
    resp = client.post("/legal/dispute/track", json={"user_id": "user1", "bank_name": "HDFC Bank"})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── API: log bank response ───────────────────────────────────────────────────────

def test_bank_response_before_deadline_updates_status_not_overdue():
    case_id = _track().json()["case_id"]
    resp = _bank_response(case_id, "We have credited the disputed amount.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "bank_responded"
    assert data["bank_response"] == "We have credited the disputed amount."
    assert data["is_overdue"] is False


def test_bank_response_unknown_case_id_404():
    resp = _bank_response("DISP-DOESNOTEXIST")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


def test_bank_response_missing_field_422():
    case_id = _track().json()["case_id"]
    resp = client.post(f"/legal/dispute/{case_id}/bank-response", json={})
    assert resp.status_code == 422


# ── API: status + is_overdue ──────────────────────────────────────────────────────

def test_status_fresh_case_is_not_overdue():
    case_id = _track().json()["case_id"]
    resp = _status(case_id)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "open"
    assert data["is_overdue"] is False
    assert "no background scheduler" in data["note"].lower()


def test_status_unknown_case_id_404():
    resp = _status("DISP-DOESNOTEXIST")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


def test_status_overdue_open_case_is_overdue(isolated_db):
    case_id = _track().json()["case_id"]
    _make_overdue(isolated_db, case_id)
    resp = _status(case_id)
    assert resp.status_code == 200
    assert resp.json()["is_overdue"] is True


def test_status_overdue_but_bank_responded_is_not_overdue(isolated_db):
    """is_overdue only applies while status is still 'open' — a case the bank
    already responded to isn't hanging, even past its original deadline."""
    case_id = _track().json()["case_id"]
    _bank_response(case_id)
    _make_overdue(isolated_db, case_id)
    resp = _status(case_id)
    assert resp.status_code == 200
    assert resp.json()["is_overdue"] is False


# ── API: escalate ──────────────────────────────────────────────────────────────

def test_escalate_before_deadline_returns_409():
    case_id = _track().json()["case_id"]
    resp = _escalate(case_id)
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("application/json")


def test_escalate_after_deadline_succeeds(isolated_db):
    case_id = _track().json()["case_id"]
    _make_overdue(isolated_db, case_id)
    resp = _escalate(case_id)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "escalated"
    assert "ombudsman" in data["escalation_text"].lower()
    assert "cms.rbi.org.in" in data["escalation_text"]
    assert case_id in data["escalation_text"]

    # Status now reflects escalated, no longer counted as an open overdue case.
    status_resp = _status(case_id)
    assert status_resp.json()["status"] == "escalated"
    assert status_resp.json()["is_overdue"] is False


def test_escalate_unknown_case_id_404():
    resp = _escalate("DISP-DOESNOTEXIST")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


def test_escalate_twice_second_call_409(isolated_db):
    """Once escalated, status is no longer 'open', so is_overdue is false again —
    a second escalate attempt correctly 409s rather than re-escalating."""
    case_id = _track().json()["case_id"]
    _make_overdue(isolated_db, case_id)
    first = _escalate(case_id)
    assert first.status_code == 200

    second = _escalate(case_id)
    assert second.status_code == 409
    assert second.headers["content-type"].startswith("application/json")
