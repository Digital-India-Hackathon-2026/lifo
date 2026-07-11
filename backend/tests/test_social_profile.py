"""Tests for /check/social-profile — heuristic fake profile scoring."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.social_profile import _MEDIUM_SCORE, _SocialProfileRequest, _score_profile

client = TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _req(**overrides) -> dict:
    """Minimal valid request body — low-risk defaults."""
    base = {"platform": "instagram", "has_profile_photo": True, "is_verified": False}
    base.update(overrides)
    return base


def _total(req_obj: _SocialProfileRequest) -> int:
    return max(0, sum(e.points for e in _score_profile(req_obj)))


def _flags(req_obj: _SocialProfileRequest) -> list[str]:
    return [e.flag for e in _score_profile(req_obj) if e.points > 0]


# ── Unit: obviously fake profile ─────────────────────────────────────────────

def test_obviously_fake_scores_high():
    """No photo + 7-day account + mass following + no posts = well above HIGH threshold."""
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=False,
        account_age_days=7,
        follower_count=5,
        following_count=500,
        post_count=0,
        is_verified=False,
    )
    assert _total(req) >= 7


def test_obviously_fake_flags_are_expected():
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=False,
        account_age_days=7,
        follower_count=5,
        following_count=500,
        post_count=0,
        is_verified=False,
    )
    f = _flags(req)
    assert "no_profile_photo" in f
    assert "very_new_account" in f
    assert "mass_following" in f
    assert "no_posts" in f


# ── Unit: obviously real profile ─────────────────────────────────────────────

def test_real_looking_profile_scores_low():
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=True,
        profile_photo_is_stock=False,
        account_age_days=500,
        follower_count=420,
        following_count=310,
        post_count=60,
        bio_text="Food lover from Mumbai. Travelling one city at a time.",
        display_name="Priya Sharma",
        is_verified=False,
    )
    assert _total(req) < 4


# ── Unit: edge cases (divide-by-zero safety) ─────────────────────────────────

def test_zero_followers_zero_following_no_crash():
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=True,
        follower_count=0,
        following_count=0,
        is_verified=False,
    )
    entries = _score_profile(req)  # must not raise
    assert "no_social_presence" in [e.flag for e in entries if e.points > 0]


def test_zero_following_many_followers_not_suspicious():
    """Celebrity pattern: following=0, large follower count — no ratio red flag."""
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=True,
        follower_count=1_000_000,
        following_count=0,
        post_count=200,
        is_verified=True,
    )
    f = _flags(req)
    assert "mass_following" not in f
    assert "low_follower_ratio" not in f


def test_zero_following_not_provided_zero_followers_flagged():
    """Only follower_count provided and it's 0 — flag no_followers."""
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=True,
        follower_count=0,
        is_verified=False,
    )
    assert "no_followers" in _flags(req)


# ── Unit: individual signal checks ───────────────────────────────────────────

def test_stock_photo_flagged():
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=True,
        profile_photo_is_stock=True,
        is_verified=False,
    )
    assert "stock_photo" in _flags(req)


def test_recently_created_medium_weight():
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=True,
        account_age_days=60,
        is_verified=False,
    )
    entries = {e.flag: e.points for e in _score_profile(req)}
    assert "recently_created" in entries
    assert entries["recently_created"] == 2


def test_gov_impersonation_in_name_high_weight():
    req = _SocialProfileRequest(
        platform="whatsapp",
        has_profile_photo=True,
        display_name="CBI Officer Mumbai",
        is_verified=False,
    )
    entries = {e.flag: e.points for e in _score_profile(req)}
    assert "gov_impersonation_in_name" in entries
    assert entries["gov_impersonation_in_name"] >= 4


def test_gov_impersonation_in_bio_high_weight():
    req = _SocialProfileRequest(
        platform="whatsapp",
        has_profile_photo=True,
        bio_text="Senior officer, Enforcement Directorate, GoI.",
        is_verified=False,
    )
    entries = {e.flag: e.points for e in _score_profile(req)}
    assert "gov_impersonation_in_bio" in entries
    assert entries["gov_impersonation_in_bio"] >= 4


