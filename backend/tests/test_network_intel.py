"""Tests for /network-intel/link — Campaign Graph entity linking."""
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.database as db_module
from app.core.database import Base
from app.main import app
from app.models.network_intel_db import ScamEntity  # noqa: F401 — registers tables on Base.metadata

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


def _link(source="+919876543210", target="scammer@upi", taxonomy="PHISHING_URL", relation_type="used_by"):
    return client.post(
        "/network-intel/link",
        json={"source": source, "target": target, "taxonomy": taxonomy, "relation_type": relation_type},
    )


# ── API: valid link ─────────────────────────────────────────────────────────────

def test_valid_link_returns_200():
    resp = _link()
    assert resp.status_code == 200
    data = resp.json()
    assert data["edge_status"] == "CREATED"
    assert data["taxonomy"] == "PHISHING_URL"
    assert isinstance(data["source_node_id"], int)
    assert isinstance(data["target_node_id"], int)


# ── API: dedup on repeat calls ────────────────────────────────────────────────

def test_repeat_call_dedups_edge():
    first = _link().json()
    second = _link().json()
    assert first["edge_status"] == "CREATED"
    assert second["edge_status"] == "EXISTS"
    assert first["source_node_id"] == second["source_node_id"]
    assert first["target_node_id"] == second["target_node_id"]


def test_different_relation_type_creates_new_edge():
    first = _link(relation_type="used_by").json()
    second = _link(relation_type="linked_to").json()
    assert first["edge_status"] == "CREATED"
    assert second["edge_status"] == "CREATED"


# ── Security regression: raw source/target never stored ──────────────────────

def test_raw_source_and_target_never_stored(isolated_db):
    source, target = "+919876543210", "scammer@upi"
    _link(source=source, target=target)

    session = isolated_db()
    try:
        rows = session.query(ScamEntity).all()
    finally:
        session.close()

    assert len(rows) == 2
    stored_values = {row.entity_value for row in rows}
    assert source not in stored_values
    assert target not in stored_values
    assert hashlib.sha256(source.encode()).hexdigest() in stored_values
    assert hashlib.sha256(target.encode()).hexdigest() in stored_values


# ── API: input validation ─────────────────────────────────────────────────────

def test_invalid_taxonomy_rejected_422():
    resp = _link(taxonomy="NOT_A_REAL_TAXONOMY")
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


def test_missing_field_rejected_422():
    resp = client.post("/network-intel/link", json={"source": "a", "target": "b"})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── API: response shape / JSON contract ───────────────────────────────────────

def test_all_responses_are_json():
    resp = _link()
    assert resp.headers["content-type"].startswith("application/json")
    resp.json()  # must parse without error


# ── NPCI MuleHunter feeder (item 62) ───────────────────────────────────────────

def test_mulehunter_feed_tags_mule_account_and_hashes_accounts(isolated_db):
    source, target = "ACC1234567890", "ACC0987654321"
    resp = client.post(
        "/network-intel/mulehunter-feed",
        json={"source_account": source, "target_account": target},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["taxonomy"] == "MULE_ACCOUNT"
    assert data["edge_status"] == "CREATED"

    session = isolated_db()
    try:
        stored_values = {row.entity_value for row in session.query(ScamEntity).all()}
    finally:
        session.close()
    assert source not in stored_values
    assert target not in stored_values
    assert hashlib.sha256(source.encode()).hexdigest() in stored_values
    assert hashlib.sha256(target.encode()).hexdigest() in stored_values
