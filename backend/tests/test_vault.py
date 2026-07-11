"""Tests for /vault/set and /vault/verify — Family Safe-Word Vault."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.vault import _hash_word, _load, _save

client = TestClient(app)


# ── Fixture: isolate vault file per test ──────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    """Redirect vault file to a temp directory so tests don't share state."""
    vault_file = tmp_path / "vault.json"
    monkeypatch.setattr("app.routers.vault._VAULT_FILE", vault_file)
    return vault_file


# ── Unit: hash helpers ────────────────────────────────────────────────────────

def test_hash_is_deterministic_with_same_salt():
    import os
    salt = os.urandom(16)
    assert _hash_word("sunshine", salt) == _hash_word("sunshine", salt)


def test_hash_differs_for_different_words():
    import os
    salt = os.urandom(16)
    assert _hash_word("sunshine", salt) != _hash_word("moonlight", salt)


def test_hash_differs_for_different_salts():
    import os
    h1 = _hash_word("sunshine", os.urandom(16))
    h2 = _hash_word("sunshine", os.urandom(16))
    assert h1 != h2


def test_save_and_load_roundtrip(isolated_vault):
    _save("deadbeef", "cafebabe")
    data = _load()
    assert data is not None
    assert data["salt"] == "deadbeef"
    assert data["hash"] == "cafebabe"


def test_load_returns_none_when_file_missing(isolated_vault):
    assert not isolated_vault.exists()
    assert _load() is None


# ── API: set then verify correct word ─────────────────────────────────────────

def test_set_then_verify_correct_word():
    set_resp = client.post("/vault/set", json={"safe_word": "BlueMango99"})
    assert set_resp.status_code == 200

    verify_resp = client.post("/vault/verify", json={"safe_word": "BlueMango99"})
    assert verify_resp.status_code == 200
    assert verify_resp.json()["matches"] is True


# ── API: set then verify wrong word ───────────────────────────────────────────

def test_set_then_verify_wrong_word():
    client.post("/vault/set", json={"safe_word": "BlueMango99"})
    verify_resp = client.post("/vault/verify", json={"safe_word": "WrongWord"})
    assert verify_resp.status_code == 200
    assert verify_resp.json()["matches"] is False


# ── API: verify before any word is set ───────────────────────────────────────

def test_verify_before_set_returns_409():
    resp = client.post("/vault/verify", json={"safe_word": "anything"})
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("application/json")
    data = resp.json()
    # Must include a clear error message — not a crash, not a silent false
    assert "error" in data or "detail" in data


# ── API: set overwrites existing word ────────────────────────────────────────

def test_set_overwrites_existing():
    client.post("/vault/set", json={"safe_word": "FirstWord"})
    client.post("/vault/set", json={"safe_word": "SecondWord"})

    assert client.post("/vault/verify", json={"safe_word": "SecondWord"}).json()["matches"] is True
    assert client.post("/vault/verify", json={"safe_word": "FirstWord"}).json()["matches"] is False


# ── API: input validation ─────────────────────────────────────────────────────

def test_empty_safe_word_rejected_422():
    resp = client.post("/vault/set", json={"safe_word": ""})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


def test_whitespace_only_safe_word_rejected_422():
    resp = client.post("/vault/set", json={"safe_word": "   "})
    assert resp.status_code == 422


def test_too_short_safe_word_rejected_422():
    resp = client.post("/vault/set", json={"safe_word": "ab"})
    assert resp.status_code == 422


def test_missing_safe_word_field_422():
    resp = client.post("/vault/set", json={})
    assert resp.status_code == 422


def test_verify_empty_safe_word_rejected_422():
    resp = client.post("/vault/verify", json={"safe_word": ""})
    assert resp.status_code == 422


# ── Security regression: raw word / hash never in any response ───────────────

def test_set_response_does_not_echo_word():
    resp = client.post("/vault/set", json={"safe_word": "SecretSunshine"})
    assert resp.status_code == 200
    body = json.dumps(resp.json())
    assert "SecretSunshine" not in body


def test_verify_response_does_not_echo_word():
    client.post("/vault/set", json={"safe_word": "SecretSunshine"})
    resp = client.post("/vault/verify", json={"safe_word": "SecretSunshine"})
    assert resp.status_code == 200
    body = json.dumps(resp.json())
    assert "SecretSunshine" not in body


def test_verify_response_does_not_contain_hash(isolated_vault):
    client.post("/vault/set", json={"safe_word": "SecretSunshine"})
    stored_hash = json.loads(isolated_vault.read_text())["hash"]
    resp = client.post("/vault/verify", json={"safe_word": "SecretSunshine"})
    body = json.dumps(resp.json())
    assert stored_hash not in body


def test_set_response_does_not_contain_hash(isolated_vault):
    resp = client.post("/vault/set", json={"safe_word": "SecretSunshine"})
    stored_hash = json.loads(isolated_vault.read_text())["hash"]
    body = json.dumps(resp.json())
    assert stored_hash not in body


# ── API: response shape ───────────────────────────────────────────────────────

def test_set_response_shape():
    resp = client.post("/vault/set", json={"safe_word": "sunshine123"})
    data = resp.json()
    assert "message" in data
    assert "note" in data


def test_verify_response_shape():
    client.post("/vault/set", json={"safe_word": "sunshine123"})
    resp = client.post("/vault/verify", json={"safe_word": "sunshine123"})
    data = resp.json()
    assert "matches" in data
    assert "note" in data
    assert "disclaimer" in data


def test_all_responses_are_json():
    for path, body in [
        ("/vault/set", {"safe_word": "testword"}),
        ("/vault/verify", {"safe_word": "testword"}),
    ]:
        resp = client.post(path, json=body)
        assert resp.headers["content-type"].startswith("application/json")
        resp.json()  # must parse without error