def test_urgency_in_bio_flagged():
    req = _SocialProfileRequest(
        platform="whatsapp",
        has_profile_photo=True,
        bio_text="Case registered against you. Pay verification fee immediately.",
        is_verified=False,
    )
    assert "urgency_in_bio" in _flags(req)


def test_digits_in_display_name_flagged():
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=True,
        display_name="RameshKumar123456",
        is_verified=False,
    )
    assert "digits_in_name" in _flags(req)


def test_two_digits_in_name_not_flagged():
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=True,
        display_name="Raj99",
        is_verified=False,
    )
    assert "digits_in_name" not in _flags(req)


def test_self_claimed_legitimacy_flagged():
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=True,
        display_name="Official RBI Help",
        is_verified=False,
    )
    assert "self_claimed_legitimacy" in _flags(req)


def test_generic_bio_flagged():
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=True,
        bio_text="DM for business | Collab DM | Follow for follow",
        is_verified=False,
    )
    assert "generic_bio" in _flags(req)


def test_verified_badge_reduces_score():
    req_base = _SocialProfileRequest(
        platform="instagram", has_profile_photo=True, account_age_days=10, is_verified=False
    )
    req_verified = _SocialProfileRequest(
        platform="instagram", has_profile_photo=True, account_age_days=10, is_verified=True
    )
    assert _total(req_verified) < _total(req_base)


def test_whatsapp_post_count_not_scored():
    """WhatsApp has no post feed — no_posts should never fire for that platform."""
    req = _SocialProfileRequest(
        platform="whatsapp",
        has_profile_photo=True,
        post_count=0,
        is_verified=False,
    )
    assert "no_posts" not in _flags(req)
    assert "very_few_posts" not in _flags(req)


def test_telegram_post_count_not_scored():
    req = _SocialProfileRequest(
        platform="telegram",
        has_profile_photo=True,
        post_count=0,
        is_verified=False,
    )
    assert "no_posts" not in _flags(req)


# ── API: input validation ─────────────────────────────────────────────────────

def test_api_negative_follower_count_422():
    resp = client.post("/check/social-profile", json=_req(follower_count=-1))
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


def test_api_negative_following_count_422():
    resp = client.post("/check/social-profile", json=_req(following_count=-10))
    assert resp.status_code == 422


def test_api_negative_post_count_422():
    resp = client.post("/check/social-profile", json=_req(post_count=-5))
    assert resp.status_code == 422


def test_api_negative_account_age_422():
    resp = client.post("/check/social-profile", json=_req(account_age_days=-1))
    assert resp.status_code == 422


def test_api_missing_required_has_profile_photo_422():
    resp = client.post("/check/social-profile", json={"platform": "instagram"})
    assert resp.status_code == 422


def test_api_invalid_platform_422():
    resp = client.post("/check/social-profile", json=_req(platform="tiktok"))
    assert resp.status_code == 422


# ── API: risk levels ──────────────────────────────────────────────────────────

def test_api_obviously_fake_high_risk():
    resp = client.post("/check/social-profile", json=_req(
        has_profile_photo=False,
        account_age_days=3,
        follower_count=2,
        following_count=800,
        post_count=0,
    ))
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["red_flags"]) >= 3


def test_api_real_looking_profile_low_risk():
    resp = client.post("/check/social-profile", json=_req(
        has_profile_photo=True,
        account_age_days=500,
        follower_count=420,
        following_count=310,
        post_count=60,
        bio_text="Travel photographer. Mumbai. Sharing moments.",
        display_name="Anil Verma",
    ))
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["total_score"] < 4


