"""Tests for /check/phishing — blocklist lookup + typosquat similarity scoring."""
import os
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.phishing import (
    _extract_domain,
    _extract_sld,
    _fetch_blocklist,
    _score_similarity,
    load_phishing_blocklist,
)

client = TestClient(app)


# ── Unit: domain extraction ──────────────────────────────────────────────────

def test_extract_domain_bare():
    assert _extract_domain("cbi.gov.in") == "cbi.gov.in"


def test_extract_domain_full_url():
    assert _extract_domain("https://www.icicibank.com/login") == "icicibank.com"


def test_extract_domain_strips_www():
    assert _extract_domain("www.sbi.co.in") == "sbi.co.in"


def test_extract_domain_empty():
    assert _extract_domain("") == ""


def test_extract_domain_http_with_path():
    assert _extract_domain("http://phish.example.com/verify?ref=1") == "phish.example.com"


# ── Unit: SLD extraction ─────────────────────────────────────────────────────

def test_extract_sld_compound_gov_in():
    assert _extract_sld("cbi.gov.in") == "cbi"


def test_extract_sld_compound_co_in():
    assert _extract_sld("sbi.co.in") == "sbi"


def test_extract_sld_compound_org_in():
    assert _extract_sld("npci.org.in") == "npci"


def test_extract_sld_simple_com():
    assert _extract_sld("hdfcbank.com") == "hdfcbank"


def test_extract_sld_simple_in():
    assert _extract_sld("pnbindia.in") == "pnbindia"


# ── Unit: similarity scoring — HIGH (typosquats) ────────────────────────────

def test_similarity_word_boundary_typosquat():
    score, match = _score_similarity("cbi-verify.gov.in")
    assert score >= 0.75
    assert match == "cbi.gov.in"


def test_similarity_prefix_typosquat_no_separator():
    score, match = _score_similarity("cbigov.in")
    assert score >= 0.75


def test_similarity_long_brand_match():
    score, _ = _score_similarity("incometaxgov.in")
    assert score >= 0.75


def test_similarity_bank_with_suffix():
    score, match = _score_similarity("hdfcbank-login.com")
    assert score >= 0.75
    assert match == "hdfcbank.com"


def test_similarity_bank_with_extra_char():
    score, _ = _score_similarity("axisbanks.com")
    assert score >= 0.75


def test_similarity_gov_in_embedded_in_com():
    # "cbi.gov.in.verify.com" — SLD extracted from .com gives "cbi.gov.in"
    score, _ = _score_similarity("cbi.gov.in.verify.com")
    assert score >= 0.75


# ── Unit: similarity scoring — LOW (legitimate domains) ─────────────────────

def test_similarity_google_low():
    score, _ = _score_similarity("google.com")
    assert score < 0.55


def test_similarity_amazon_low():
    score, _ = _score_similarity("amazon.com")
    assert score < 0.55


def test_similarity_example_low():
    score, _ = _score_similarity("example.com")
    assert score < 0.55


def test_similarity_openai_low():
    score, _ = _score_similarity("openai.com")
    assert score < 0.55


def test_similarity_facebook_low():
    score, _ = _score_similarity("facebook.com")
    assert score < 0.55


# ── API: malformed / missing input ───────────────────────────────────────────

def test_api_empty_url_returns_400():
    resp = client.post("/check/phishing", json={"url": ""})
    assert resp.status_code == 400
    assert resp.headers["content-type"].startswith("application/json")
    assert "error" in resp.json() or "detail" in resp.json()


def test_api_missing_field_returns_422():
    resp = client.post("/check/phishing", json={})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── API: known-clean domain → low risk ──────────────────────────────────────

