import pytest
from fastapi.testclient import TestClient

from app.main import app

# raise_server_exceptions=False: let our exception handler return the 500 JSON
# instead of TestClient re-raising the exception into the test.
client = TestClient(app, raise_server_exceptions=False)

JSON_CONTENT_TYPE = "application/json"


def assert_json_response(resp, expected_status: int) -> dict:
    """Assert status code, JSON content-type, and parseable body. Returns parsed dict."""
    assert resp.status_code == expected_status
    assert resp.headers["content-type"].startswith(JSON_CONTENT_TYPE), (
        f"Expected content-type {JSON_CONTENT_TYPE!r}, got {resp.headers['content-type']!r}"
    )
    return resp.json()  # raises if body isn't valid JSON


def test_health_returns_ok():
    data = assert_json_response(client.get("/health"), 200)
    assert data == {"status": "ok"}


def test_404_is_valid_json():
    data = assert_json_response(client.get("/nonexistent-route-xyz"), 404)
    assert "error" in data
    assert "status_code" in data
    assert data["status_code"] == 404


def test_500_is_valid_json():
    data = assert_json_response(client.get("/debug/crash"), 500)
    assert "error" in data
    assert "status_code" in data
    assert data["status_code"] == 500
