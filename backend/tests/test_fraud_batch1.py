"""Tests for /scams/{romance,investment,lottery,courier,bec}/check — Track 1 items 1/2/4/5/6."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _post(path: str, **body):
    return client.post(path, json=body)


# ── Romance (item 1) — weighted phrase + structural scoring ───────────────────

def test_romance_high_risk_text():
    resp = _post(
        "/scams/romance/check",
        transcript=(
            "You are my soulmate and I fell in love with you instantly, but my camera "
            "is broken so we cannot video call. Please wire me money via western union."
        ),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 3


def test_romance_clean_text():
    resp = _post("/scams/romance/check", transcript="Hey, how was your weekend? Let's catch up soon.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []
    assert data["confidence_score"] == 0.0


def test_romance_empty_body_422():
    resp = client.post("/scams/romance/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Investment (item 2) ─────────────────────────────────────────────────────

def test_investment_high_risk_text():
    resp = _post(
        "/scams/investment/check",
        transcript="This is a guaranteed returns scheme, SEBI approved, but join the group now — limited slots.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_investment_clean_text():
    resp = _post("/scams/investment/check", transcript="I'm thinking about opening a fixed deposit at my bank.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_investment_empty_body_422():
    resp = client.post("/scams/investment/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Lottery (item 4) ─────────────────────────────────────────────────────────

def test_lottery_high_risk_text():
    resp = _post(
        "/scams/lottery/check",
        transcript="Congratulations you won the lottery! Please pay the income tax fee to claim your prize money.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_lottery_evidence_trail_matches_flags():
    """evidence_trail (item 84) is additive: one item per flag, all contributing, zero flags-field change."""
    resp = _post(
        "/scams/lottery/check",
        transcript="Congratulations you won the lottery! Please pay the income tax fee to claim your prize money.",
    )
    data = resp.json()
    trail = data["evidence_trail"]["items"]
    assert [t["signal"] for t in trail] == data["flags"]
    assert all(t["contributed_to_verdict"] for t in trail)


def test_lottery_clean_text():
    resp = _post("/scams/lottery/check", transcript="Don't forget to pick up milk on your way home.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_lottery_empty_body_422():
    resp = client.post("/scams/lottery/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Courier (item 5) ─────────────────────────────────────────────────────────

def test_courier_high_risk_text():
    resp = _post(
        "/scams/courier/check",
        transcript=(
            "This is FedEx parcel customs department calling. Your package contains illegal "
            "drugs and contraband. We are transferring you to cyber cell for CBI clearance."
        ),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) == 3


def test_courier_clean_text():
    resp = _post("/scams/courier/check", transcript="Your Amazon order has shipped and will arrive tomorrow.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_courier_empty_body_422():
    resp = client.post("/scams/courier/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── BEC (item 6) ─────────────────────────────────────────────────────────────

def test_bec_high_risk_text():
    resp = _post(
        "/scams/bec/check",
        email_body=(
            "Please note the updated banking details for this alternative bank account. "
            "This is a confidential project, do not mention to staff, and process immediately."
        ),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_bec_clean_text():
    resp = _post("/scams/bec/check", email_body="Attached is the quarterly report for your review, no rush.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_bec_empty_body_422():
    resp = client.post("/scams/bec/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")