def test_api_clean_domain_low_risk():
    with patch("app.routers.phishing._blocklist_domains", set()):
        resp = client.post("/check/phishing", json={"url": "google.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["in_blocklist"] is False
    assert data["risk_level"] == "low"
    assert data["similarity_score"] < 0.55
    assert data["matched_against"] is None
    assert "disclaimer" in data


# ── API: known-bad domain (blocklisted) → high risk ─────────────────────────

def test_api_blocklisted_domain_high_risk():
    fake_blocklist = {"phishing-example.com", "malicious-site.net"}
    with patch("app.routers.phishing._blocklist_domains", fake_blocklist):
        resp = client.post("/check/phishing", json={"url": "phishing-example.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["in_blocklist"] is True
    assert data["blocklist_match"] == "phishing-example.com"
    assert data["risk_level"] == "high"


# ── API: typosquat but not in blocklist → high risk by similarity ─────────────

def test_api_typosquat_not_blocklisted_high_risk():
    with patch("app.routers.phishing._blocklist_domains", set()):
        resp = client.post("/check/phishing", json={"url": "https://cbi-verify.gov.in/login"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["in_blocklist"] is False
    assert data["similarity_score"] >= 0.75
    assert data["risk_level"] == "high"
    assert data["matched_against"] is not None
    assert "cbi" in data["note"].lower() or "resembles" in data["note"].lower()


# ── API: URL normalisation (path/www stripped) ───────────────────────────────

def test_api_url_with_path_and_www():
    with patch("app.routers.phishing._blocklist_domains", set()):
        resp = client.post(
            "/check/phishing",
            json={"url": "http://www.incometaxgov.in/verify/pay?token=abc"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["domain"] == "incometaxgov.in"
    assert data["risk_level"] == "high"


# ── Unit: cache cold-start behavior ─────────────────────────────────────────

def test_cache_cold_start_fresh_cache_loads(tmp_path):
    """Fresh cache file → read from disk, no network call."""
    cache_file = tmp_path / "phishtank_cache.txt"
    cache_file.write_text("evil1.com\nevil2.com\n")

    import app.routers.phishing as mod

    orig_file, orig_domains = mod._CACHE_FILE, mod._blocklist_domains
    try:
        mod._CACHE_FILE = cache_file
        mod._blocklist_domains = set()
        load_phishing_blocklist()
        assert "evil1.com" in mod._blocklist_domains
        assert "evil2.com" in mod._blocklist_domains
    finally:
        mod._CACHE_FILE = orig_file
        mod._blocklist_domains = orig_domains


def test_cache_stale_fetch_fails_uses_stale(tmp_path):
    """Stale cache + network failure → serve stale rather than empty."""
    cache_file = tmp_path / "phishtank_cache.txt"
    cache_file.write_text("stale-evil.com\n")
    old_mtime = time.time() - 90_000
    os.utime(cache_file, (old_mtime, old_mtime))

    import app.routers.phishing as mod

    orig_file, orig_domains = mod._CACHE_FILE, mod._blocklist_domains
    try:
        mod._CACHE_FILE = cache_file
        mod._blocklist_domains = set()
        with patch("app.routers.phishing._fetch_blocklist", side_effect=RuntimeError("down")):
            load_phishing_blocklist()
        assert "stale-evil.com" in mod._blocklist_domains
    finally:
        mod._CACHE_FILE = orig_file
        mod._blocklist_domains = orig_domains


def test_cache_no_cache_fetch_fails_stays_empty(tmp_path):
    """No cache + network failure → blocklist empty, but no crash."""
    cache_file = tmp_path / "missing_cache.txt"  # does not exist

    import app.routers.phishing as mod

    orig_file, orig_domains = mod._CACHE_FILE, mod._blocklist_domains
    try:
        mod._CACHE_FILE = cache_file
        mod._blocklist_domains = set()
        with patch("app.routers.phishing._fetch_blocklist", side_effect=RuntimeError("down")):
            load_phishing_blocklist()
        assert mod._blocklist_domains == set()
    finally:
        mod._CACHE_FILE = orig_file
        mod._blocklist_domains = orig_domains


# ── Integration: real PhishTank fetch (skip if unavailable) ─────────────────

@pytest.mark.integration
def test_integration_phishtank_live_fetch():
    """Fetch real PhishTank CSV and verify shape of returned data."""
    try:
        domains = _fetch_blocklist()
    except Exception as exc:
        pytest.skip(f"PhishTank unavailable: {exc}")

    assert len(domains) > 100, f"Expected >100 domains, got {len(domains)}"
    for d in list(domains)[:10]:
        assert "://" not in d, f"Domain should not contain protocol: {d}"
        assert "/" not in d, f"Domain should not contain path: {d}"
