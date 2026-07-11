"""
Tests for /classify/document.

Unit tests:    Vision API fully mocked — tests rule logic and HTTP layer in isolation.
               Run: uv run python -m pytest tests/test_document.py -v -k "not integration"
Integration:   Hits real Google Cloud Vision API.
               Requires: GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcp-credentials.json
               Run: GOOGLE_APPLICATION_CREDENTIALS=... uv run python -m pytest tests/test_document.py -v -k integration
"""
import io
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app
from app.routers.document import _analyze_text

DISCLAIMER = (
    "This tool reduces risk but cannot guarantee 100% accuracy. "
    "Always verify through a second, independent channel before sending money."
)
JSON_CT = "application/json"

# Module-level client — lifespan NOT triggered; unit tests patch _vision_client per-test.
client = TestClient(app, raise_server_exceptions=False)


def _img_bytes(color: tuple = (240, 240, 240)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, format="JPEG")
    return buf.getvalue()


def _mock_vision(text: str = "", error: str = "") -> MagicMock:
    annotation = MagicMock()
    annotation.description = text
    resp = MagicMock()
    resp.text_annotations = [annotation] if text else []
    resp.error.message = error
    mock = MagicMock()
    mock.text_detection.return_value = resp
    return mock


def _assert_json(resp, expected_status: int) -> dict:
    assert resp.status_code == expected_status, resp.text
    assert resp.headers["content-type"].startswith(JSON_CT)
    return resp.json()


requires_gcp = pytest.mark.skipif(
    not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    reason="GOOGLE_APPLICATION_CREDENTIALS not set — set it to run integration tests",
)


# ── Unit: HTTP layer with mocked Vision client ────────────────────────────────

def test_document_high_risk_scam_with_payment():
    text = "Digital arrest notice. Pay immediately. UPI: abc@okicici"
    with patch("app.routers.document._vision_client", _mock_vision(text)), \
         patch("app.routers.document._gcp_vision", MagicMock()):
        body = _assert_json(
            client.post("/classify/document", files={"file": ("n.jpg", _img_bytes(), "image/jpeg")}),
            200,
        )
    assert body["risk_level"] == "high"
    types = {i["type"] for i in body["scam_indicators"]}
    assert "digital_arrest" in types
    assert "upi_id_or_email" in types
    assert body["disclaimer"] == DISCLAIMER
    assert "note" in body


def test_document_evidence_trail_matches_indicators():
    """evidence_trail (item 84) mirrors scam_indicators/pii_detected — additive, not a replacement."""
    text = "Digital arrest notice. Pay immediately. UPI: abc@okicici"
    with patch("app.routers.document._vision_client", _mock_vision(text)), \
         patch("app.routers.document._gcp_vision", MagicMock()):
        body = _assert_json(
            client.post("/classify/document", files={"file": ("n.jpg", _img_bytes(), "image/jpeg")}),
            200,
        )
    trail_signals = {t["signal"] for t in body["evidence_trail"]["items"]}
    assert trail_signals == {i["type"] for i in body["scam_indicators"]} | {f"pii:{p['type']}" for p in body["pii_detected"]}
    assert body["scam_indicators"]  # existing field untouched


def test_document_medium_risk_scam_no_payment():
    text = "This is a verification fee document. CBI notice enclosed."
    with patch("app.routers.document._vision_client", _mock_vision(text)), \
         patch("app.routers.document._gcp_vision", MagicMock()):
        body = _assert_json(
            client.post("/classify/document", files={"file": ("n.jpg", _img_bytes(), "image/jpeg")}),
            200,
        )
    assert body["risk_level"] == "medium"
    types = {i["type"] for i in body["scam_indicators"]}
    assert "verification_payment" in types


def test_document_low_risk_clean_text():
    text = "Property deed for plot 42, signed on January 2026. Witness: Ramesh."
    with patch("app.routers.document._vision_client", _mock_vision(text)), \
         patch("app.routers.document._gcp_vision", MagicMock()):
        body = _assert_json(
            client.post("/classify/document", files={"file": ("n.jpg", _img_bytes(), "image/jpeg")}),
            200,
        )
    assert body["risk_level"] == "low"
    assert body["scam_indicators"] == []
    assert body["pii_detected"] == []


def test_document_detects_aadhaar_pii():
    text = "Holder Aadhaar: 1234 5678 9012. Please verify."
    with patch("app.routers.document._vision_client", _mock_vision(text)), \
         patch("app.routers.document._gcp_vision", MagicMock()):
        body = _assert_json(
            client.post("/classify/document", files={"file": ("n.jpg", _img_bytes(), "image/jpeg")}),
            200,
        )
    pii_types = [p["type"] for p in body["pii_detected"]]
    assert "aadhaar" in pii_types
    masked = next(p["masked_value"] for p in body["pii_detected"] if p["type"] == "aadhaar")
    assert masked == "XXXX-XXXX-9012"
    # Bare Aadhaar without an account keyword must NOT also flag bank_account
    assert "bank_account" not in {i["type"] for i in body["scam_indicators"]}


def test_document_detects_pan_pii():
    text = "PAN card: ABCDE1234F issued to the holder."
    with patch("app.routers.document._vision_client", _mock_vision(text)), \
         patch("app.routers.document._gcp_vision", MagicMock()):
        body = _assert_json(
            client.post("/classify/document", files={"file": ("n.jpg", _img_bytes(), "image/jpeg")}),
            200,
        )
    pii_types = [p["type"] for p in body["pii_detected"]]
    assert "pan" in pii_types
    masked = next(p["masked_value"] for p in body["pii_detected"] if p["type"] == "pan")
    assert masked == "ABCXXXXXXF"


