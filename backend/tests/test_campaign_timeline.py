"""Tests for Track 1 item 30: Scam Campaign Timeline.

Genuinely new work — no reference repo to check against (Track 1's
collaborator repo claimed "Redis-backed session stitching" for this
item, but the audit confirmed zero actual code behind that claim).
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.database as db_module
from app.core.database import Base
from app.main import app

client = TestClient(app)


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


def _create_case(user_id="user1", title="Fake CBI call + UPI demand"):
    return client.post("/timeline/cases", json={"user_id": user_id, "title": title})


def _add_event(case_id, event_type="call", description="Scammer called claiming to be CBI", event_timestamp="2026-06-01T10:00:00", artifact_id=None):
    payload = {"event_type": event_type, "description": description, "event_timestamp": event_timestamp}
    if artifact_id is not None:
        payload["artifact_id"] = artifact_id
    return client.post(f"/timeline/cases/{case_id}/events", json=payload)


# ── Case creation ──────────────────────────────────────────────────────────────

def test_create_case_returns_case_id_and_empty_events():
    resp = _create_case()
    assert resp.status_code == 201
    data = resp.json()
    assert data["case_id"].startswith("CASE-")
    assert data["user_id"] == "user1"
    assert data["title"] == "Fake CBI call + UPI demand"
    assert data["status"] == "open"
    assert data["events"] == []


def test_create_case_missing_field_422():
    resp = client.post("/timeline/cases", json={"user_id": "user1"})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Adding events ──────────────────────────────────────────────────────────────

def test_add_event_to_existing_case():
    case_id = _create_case().json()["case_id"]
    resp = _add_event(case_id, event_type="whatsapp", description="Message with fake CBI notice PDF", artifact_id="doc-check-123")
    assert resp.status_code == 201
    data = resp.json()
    assert data["event_type"] == "whatsapp"
    assert data["description"] == "Message with fake CBI notice PDF"
    assert data["artifact_id"] == "doc-check-123"


def test_add_event_without_artifact_id_is_null():
    case_id = _create_case().json()["case_id"]
    resp = _add_event(case_id)
    assert resp.status_code == 201
    assert resp.json()["artifact_id"] is None


def test_add_event_unknown_case_404():
    resp = _add_event("CASE-DOESNOTEXIST")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


def test_add_event_invalid_event_type_422():
    case_id = _create_case().json()["case_id"]
    resp = _add_event(case_id, event_type="sms")
    assert resp.status_code == 422


def test_add_event_missing_timestamp_422():
    case_id = _create_case().json()["case_id"]
    resp = client.post(
        f"/timeline/cases/{case_id}/events",
        json={"event_type": "call", "description": "Scammer called"},
    )
    assert resp.status_code == 422


# ── Chronological ordering ──────────────────────────────────────────────────────

def test_events_returned_in_chronological_not_insertion_order():
    case_id = _create_case().json()["case_id"]
    # Insert deliberately out of chronological order.
    _add_event(case_id, event_type="upi", description="Paid via UPI collect request", event_timestamp="2026-06-03T09:00:00")
    _add_event(case_id, event_type="call", description="First scam call", event_timestamp="2026-06-01T10:00:00")
    _add_event(case_id, event_type="whatsapp", description="Follow-up WhatsApp message", event_timestamp="2026-06-02T15:00:00")

    resp = client.get(f"/timeline/cases/{case_id}")
    assert resp.status_code == 200
    events = resp.json()["events"]
    assert [e["event_type"] for e in events] == ["call", "whatsapp", "upi"]
    assert events[0]["event_timestamp"] < events[1]["event_timestamp"] < events[2]["event_timestamp"]


def test_aware_timestamp_converted_to_utc_correctly():
    """+05:30 (IST) 10:00 must store/return as 04:30 UTC, not a naive-stripped 10:00."""
    case_id = _create_case().json()["case_id"]
    resp = _add_event(case_id, event_timestamp="2026-06-01T10:00:00+05:30")
    assert resp.status_code == 201
    returned = datetime.fromisoformat(resp.json()["event_timestamp"])
    assert returned.hour == 4
    assert returned.minute == 30


# ── Retrieval ─────────────────────────────────────────────────────────────────

def test_get_case_unknown_404():
    resp = client.get("/timeline/cases/CASE-DOESNOTEXIST")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


def test_list_user_cases_returns_multiple_and_excludes_other_users():
    _create_case(user_id="userA", title="Case A1")
    _create_case(user_id="userA", title="Case A2")
    _create_case(user_id="userB", title="Case B1")

    resp = client.get("/timeline/cases", params={"user_id": "userA"})
    assert resp.status_code == 200
    cases = resp.json()["cases"]
    assert len(cases) == 2
    assert {c["title"] for c in cases} == {"Case A1", "Case A2"}


def test_list_cases_missing_user_id_422():
    resp = client.get("/timeline/cases")
    assert resp.status_code == 422
