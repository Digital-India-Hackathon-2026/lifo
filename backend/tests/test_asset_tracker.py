"""Tests for /legal/asset-tracker/* — Asset-Recovery Status Tracker."""
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.database as db_module
from app.core.database import Base
from app.main import app
from app.models.network_intel_db import AssetRecoveryEntity  # noqa: F401 — registers table on Base.metadata

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


def _create(case_id="CASE001", frozen_amount=50000.0, bank_node="SBI-DELHI"):
    return client.post(
        "/legal/asset-tracker/hold",
        json={"case_id": case_id, "frozen_amount": frozen_amount, "bank_node": bank_node},
    )


def _update(case_id="CASE001", **fields):
    return client.patch(f"/legal/asset-tracker/{case_id}", json=fields)


def _get(case_id="CASE001"):
    return client.get(f"/legal/asset-tracker/{case_id}")


# ── API: create hold ───────────────────────────────────────────────────────────

def test_create_hold_returns_frozen():
    resp = _create()
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "FROZEN"
    assert data["case_id"] == "CASE001"
    assert data["frozen_amount"] == 50000.0
    assert data["bank_node"] == "SBI-DELHI"
    assert data["hold_timestamp_utc"] == data["last_updated_utc"]


def test_duplicate_create_returns_409():
    _create()
    resp = _create()
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("application/json")


# ── API: update hold ─────────────────────────────────────────────────────────

def test_update_status_reflects_and_bumps_last_updated():
    created = _create().json()
    time.sleep(0.01)  # guarantee a distinguishable last_updated_utc
    resp = _update(status="UNDER_INVESTIGATION")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "UNDER_INVESTIGATION"
    assert data["hold_timestamp_utc"] == created["hold_timestamp_utc"]
    assert data["last_updated_utc"] > created["last_updated_utc"]


def test_update_unknown_case_id_returns_404():
    resp = _update(case_id="GHOST", status="RELEASED")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


# ── API: get hold ─────────────────────────────────────────────────────────────

def test_get_existing_returns_correct_fields():
    _create()
    resp = _get()
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == "CASE001"
    assert data["status"] == "FROZEN"
    assert data["frozen_amount"] == 50000.0
    assert data["bank_node"] == "SBI-DELHI"


def test_get_unknown_returns_404():
    resp = _get(case_id="GHOST")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


# ── API: input validation ─────────────────────────────────────────────────────

def test_invalid_status_value_rejected_422():
    _create()
    resp = _update(status="NOT_A_REAL_STATUS")
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── API: response shape / JSON contract ───────────────────────────────────────

def test_all_responses_are_json():
    resp = _create()
    assert resp.headers["content-type"].startswith("application/json")
    resp.json()