def test_api_gov_impersonation_medium_or_high():
    resp = client.post("/check/social-profile", json=_req(
        display_name="RBI Official Account",
        bio_text="Reserve Bank of India enforcement division.",
    ))
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] in ("medium", "high")
    flags = data["red_flags"]
    assert "gov_impersonation_in_name" in flags or "gov_impersonation_in_bio" in flags


# ── API: response shape and content guarantees ────────────────────────────────

def test_api_response_has_all_required_fields():
    resp = client.post("/check/social-profile", json=_req())
    assert resp.status_code == 200
    data = resp.json()
    for field in ("risk_level", "total_score", "red_flags", "score_breakdown", "note", "disclaimer"):
        assert field in data


def test_api_score_breakdown_entry_shape():
    resp = client.post("/check/social-profile", json=_req(
        has_profile_photo=False,
        account_age_days=5,
    ))
    data = resp.json()
    assert len(data["score_breakdown"]) > 0
    for entry in data["score_breakdown"]:
        assert "flag" in entry
        assert "points" in entry
        assert "reason" in entry


def test_api_total_score_matches_breakdown_sum():
    resp = client.post("/check/social-profile", json=_req(
        has_profile_photo=False,
        account_age_days=5,
        follower_count=0,
        following_count=0,
    ))
    data = resp.json()
    raw = sum(e["points"] for e in data["score_breakdown"])
    assert data["total_score"] == max(0, raw)


def test_api_limitation_note_always_present():
    """The coarse-filter limitation must appear in every response — not just docs."""
    for body in [
        _req(),  # low risk
        _req(has_profile_photo=False, account_age_days=3),  # high risk
    ]:
        resp = client.post("/check/social-profile", json=body)
        assert "well-resourced" in resp.json()["note"]


def test_api_content_type_always_json():
    resp = client.post("/check/social-profile", json=_req())
    assert resp.headers["content-type"].startswith("application/json")


def test_api_evidence_trail_mirrors_score_breakdown():
    """evidence_trail (item 84) is a normalized parallel view of score_breakdown — additive."""
    resp = client.post("/check/social-profile", json=_req(has_profile_photo=False, account_age_days=5))
    data = resp.json()
    trail = data["evidence_trail"]["items"]
    assert len(trail) == len(data["score_breakdown"])
    for item, entry in zip(trail, data["score_breakdown"]):
        assert item["signal"] == entry["flag"]
        assert item["weight"] == entry["points"]
        assert item["contributed_to_verdict"] == (entry["points"] > 0)


# ── Regression: calibration fixes for legitimate-profile false positives ──────

def test_verified_rbi_licensed_nbfc_not_flagged_as_impersonation():
    """A verified financial brand disclosing 'RBI licensed' for compliance is not scam impersonation."""
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=True,
        profile_photo_is_stock=False,
        account_age_days=900,
        follower_count=80000,
        following_count=150,
        post_count=1200,
        display_name="Acme Finance Official",
        bio_text="Official page of Acme Finance. RBI licensed NBFC. Grievance redressal as per RBI guidelines.",
        is_verified=True,
    )
    f = _flags(req)
    assert "gov_impersonation_in_bio" not in f
    assert _total(req) < _MEDIUM_SCORE


def test_normal_new_personal_account_not_scored_high():
    """A brand-new genuine user (no photo yet, following before followers reciprocate) is not HIGH risk."""
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=False,
        account_age_days=15,
        follower_count=8,
        following_count=120,
        is_verified=False,
    )
    assert _total(req) < 7
    assert "mass_following" not in _flags(req)


def test_small_legit_business_account_not_flagged_medium():
    """A small, genuinely new business account with a normal 'DM for business' bio scores low."""
    req = _SocialProfileRequest(
        platform="instagram",
        has_profile_photo=True,
        profile_photo_is_stock=False,
        account_age_days=45,
        follower_count=40,
        following_count=180,
        post_count=8,
        bio_text="DM for business inquiries and collab opportunities.",
        is_verified=False,
    )
    assert _total(req) < _MEDIUM_SCORE
    assert "low_follower_ratio" not in _flags(req)