def test_document_medium_risk_from_pii_alone():
    # PII present but no scam phrases → medium (privacy risk)
    text = "Holder PAN: ABCDE1234F. Date: 01 Jan 2026."
    with patch("app.routers.document._vision_client", _mock_vision(text)), \
         patch("app.routers.document._gcp_vision", MagicMock()):
        body = _assert_json(
            client.post("/classify/document", files={"file": ("n.jpg", _img_bytes(), "image/jpeg")}),
            200,
        )
    assert body["risk_level"] == "medium"
    assert body["scam_indicators"] == []
    assert any(p["type"] == "pan" for p in body["pii_detected"])


# ── Unit: rule-logic regression (direct _analyze_text) ───────────────────────

def test_aadhaar_not_flagged_as_bank_account():
    """12-digit Aadhaar number without an account anchor keyword must not trigger bank_account."""
    indicators, pii = _analyze_text("Your Aadhaar number is 1234 5678 9012.")
    assert any(p.type == "aadhaar" for p in pii)
    assert all(i.type != "bank_account" for i in indicators)


def test_plain_number_no_anchor_does_not_trigger_bank_account():
    """Standalone numbers with no account/a-c/ifsc keyword must not trigger bank_account."""
    indicators, pii = _analyze_text(
        "Invoice #98765432101 dated 01-Jan-2026. Total: 12500. Ref: 9876543210."
    )
    assert indicators == []
    assert pii == []


def test_bank_account_with_anchor_does_trigger():
    """Number preceded by 'Account No' (11 digits, not Aadhaar-shaped) must trigger bank_account."""
    indicators, _ = _analyze_text(
        "Please transfer to Account No: 98765432101 before Friday."
    )
    assert any(i.type == "bank_account" for i in indicators)


def test_aadhaar_shaped_account_suppressed():
    """12-digit number after 'Account No' matches Aadhaar pattern → bank_account suppressed."""
    indicators, pii = _analyze_text("Account No: 1234 5678 9012")
    assert any(p.type == "aadhaar" for p in pii)
    assert all(i.type != "bank_account" for i in indicators)


# ── Unit: edge cases ──────────────────────────────────────────────────────────

def test_document_no_text_returns_400():
    with patch("app.routers.document._vision_client", _mock_vision("")), \
         patch("app.routers.document._gcp_vision", MagicMock()):
        body = _assert_json(
            client.post("/classify/document", files={"file": ("n.jpg", _img_bytes(), "image/jpeg")}),
            400,
        )
    assert "error" in body


def test_document_wrong_content_type_returns_415():
    body = _assert_json(
        client.post("/classify/document", files={"file": ("f.pdf", b"data", "application/pdf")}),
        415,
    )
    assert "error" in body


def test_document_oversized_returns_413():
    body = _assert_json(
        client.post(
            "/classify/document",
            files={"file": ("big.jpg", b"x" * (10 * 1024 * 1024 + 1), "image/jpeg")},
        ),
        413,
    )
    assert "error" in body


def test_document_corrupted_image_returns_400():
    body = _assert_json(
        client.post("/classify/document", files={"file": ("bad.jpg", b"not_an_image", "image/jpeg")}),
        400,
    )
    assert "error" in body


def test_document_gcp_api_error_returns_503():
    with patch("app.routers.document._vision_client", _mock_vision(error="quota exceeded")), \
         patch("app.routers.document._gcp_vision", MagicMock()):
        body = _assert_json(
            client.post("/classify/document", files={"file": ("n.jpg", _img_bytes(), "image/jpeg")}),
            503,
        )
    assert "error" in body


def test_document_missing_credentials_returns_503():
    with patch("app.routers.document._vision_client", None):
        body = _assert_json(
            client.post("/classify/document", files={"file": ("n.jpg", _img_bytes(), "image/jpeg")}),
            503,
        )
    assert "error" in body


# ── Integration: real GCP Vision API ─────────────────────────────────────────

def _make_scam_notice_image() -> bytes:
    """Render a fake CBI notice with obvious red-flag phrases as a JPEG."""
    img = Image.new("RGB", (1200, 950), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size=36
    )

    lines = [
        "CENTRAL BUREAU OF INVESTIGATION",
        "DIGITAL ARREST NOTICE",
        "",
        "You have been placed under digital arrest.",
        "A verification fee of Rs 50000 is required.",
        "Pay immediately to avoid criminal proceedings.",
        "UPI Payment: cbi.verify@okicici",
        "Account No: 98765432101",
        "Do not inform family or relatives.",
        "Comply within 24 hours.",
        "Aadhaar: 1234 5678 9012",
    ]

    y = 50
    for line in lines:
        draw.text((50, y), line, fill=(0, 0, 0), font=font)
        y += 70

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


@requires_gcp
def test_integration_document_real_vision_scam_notice():
    """Submit a rendered fake CBI notice; Vision OCR + rule engine must flag it HIGH."""
    img_data = _make_scam_notice_image()
    with TestClient(app) as live:
        body = _assert_json(
            live.post(
                "/classify/document",
                files={"file": ("fake_cbi_notice.jpg", img_data, "image/jpeg")},
            ),
            200,
        )
    ocr_snippet = body.get("ocr_text", "")[:400]
    assert body["risk_level"] in ("medium", "high"), (
        f"Expected medium/high, got '{body['risk_level']}'. OCR: {ocr_snippet}"
    )
    assert len(body["scam_indicators"]) > 0, f"No indicators. OCR: {ocr_snippet}"
    assert len(body["ocr_text"]) > 0
    assert body["disclaimer"] == DISCLAIMER
    assert "note" in body
