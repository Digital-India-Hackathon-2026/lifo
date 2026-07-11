"""Tests for /poc/moonshots/distributed-honeypot — moonshot PoC scaffold (item 87)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_distributed_honeypot_grid_returns_200_with_scaffold_values():
    resp = client.get("/poc/moonshots/distributed-honeypot")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_nodes"] == 42
    assert data["intercepted_payloads"] == 105


def test_note_field_present_and_non_empty():
    resp = client.get("/poc/moonshots/distributed-honeypot")
    note = resp.json()["note"]
    assert isinstance(note, str)
    assert len(note) > 0


def test_response_is_json():
    resp = client.get("/poc/moonshots/distributed-honeypot")
    assert resp.headers["content-type"].startswith("application/json")
    resp.json()
