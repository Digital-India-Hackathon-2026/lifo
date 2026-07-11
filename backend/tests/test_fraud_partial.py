"""Tests for /scams/{job,loan,sextortion}/check — Track 1 items 3/7/9.

Unlike the pure-port batches, these 3 add a real capability the reference
lacked. Each item's tests cover the base phrase-detection path AND prove
the new capability actually changes the outcome, not just that it responds.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _post(path: str, **body):
    return client.post(path, json=body)


# ── Job / WFH scam (item 3) — base phrase detection ───────────────────────────

def test_job_base_high_risk_all_three_phrases():
    resp = _post(
        "/scams/job/check",
        transcript="Pay a registration fee to start. Earn ₹5000 per day liking videos, no experience needed — join our Telegram group for tasks.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) == 3
    assert "mca_check_note" in data and len(data["mca_check_note"]) > 0


def test_job_clean_text():
    resp = _post("/scams/job/check", transcript="Excited to start my new role next Monday, the onboarding email looks normal.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_job_empty_body_422():
    resp = client.post("/scams/job/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Job / WFH scam (item 3) — MCA-proxy escalation capability ────────────────

def test_job_mca_proxy_escalates_unknown_employer():
    # Single phrase signal alone would be low/0.40 — the unallowlisted company
    # mention must independently escalate it to medium.
    resp = _post(
        "/scams/job/check",
        transcript="We are hiring on behalf of Zentro Nexus Pvt Ltd — pay a refundable deposit to receive your starter kit.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "medium"
    assert data["confidence_score"] == 0.75
    assert any("Zentro Nexus" in f for f in data["flags"])


def test_job_mca_proxy_does_not_escalate_known_employer():
    resp = _post(
        "/scams/job/check",
        transcript="We are hiring on behalf of Infosys — pay a refundable deposit to receive your starter kit.",
    )
    assert resp.status_code == 200
    data = resp.json()
    # Base single-phrase-signal result, unescalated — allowlisted employer, no MCA flag.
    assert data["risk_level"] == "low"
    assert data["confidence_score"] == 0.40
    assert not any("does not" in f or "known-legitimate" in f for f in data["flags"])


# ── Loan app scam (item 7) — base phrase detection ────────────────────────────

def test_loan_base_high_risk_two_phrases():
    resp = _post(
        "/scams/loan/check",
        transcript="This app needs access to contacts and photo gallery, and will contact your family if you don't repay.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_loan_clean_text():
    resp = _post("/scams/loan/check", transcript="My personal loan EMI was auto-debited successfully this month.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []
    assert data["app_registry_status"] == "not_mentioned"


def test_loan_empty_body_422():
    resp = client.post("/scams/loan/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Loan app scam (item 7) — RBI registry cross-check capability ─────────────

def test_loan_unregistered_app_escalates_with_phrase_signal():
    # Single phrase signal alone would be medium/0.65 — the unregistered app
    # name must independently escalate it to high.
    resp = _post(
        "/scams/loan/check",
        transcript="This is a 7-day loan tenure using the QuickPaisa app.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert data["confidence_score"] == 0.97
    assert data["app_registry_status"] == "unregistered"
    assert any("QuickPaisa" in f for f in data["flags"])


def test_loan_registered_app_does_not_escalate():
    resp = _post(
        "/scams/loan/check",
        transcript="This is a 7-day loan tenure using the KreditBee app.",
    )
    assert resp.status_code == 200
    data = resp.json()
    # Base single-phrase-signal result, unescalated — registered app, no extra flag.
    assert data["risk_level"] == "medium"
    assert data["confidence_score"] == 0.65
    assert data["app_registry_status"] == "registered"


def test_loan_app_name_alone_no_phrase_signal_does_not_escalate():
    resp = _post("/scams/loan/check", transcript="I am using the QuickPaisa app for my daily budgeting.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["app_registry_status"] == "unregistered"
    assert data["flags"] == []


# ── Sextortion (item 9) — base content-analysis path ──────────────────────────

def test_sextortion_base_high_adult_context():
    resp = _post(
        "/scams/sextortion/check",
        transcript="If you don't pay money or upload the payment, I will leak your video to your friends.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert data["escalation_path"] == "adult_standard"
    assert "cybercrime.gov.in" in data["legal_escalation"]
    assert "1930" in data["legal_escalation"]
    assert "note" in data and "not a live handoff" in data["note"]


def test_sextortion_clean_text():
    resp = _post("/scams/sextortion/check", transcript="Just catching up with an old friend on video call, nothing unusual.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["legal_escalation"] == "None required."


def test_sextortion_empty_body_422():
    resp = client.post("/scams/sextortion/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Sextortion (item 9) — computed escalation_path capability ────────────────

def test_sextortion_minor_context_routes_to_minor_protection():
    resp = _post(
        "/scams/sextortion/check",
        transcript="I am 14 years old, class 9 school student. They said they will leak your video if I don't pay money or upload again.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert data["escalation_path"] == "minor_protection"
    assert "POCSO" in data["legal_escalation"]
    assert "1098" in data["legal_escalation"]
    assert any("guardian" in a.lower() for a in data["immediate_actions"])


def test_sextortion_minor_indicator_alone_does_not_false_escalate():
    # Minor-context language with no actual threat keyword — should not
    # fabricate an escalation; flags note the age context but risk stays low.
    resp = _post("/scams/sextortion/check", transcript="I am 15 years old, class 10 school student, studying for board exam.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["escalation_path"] == "minor_protection"
    assert data["legal_escalation"] == "None required."
    assert any("minor" in f.lower() for f in data["flags"])
