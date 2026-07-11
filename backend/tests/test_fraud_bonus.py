"""Tests for /scams/{challan,customercare,kyc,rental,reward,utility}/check —
unscoped bonus fraud detectors (not part of Track 1's assigned 30-item scope)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _post(path: str, **body):
    return client.post(path, json=body)


# ── Challan / e-challan (bonus) ────────────────────────────────────────────────

def test_challan_high_risk_text():
    resp = _post(
        "/scams/challan/check",
        transcript="Traffic violation penalty pending — vehicle impound warning. Click here to pay challan now.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_challan_clean_text():
    resp = _post("/scams/challan/check", transcript="Renewed my driving license at the RTO office today.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_challan_empty_body_422():
    resp = client.post("/scams/challan/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Customer care (bonus) ───────────────────────────────────────────────────

def test_customercare_high_risk_text():
    resp = _post(
        "/scams/customercare/check",
        transcript="Please pay the customer care processing charge and download QuickSupport so I can share screen for support.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_customercare_clean_text():
    resp = _post("/scams/customercare/check", transcript="Thanks for calling, your issue has been resolved at no charge.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_customercare_empty_body_422():
    resp = client.post("/scams/customercare/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── KYC (bonus) ──────────────────────────────────────────────────────────────

def test_kyc_high_risk_text():
    resp = _post(
        "/scams/kyc/check",
        transcript="Your PAN card blocked, account suspended. Click link to update PAN immediately.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert data["confidence_score"] == 0.96
    assert len(data["flags"]) >= 2


def test_kyc_clean_text():
    resp = _post("/scams/kyc/check", transcript="My KYC was completed successfully at the branch last week.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_kyc_empty_body_422():
    resp = client.post("/scams/kyc/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Rental (bonus) ───────────────────────────────────────────────────────────

def test_rental_high_risk_text():
    resp = _post(
        "/scams/rental/check",
        transcript="I'm an army officer transfer to your city, cantonment area rule requires a token amount to lock the flat before I visit.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert data["confidence_score"] == 0.98
    assert len(data["flags"]) >= 2


def test_rental_clean_text():
    resp = _post("/scams/rental/check", transcript="The 2BHK is available from next month, feel free to visit anytime this week.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_rental_empty_body_422():
    resp = client.post("/scams/rental/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Reward (bonus) — needs all 3 flags for high ───────────────────────────────

def test_reward_high_risk_text():
    resp = _post(
        "/scams/reward/check",
        transcript="You have been selected for a reward! Pay the reward processing fee now — reward expires today.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) == 3


def test_reward_clean_text():
    resp = _post("/scams/reward/check", transcript="Thanks for shopping with us, here is your regular monthly statement.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_reward_empty_body_422():
    resp = client.post("/scams/reward/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Utility (bonus) ──────────────────────────────────────────────────────────

def test_utility_high_risk_text():
    resp = _post(
        "/scams/utility/check",
        transcript="Electricity will be disconnected tonight due to unpaid bill. Contact power department helpline immediately.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_utility_clean_text():
    resp = _post("/scams/utility/check", transcript="Your electricity bill for this month has been generated and paid successfully.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_utility_empty_body_422():
    resp = client.post("/scams/utility/check", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")
