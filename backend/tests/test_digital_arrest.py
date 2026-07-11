"""Tests for /check/digital-arrest — pattern recognition over call transcripts."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.routers.digital_arrest import _analyze_transcript, _severity, _CALL_PATTERNS

client = TestClient(app)

_DA_TRANSCRIPT = (
    "Sir this is CBI officer, a case of money laundering has been registered against you. "
    "Your Aadhaar has been misused. You are under digital arrest. "
    "Do not tell anyone about this call — keep it confidential. "
    "You have to pay a verification fee. Pay now or we file the warrant. "
    "Transfer funds to this account or your assets will be frozen. "
    "Don't hang up. Stay on the line."
)

_CLEAN_TRANSCRIPT = (
    "Hi, I am calling to confirm your appointment tomorrow at 3pm. "
    "Please bring your ID card. See you then. Have a nice day."
)


# ── Unit: _analyze_transcript ────────────────────────────────────────────────

def test_da_transcript_hits_scam_patterns():
    scam, _ = _analyze_transcript(_DA_TRANSCRIPT)
    assert len(scam) >= 3


def test_da_transcript_hits_expected_labels():
    scam, payment = _analyze_transcript(_DA_TRANSCRIPT)
    assert "digital_arrest" in scam
    assert "money_laundering_claim" in scam
    assert "isolation_tactic" in scam or "secrecy_demand" in scam
    assert "stay_on_line" in scam
    assert "verification_payment" in payment or "immediate_payment" in payment


def test_da_transcript_hits_payment_patterns():
    _, payment = _analyze_transcript(_DA_TRANSCRIPT)
    assert len(payment) >= 1


def test_clean_transcript_no_hits():
    scam, payment = _analyze_transcript(_CLEAN_TRANSCRIPT)
    assert scam == []
    assert payment == []


def test_call_specific_stay_on_line():
    _, _ = _analyze_transcript("Don't hang up. I am an officer.")
    scam, _ = _analyze_transcript("Don't hang up. I am an officer.")
    assert "stay_on_line" in scam


def test_call_specific_surveillance_claim():
    scam, _ = _analyze_transcript("We are tracking your phone right now.")
    assert "surveillance_claim" in scam


def test_call_specific_immediate_warrant():
    scam, _ = _analyze_transcript(
        "A warrant is being issued right now. You have only 10 minutes to comply."
    )
    assert "immediate_warrant_pressure" in scam


def test_patterns_deduplicated():
    """Same label should appear at most once even if multiple phrases match."""
    text = "Don't hang up. Stay on the line. Don't disconnect."
    scam, _ = _analyze_transcript(text)
    assert scam.count("stay_on_line") == 1


# ── Unit: _severity ──────────────────────────────────────────────────────────

def test_severity_high_when_both():
    assert _severity(["digital_arrest"], ["verification_payment"]) == "high"


def test_severity_medium_scam_only():
    assert _severity(["digital_arrest"], []) == "medium"


def test_severity_medium_payment_only():
    assert _severity([], ["immediate_payment"]) == "medium"


def test_severity_low_neither():
    assert _severity([], []) == "low"


# ── API: known DA transcript → high severity ─────────────────────────────────

def test_api_da_transcript_high_severity():
    resp = client.post("/check/digital-arrest", json={"transcript": _DA_TRANSCRIPT})
    assert resp.status_code == 200
    data = resp.json()
    assert data["severity"] == "high"
    assert len(data["matched_patterns"]) >= 3
    assert len(data["payment_indicators_found"]) >= 1
    assert "hard_factual_anchor" in data
    assert "video call" in data["hard_factual_anchor"].lower() or "video" in data["hard_factual_anchor"].lower()
    assert "disclaimer" in data


def test_api_clean_transcript_low_severity():
    resp = client.post("/check/digital-arrest", json={"transcript": _CLEAN_TRANSCRIPT})
    assert resp.status_code == 200
    data = resp.json()
    assert data["severity"] == "low"
    assert data["matched_patterns"] == []
    assert data["payment_indicators_found"] == []


def test_api_hard_factual_anchor_always_present():
    """Anchor must appear in every response, regardless of severity."""
    for transcript in [_DA_TRANSCRIPT, _CLEAN_TRANSCRIPT]:
        resp = client.post("/check/digital-arrest", json={"transcript": transcript})
        assert resp.status_code == 200
        assert resp.json()["hard_factual_anchor"]  # non-empty


def test_api_anchor_text_matches_document_anchor():
    """Anchor text must be identical to document.py — no rewording."""
    from app.routers.document import _ANCHOR
    resp = client.post("/check/digital-arrest", json={"transcript": _DA_TRANSCRIPT})
    assert resp.json()["hard_factual_anchor"] == _ANCHOR.strip()


# ── API: session_id lookup path ───────────────────────────────────────────────

def test_api_session_id_pulls_transcript():
    fake_session = {
        "test-session-abc": {
            "turns": [
                {"transcript": "Your account will be frozen immediately."},
                {"transcript": "Pay verification fee or face digital arrest."},
                {"transcript": None},  # failed STT turn — must be skipped
            ],
            "cumulative_intel": {},
        }
    }
    with patch("app.routers.digital_arrest._resolve_transcript") as mock_resolve:
        combined = "Your account will be frozen immediately. Pay verification fee or face digital arrest."
        mock_resolve.return_value = combined
        resp = client.post("/check/digital-arrest", json={"session_id": "test-session-abc"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["severity"] in ("medium", "high")


def test_api_session_id_real_lookup():
    """Direct integration: inject a session into the honeypot store and pull via session_id."""
    import app.routers.honeypot as honeypot_mod

    sid = "test-da-integration-001"
    honeypot_mod._sessions[sid] = {
        "turns": [
            {"transcript": "Digital arrest case registered against you."},
            {"transcript": "Pay verification fee now. Don't hang up."},
            {"transcript": None},
        ],
        "cumulative_intel": {},
    }
    try:
        resp = client.post("/check/digital-arrest", json={"session_id": sid})
        assert resp.status_code == 200
        data = resp.json()
        assert "digital_arrest" in data["matched_patterns"]
        assert "stay_on_line" in data["matched_patterns"]
    finally:
        honeypot_mod._sessions.pop(sid, None)


def test_api_unknown_session_id_404():
    resp = client.post("/check/digital-arrest", json={"session_id": "nonexistent-uuid-xyz"})
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


# ── API: input validation ─────────────────────────────────────────────────────

def test_api_empty_transcript_400():
    resp = client.post("/check/digital-arrest", json={"transcript": ""})
    assert resp.status_code == 400
    assert resp.headers["content-type"].startswith("application/json")


def test_api_whitespace_only_transcript_400():
    resp = client.post("/check/digital-arrest", json={"transcript": "   \n\t  "})
    assert resp.status_code == 400


def test_api_transcript_exceeds_max_length_422():
    long_text = "a " * 6000  # 12000 chars > 10000 limit
    resp = client.post("/check/digital-arrest", json={"transcript": long_text})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


def test_api_neither_field_provided_422():
    resp = client.post("/check/digital-arrest", json={})
    assert resp.status_code == 422


def test_api_response_json_always():
    """Global exception handler guarantee — every response is JSON."""
    resp = client.post("/check/digital-arrest", json={"transcript": ""})
    assert resp.headers["content-type"].startswith("application/json")
    resp.json()  # must parse without error
