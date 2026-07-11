"""Tests for /assist/complaint — NCRP and bank dispute template generation."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.complaint import _build_bank_dispute, _build_ncrp, ComplaintRequest

client = TestClient(app)

_FULL_REQ = {
    "complaint_type": "both",
    "complainant_name": "Ramesh Kumar",
    "complainant_phone": "9876543210",
    "complainant_email": "ramesh@example.com",
    "complainant_address": "12 MG Road, Bengaluru, Karnataka 560001",
    "incident_date": "2 July 2026, 3:00 PM",
    "incident_description": "A person claiming to be a CBI officer called me on WhatsApp.",
    "platform_used": "WhatsApp video call",
    "suspect_name": "Officer Sharma",
    "suspect_phone": "8765432109",
    "suspect_upi_id": "cbi.verify@okicici",
    "suspect_claimed_agency": "CBI, Cybercrime Division",
    "amount_lost": 50000.0,
    "payment_mode": "UPI",
    "transaction_reference": "UTR123456789",
    "transaction_date": "2 July 2026",
    "recipient_account": "cbi.verify@okicici",
    "bank_name": "HDFC Bank",
    "account_number": "1234567890",
    "ncrp_complaint_number": "NCRP-2026-12345",
    "matched_patterns": ["digital_arrest", "money_laundering_claim", "stay_on_line"],
    "payment_indicators": ["immediate_payment", "transfer_demand"],
}

_MINIMAL_REQ = {"complaint_type": "both"}


# ── Unit: _build_ncrp ─────────────────────────────────────────────────────────

def test_ncrp_full_input_contains_complainant_name():
    req = ComplaintRequest(**_FULL_REQ)
    text = _build_ncrp(req)
    assert "Ramesh Kumar" in text


def test_ncrp_full_input_contains_amount():
    req = ComplaintRequest(**_FULL_REQ)
    text = _build_ncrp(req)
    assert "50,000.00" in text


def test_ncrp_full_input_contains_upi_id():
    req = ComplaintRequest(**_FULL_REQ)
    text = _build_ncrp(req)
    assert "cbi.verify@okicici" in text


def test_ncrp_full_input_contains_matched_patterns():
    req = ComplaintRequest(**_FULL_REQ)
    text = _build_ncrp(req)
    assert "digital_arrest" in text


def test_ncrp_full_input_contains_legal_sections():
    req = ComplaintRequest(**_FULL_REQ)
    text = _build_ncrp(req)
    assert "§66C" in text or "66C" in text


def test_ncrp_full_input_contains_cybercrime_portal():
    req = ComplaintRequest(**_FULL_REQ)
    text = _build_ncrp(req)
    assert "cybercrime.gov.in" in text
    assert "1930" in text


def test_ncrp_minimal_input_uses_placeholders():
    req = ComplaintRequest(**_MINIMAL_REQ)
    text = _build_ncrp(req)
    assert "[FULL NAME]" in text
    assert "[AMOUNT]" in text
    assert "cybercrime.gov.in" in text


def test_ncrp_minimal_input_does_not_crash():
    req = ComplaintRequest(**_MINIMAL_REQ)
    _build_ncrp(req)  # must not raise


# ── Unit: _build_bank_dispute ─────────────────────────────────────────────────

def test_bank_dispute_full_input_subject_contains_last4():
    req = ComplaintRequest(**_FULL_REQ)
    text = _build_bank_dispute(req)
    assert "7890" in text  # last 4 of account_number="1234567890"


def test_bank_dispute_full_input_contains_amount():
    req = ComplaintRequest(**_FULL_REQ)
    text = _build_bank_dispute(req)
    assert "50,000.00" in text


def test_bank_dispute_full_input_contains_ncrp_ref():
    req = ComplaintRequest(**_FULL_REQ)
    text = _build_bank_dispute(req)
    assert "NCRP-2026-12345" in text


def test_bank_dispute_full_input_contains_rbi_reference():
    req = ComplaintRequest(**_FULL_REQ)
    text = _build_bank_dispute(req)
    assert "RBI" in text


def test_bank_dispute_full_input_mentions_digital_arrest():
    req = ComplaintRequest(**_FULL_REQ)
    text = _build_bank_dispute(req)
    assert "Digital Arrest" in text


def test_bank_dispute_minimal_input_uses_placeholders():
    req = ComplaintRequest(**_MINIMAL_REQ)
    text = _build_bank_dispute(req)
    assert "[FULL NAME]" in text or "[AMOUNT]" in text


def test_bank_dispute_minimal_input_does_not_crash():
    req = ComplaintRequest(**_MINIMAL_REQ)
    _build_bank_dispute(req)  # must not raise


# ── API: complaint_type filtering ─────────────────────────────────────────────

def test_api_type_ncrp_only():
    req = {**_FULL_REQ, "complaint_type": "ncrp"}
    resp = client.post("/assist/complaint", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ncrp_complaint_text"] is not None
    assert data["bank_dispute_text"] is None


def test_api_type_bank_dispute_only():
    req = {**_FULL_REQ, "complaint_type": "bank_dispute"}
    resp = client.post("/assist/complaint", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["bank_dispute_text"] is not None
    assert data["ncrp_complaint_text"] is None


def test_api_type_both():
    resp = client.post("/assist/complaint", json=_FULL_REQ)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ncrp_complaint_text"] is not None
    assert data["bank_dispute_text"] is not None


# ── API: full input ───────────────────────────────────────────────────────────

def test_api_full_input_200():
    resp = client.post("/assist/complaint", json=_FULL_REQ)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")


def test_api_full_input_next_steps_present():
    resp = client.post("/assist/complaint", json=_FULL_REQ)
    data = resp.json()
    assert isinstance(data["next_steps"], list)
    assert len(data["next_steps"]) > 0
    # Must include helpline
    combined = " ".join(data["next_steps"])
    assert "1930" in combined
    assert "cybercrime.gov.in" in combined


def test_api_full_input_disclaimer_present():
    resp = client.post("/assist/complaint", json=_FULL_REQ)
    assert resp.json()["disclaimer"]


# ── API: minimal input — graceful, no crash ───────────────────────────────────

def test_api_minimal_input_200():
    resp = client.post("/assist/complaint", json=_MINIMAL_REQ)
    assert resp.status_code == 200


def test_api_minimal_input_templates_produced():
    resp = client.post("/assist/complaint", json=_MINIMAL_REQ)
    data = resp.json()
    # Templates are produced even with no data — just have placeholders
    assert data["ncrp_complaint_text"] is not None
    assert data["bank_dispute_text"] is not None
    assert "[FULL NAME]" in data["ncrp_complaint_text"]


# ── API: input validation ─────────────────────────────────────────────────────

def test_api_invalid_complaint_type_422():
    resp = client.post("/assist/complaint", json={"complaint_type": "police_station"})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


def test_api_missing_complaint_type_422():
    resp = client.post("/assist/complaint", json={"complainant_name": "Test"})
    assert resp.status_code == 422


def test_api_negative_amount_422():
    resp = client.post("/assist/complaint", json={**_MINIMAL_REQ, "amount_lost": -1000})
    assert resp.status_code == 422


def test_api_response_shape():
    resp = client.post("/assist/complaint", json=_FULL_REQ)
    data = resp.json()
    for field in ("ncrp_complaint_text", "bank_dispute_text", "next_steps", "disclaimer"):
        assert field in data


# ── API: forwarded fields from prior endpoints ────────────────────────────────

def test_api_matched_patterns_appear_in_ncrp():
    resp = client.post("/assist/complaint", json={
        **_MINIMAL_REQ,
        "complaint_type": "ncrp",
        "matched_patterns": ["digital_arrest", "stay_on_line"],
    })
    ncrp = resp.json()["ncrp_complaint_text"]
    assert "digital_arrest" in ncrp


def test_api_payment_indicators_appear_in_ncrp():
    resp = client.post("/assist/complaint", json={
        **_MINIMAL_REQ,
        "complaint_type": "ncrp",
        "payment_indicators": ["immediate_payment"],
    })
    ncrp = resp.json()["ncrp_complaint_text"]
    assert "immediate_payment" in ncrp


# ── API: /legal/templates/ezero-fir (item 65) ─────────────────────────────────

def test_ezero_fir_valid_category_returns_correct_statute_and_hash_format():
    resp = client.post("/legal/templates/ezero-fir", json={"category": "digital_arrest"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["statute"] == "Bhartiya Nagarik Suraksha Sanhita (BNSS) Sec 457"
    assert data["jurisdiction"] == "NCRP_CENTRAL_NODE"
    assert data["threat_category"] == "digital_arrest"
    assert data["status"] == "AWAITING_CRYPTOGRAPHIC_SIGNATURE"
    assert data["fir_hash"].startswith("FIR-")
    assert len(data["fir_hash"]) == len("FIR-") + 12


def test_ezero_fir_missing_category_422():
    resp = client.post("/legal/templates/ezero-fir", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")
