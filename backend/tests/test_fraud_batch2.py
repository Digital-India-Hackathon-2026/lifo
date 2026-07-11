"""Tests for /scams/{matrimonial,gov-scheme,qr,exam,ecommerce,ussd,recruitment}/check — Track 1 items 8/10/11/12/13/14/15."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _post(path: str, **body):
    return client.post(path, json=body)


# ── Matrimonial (item 8) ──────────────────────────────────────────────────────

def test_matrimonial_high_risk_text():
    resp = _post(
        "/scams/matrimonial/check",
        transcript="I am an NRI doctor, UK surgeon, returning to India soon, but I had a medical emergency and got robbed.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_matrimonial_clean_text():
    resp = _post("/scams/matrimonial/check", transcript="I really enjoyed our conversation yesterday, looking forward to meeting your family.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_matrimonial_empty_body_422():
    resp = client.post("/scams/matrimonial/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Government scheme (item 10) — needs all 3 flags for high ─────────────────

def test_gov_scheme_high_risk_text():
    resp = _post(
        "/scams/gov-scheme/check",
        transcript="Claim your PM-Kisan subsidy now. Pay the registration fee to release funds — update KYC today or face scheme cancellation.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) == 3


def test_gov_scheme_clean_text():
    resp = _post("/scams/gov-scheme/check", transcript="The gram panchayat office is open from 10am to 5pm on weekdays.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_gov_scheme_empty_body_422():
    resp = client.post("/scams/gov-scheme/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── QR / quishing (item 11) — either 1 signal alone is already "high" ────────

def test_qr_high_risk_text_single_signal():
    resp = _post("/scams/qr/check", transcript="Just scan to receive your cashback instantly!")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert data["confidence_score"] == 0.90
    assert len(data["flags"]) == 1


def test_qr_clean_text():
    resp = _post("/scams/qr/check", transcript="Please pay using the QR code at checkout to complete your purchase.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_qr_empty_body_422():
    resp = client.post("/scams/qr/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Exam / scholarship (item 12) — email_body preferred ───────────────────────

def test_exam_high_risk_text():
    resp = _post(
        "/scams/exam/check",
        email_body="We guarantee a pass with a leaked paper. Pay the scholarship processing fee before the deadline tonight.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_exam_clean_text():
    resp = _post("/scams/exam/check", email_body="Your semester exam timetable has been published on the student portal.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_exam_empty_body_422():
    resp = client.post("/scams/exam/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── E-commerce / delivery / refund (item 13) — needs all 3 flags for high ────

def test_ecommerce_high_risk_text():
    resp = _post(
        "/scams/ecommerce/check",
        transcript="Accidental double charge — click to process refund. Reschedule delivery fee required, and claim your reward now.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) == 3


def test_ecommerce_clean_text():
    resp = _post("/scams/ecommerce/check", transcript="Your order has been delivered. Thank you for shopping with us.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_ecommerce_empty_body_422():
    resp = client.post("/scams/ecommerce/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── USSD call-forwarding (item 14) ────────────────────────────────────────────

def test_ussd_high_risk_text():
    resp = _post(
        "/scams/ussd/check",
        transcript="Please dial *401* to upgrade your SIM for the Jio network update, you will receive a code, do not disconnect.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_ussd_clean_text():
    resp = _post("/scams/ussd/check", transcript="My phone battery is draining faster than usual lately.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_ussd_empty_body_422():
    resp = client.post("/scams/ussd/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Fake recruitment portal (item 15) — email_body preferred ─────────────────

def test_recruitment_high_risk_text():
    resp = _post(
        "/scams/recruitment/check",
        email_body="Naukri Premium fast track placement — pay for interview and a laptop security deposit to secure your guaranteed joining reward.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_recruitment_clean_text():
    resp = _post("/scams/recruitment/check", email_body="Thank you for applying. Our HR team will review your resume and get back to you.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_recruitment_empty_body_422():
    resp = client.post("/scams/recruitment/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")
