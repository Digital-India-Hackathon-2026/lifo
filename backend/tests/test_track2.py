"""Tests for Track 2 items 34/35/41/49/70/76/77/79/80.

This is our own test coverage for these endpoints — the Track 2
collaborator repo (kavach-track2-audit) has zero tests, confirmed by the
audit. Item 40 (safe-word verify hmac bug) is NOT retested here: our own
safevault.py already uses hmac.compare_digest correctly, so there was
nothing to fix (see AGENTS.md) — see test_vault.py for its existing
coverage.
"""
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.database as db_module
from app.core.database import Base
from app.main import app
from app.models.track2_db import B2BThreatIndicator, PairedDevice  # noqa: F401 — registers tables on Base.metadata

client = TestClient(app)


# ── Fixture: isolate DB per test ───────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect the DB session factory to a temp SQLite file so tests don't share state."""
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'test_kavach.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=test_engine)
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(db_module, "SessionLocal", test_session_local)
    yield test_session_local


@pytest.fixture(autouse=True)
def _clear_call_sessions():
    """vulnerable.py's _call_sessions is a plain in-memory dict (same shape as
    honeypot.py's _sessions) — clear it between tests, same convention as
    test_honeypot.py's own autouse fixture for its session store."""
    from app.routers.vulnerable import _call_sessions
    _call_sessions.clear()
    yield
    _call_sessions.clear()


def _report(reporter_id="reporter1", scam_type="digital_arrest", lat=12.9716, lng=77.5946, description="Fake CBI call"):
    return client.post(
        "/community/report",
        json={
            "reporter_id": reporter_id,
            "scam_type": scam_type,
            "location_lat": lat,
            "location_lng": lng,
            "description": description,
        },
    )


# ── Items 34/35: community report + heatmap reputation gate ──────────────────

def test_first_report_does_not_contribute_to_heatmap():
    resp = _report()
    assert resp.status_code == 201
    data = resp.json()
    assert data["report_count"] == 1
    assert data["contributed_to_heatmap"] is False

    heatmap = client.get("/community/heatmap")
    assert heatmap.json()["active_zones"] == []


def test_second_report_from_same_reporter_contributes_to_heatmap():
    _report()
    resp = _report()
    assert resp.status_code == 201
    data = resp.json()
    assert data["report_count"] == 2
    assert data["contributed_to_heatmap"] is True

    heatmap = client.get("/community/heatmap")
    zones = heatmap.json()["active_zones"]
    assert len(zones) == 1
    assert zones[0]["scam_type"] == "digital_arrest"


def test_different_reporters_each_start_at_report_count_one():
    resp_a = _report(reporter_id="reporterA")
    resp_b = _report(reporter_id="reporterB")
    assert resp_a.json()["report_count"] == 1
    assert resp_b.json()["report_count"] == 1
    assert resp_a.json()["contributed_to_heatmap"] is False
    assert resp_b.json()["contributed_to_heatmap"] is False


def test_report_invalid_latitude_422():
    resp = _report(lat=999.0)
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Item 41: panic trigger — paired vs unpaired ───────────────────────────────

def test_panic_trigger_unpaired_broadcasts_public():
    resp = client.post("/vulnerable/panic-trigger", json={"protected_id": "elder1", "device_source": "smartwatch"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["broadcast_success"] is True
    assert data["protector_notified_id"] is None
    assert data["action_dispatched"] == "BROADCAST_TO_PUBLIC_EMERGENCY"


def test_panic_trigger_paired_notifies_protector(isolated_db):
    session = isolated_db()
    try:
        session.add(PairedDevice(protected_id="elder2", protector_id="child2"))
        session.commit()
    finally:
        session.close()

    resp = client.post("/vulnerable/panic-trigger", json={"protected_id": "elder2", "device_source": "panic_button"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["protector_notified_id"] == "child2"
    assert data["action_dispatched"] == "IMMEDIATE_SMS_AND_PUSH_DISPATCH"


def test_panic_trigger_missing_field_422():
    resp = client.post("/vulnerable/panic-trigger", json={"protected_id": "elder1"})
    assert resp.status_code == 422


# ── Item 49: QR scanner ────────────────────────────────────────────────────────

def test_qr_scan_flags_collect_request():
    resp = client.get("/surfaces/qr/scan", params={"decoded_text": "upi://pay?pa=scammer@upi&cu=INR"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_dangerous_collect"] is True
    assert data["recommendation"] == "DO NOT SCAN - FORCED DEBIT"


def test_qr_scan_safe_when_amount_present():
    resp = client.get("/surfaces/qr/scan", params={"decoded_text": "upi://pay?pa=merchant@upi&am=500&cu=INR"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_dangerous_collect"] is False
    assert data["recommendation"] == "SAFE"


def test_qr_scan_missing_param_422():
    resp = client.get("/surfaces/qr/scan")
    assert resp.status_code == 422


# ── Item 70: freemium feature gate ────────────────────────────────────────────

def test_feature_gate_free_tier_blocks_premium_feature():
    resp = client.get("/business/sdk/feature-gate/remote_hangup", params={"tier": "free"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_granted"] is False
    assert data["requires_upgrade"] is True


def test_feature_gate_premium_tier_allows_premium_feature():
    resp = client.get("/business/sdk/feature-gate/remote_hangup", params={"tier": "premium"})
    assert resp.status_code == 200
    assert resp.json()["access_granted"] is True


def test_feature_gate_non_premium_feature_always_allowed():
    resp = client.get("/business/sdk/feature-gate/basic_scan", params={"tier": "free"})
    assert resp.status_code == 200
    assert resp.json()["access_granted"] is True


def test_feature_gate_invalid_tier_422():
    resp = client.get("/business/sdk/feature-gate/remote_hangup", params={"tier": "enterprise"})
    assert resp.status_code == 422


# ── Items 76/77: B2B verification + threat-intel feed ─────────────────────────

def test_verify_profile_high_risk_hashes_contact_number(isolated_db):
    contact = "+919876543210"
    resp = client.post(
        "/business/verify-profile",
        json={
            "platform": "matrimony_site_x",
            "profile_text": "Please pay a verification fee before we proceed with digital arrest clearance.",
            "contact_number": contact,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert len(data["flags_detected"]) >= 2
    assert contact not in resp.text

    session = isolated_db()
    try:
        rows = session.query(B2BThreatIndicator).all()
    finally:
        session.close()
    assert len(rows) == 1
    assert rows[0].sha256_hash == hashlib.sha256(contact.encode()).hexdigest()

    intel = client.get("/business/threat-intel")
    intel_data = intel.json()
    assert intel_data["indicators_count"] == 1
    assert intel_data["platforms_represented"] == ["matrimony_site_x"]
    assert contact not in intel.text


def test_verify_profile_low_risk_does_not_store_contact():
    resp = client.post(
        "/business/verify-profile",
        json={"platform": "job_portal_y", "profile_text": "Looking forward to the interview next week.", "contact_number": "+919876543211"},
    )
    assert resp.status_code == 200
    assert resp.json()["risk_level"] == "low"

    intel = client.get("/business/threat-intel")
    assert intel.json()["indicators_count"] == 0


def test_verify_profile_missing_field_422():
    resp = client.post("/business/verify-profile", json={"platform": "x"})
    assert resp.status_code == 422


# ── Items 79/80: video library + heatmap tie-in ───────────────────────────────

def test_content_library_default_language_english():
    resp = client.get("/education/content-library")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["videos"]) == 1
    assert data["videos"][0]["lang"] == "en"
    assert data["heatmap_layer_url"] == "/community/heatmap"


def test_content_library_all_languages_returns_all_videos():
    resp = client.get("/education/content-library", params={"language": "all"})
    assert resp.status_code == 200
    assert len(resp.json()["videos"]) == 3


def test_content_library_heatmap_tie_in_url_is_real_endpoint():
    resp = client.get("/education/content-library")
    heatmap_url = resp.json()["heatmap_layer_url"]
    # Confirm this is a real, live endpoint in this backend, not a stub URL.
    heatmap_resp = client.get(heatmap_url)
    assert heatmap_resp.status_code == 200
    assert "active_zones" in heatmap_resp.json()


# ── Item 37: protector-protected pairing ──────────────────────────────────────

def test_pair_devices_creates_pairing():
    resp = client.post("/vulnerable/pair-devices", json={"protected_id": "elder3", "protector_id": "child3"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["protected_id"] == "elder3"
    assert data["protector_id"] == "child3"


def test_pair_devices_repairing_updates_not_duplicates(isolated_db):
    client.post("/vulnerable/pair-devices", json={"protected_id": "elder4", "protector_id": "childA"})
    resp = client.post("/vulnerable/pair-devices", json={"protected_id": "elder4", "protector_id": "childB"})
    assert resp.status_code == 200
    assert resp.json()["protector_id"] == "childB"

    session = isolated_db()
    try:
        rows = session.query(PairedDevice).filter_by(protected_id="elder4").all()
    finally:
        session.close()
    assert len(rows) == 1
    assert rows[0].protector_id == "childB"


def test_pair_devices_missing_field_422():
    resp = client.post("/vulnerable/pair-devices", json={"protected_id": "elder5"})
    assert resp.status_code == 422


def test_panic_trigger_paired_via_real_pair_devices_endpoint():
    """End-to-end proof that panic_trigger's paired branch works through the
    real /pair-devices write path, not just DB-seeding (closes the gap left
    open in Session 27 — see AGENTS.md)."""
    client.post("/vulnerable/pair-devices", json={"protected_id": "elder6", "protector_id": "child6"})
    resp = client.post("/vulnerable/panic-trigger", json={"protected_id": "elder6", "device_source": "smartwatch"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["protector_notified_id"] == "child6"
    assert data["action_dispatched"] == "IMMEDIATE_SMS_AND_PUSH_DISPATCH"


# ── Item 38: call-state sync + remote hangup ──────────────────────────────────

def test_update_call_state_risk_detected_forces_overlay():
    resp = client.post(
        "/vulnerable/update-call-state",
        json={
            "session_id": "call1",
            "protected_id": "elder7",
            "is_call_active": True,
            "detected_scam_phrases": ["digital arrest", "cbi"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "call1"
    assert data["ui_action_required"] == "FORCE_DEESCALATION_OVERLAY"


def test_update_call_state_no_risk_no_overlay():
    resp = client.post(
        "/vulnerable/update-call-state",
        json={"session_id": "call2", "protected_id": "elder8", "is_call_active": True, "detected_scam_phrases": []},
    )
    assert resp.status_code == 200
    assert resp.json()["ui_action_required"] == "NONE"


def test_update_call_state_missing_field_422():
    resp = client.post("/vulnerable/update-call-state", json={"session_id": "call3"})
    assert resp.status_code == 422


def test_remote_hangup_terminates_session():
    client.post(
        "/vulnerable/update-call-state",
        json={"session_id": "call4", "protected_id": "elder9", "is_call_active": True, "detected_scam_phrases": ["cbi"]},
    )
    resp = client.post("/vulnerable/remote-hangup/call4")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "call4"
    assert data["current_status"] == "TERMINATED_BY_REMOTE_PROTECTOR"


def test_remote_hangup_unknown_session_404():
    resp = client.post("/vulnerable/remote-hangup/does-not-exist")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


# ── Items 44/45: WhatsApp/Telegram chat webhook ───────────────────────────────

def test_chat_webhook_whatsapp_detects_scam_patterns():
    resp = client.post(
        "/surfaces/chat-webhook/whatsapp",
        json={"sender_id": "user1", "text_payload": "This is a digital arrest, pay the verification fee immediately."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["platform"] == "whatsapp"
    assert data["risk_detected"] is True
    assert "digital_arrest" in data["matched_patterns"]
    assert "KAVACH ALERT" in data["auto_reply_action"]


def test_chat_webhook_telegram_clean_message():
    resp = client.post(
        "/surfaces/chat-webhook/telegram",
        json={"sender_id": "user2", "text_payload": "Hey, are we still meeting for lunch tomorrow?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["platform"] == "telegram"
    assert data["risk_detected"] is False
    assert data["matched_patterns"] == []


def test_chat_webhook_invalid_platform_422():
    resp = client.post("/surfaces/chat-webhook/signal", json={"sender_id": "user3", "text_payload": "hello"})
    assert resp.status_code == 422


def test_chat_webhook_missing_field_422():
    resp = client.post("/surfaces/chat-webhook/whatsapp", json={"sender_id": "user4"})
    assert resp.status_code == 422


# ── Item 46: browser extension URL check ──────────────────────────────────────

def test_extension_check_url_flags_suspicious():
    resp = client.get("/surfaces/extension/check-url", params={"url": "http://cbi-verify.fake-site.com"})
    assert resp.status_code == 200
    assert resp.json()["action"] == "BLOCK_NAVIGATION"


def test_extension_check_url_allows_clean_url():
    resp = client.get("/surfaces/extension/check-url", params={"url": "https://www.google.com"})
    assert resp.status_code == 200
    assert resp.json()["action"] == "ALLOW"


def test_extension_check_url_missing_param_422():
    resp = client.get("/surfaces/extension/check-url")
    assert resp.status_code == 422


# ── Item 48: IVR routing ───────────────────────────────────────────────────────

def test_ivr_panic_digit_routes_to_family_alert():
    resp = client.post("/surfaces/ivr/incoming", json={"caller_id": "+919876543212", "keypad_dtmf": "9"})
    assert resp.status_code == 200
    assert resp.json()["routed_action"] == "TRIGGER_FAMILY_PANIC_ALERT"


def test_ivr_other_digit_routes_to_human_operator():
    resp = client.post("/surfaces/ivr/incoming", json={"caller_id": "+919876543213", "keypad_dtmf": "1"})
    assert resp.status_code == 200
    assert resp.json()["routed_action"] == "ROUTING_TO_HUMAN_OPERATOR"


def test_ivr_missing_field_422():
    resp = client.post("/surfaces/ivr/incoming", json={"caller_id": "+919876543214"})
    assert resp.status_code == 422


# ── Item 50: smart-TV broadcast (hardcoded stub) ──────────────────────────────

def test_tv_broadcast_returns_hardcoded_status_and_says_so():
    resp = client.post("/surfaces/smart-tv/broadcast", json={"household_id": "house1", "trigger_source": "honeypot_alert"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["household"] == "house1"
    assert data["broadcast_status"] == "ACTIVE_FULLSCREEN_WARNING"
    assert "hardcoded" in data["note"].lower()


def test_tv_broadcast_missing_field_422():
    resp = client.post("/surfaces/smart-tv/broadcast", json={"household_id": "house2"})
    assert resp.status_code == 422


# ── Items 51-56: Adjacent User Segments risk evaluation ───────────────────────

def _evaluate(segment_type, payload_text):
    return client.post("/segments/evaluate", json={"segment_type": segment_type, "payload_text": payload_text})


def test_segment_nri_real_match_high_risk():
    resp = _evaluate("NRI", "This is urgent, send money immediately, my camera is broken so I can't video call, use Western Union.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["segment_type"] == "NRI"
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_segment_nri_clean_text_low_risk():
    resp = _evaluate("NRI", "Hi, just checking in, hope you're doing well this week.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "low"
    assert data["flags"] == []


def test_segment_sme_real_match_high_risk():
    resp = _evaluate("SME", "Please note our updated banking details for the new wire instructions, and process immediately before end of day.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["segment_type"] == "SME"
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_segment_sme_clean_text_low_risk():
    resp = _evaluate("SME", "Thanks for the invoice, we'll process payment on the usual schedule.")
    assert resp.status_code == 200
    assert resp.json()["risk_level"] == "low"


def test_segment_kids_real_match_high_risk():
    resp = _evaluate("KIDS", "I can give you free V-Bucks, just add me on Discord and don't tell your parents.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["segment_type"] == "KIDS"
    assert data["risk_level"] == "high"
    assert "monitor" in data["note"].lower()


def test_segment_kids_clean_text_low_risk():
    resp = _evaluate("KIDS", "Good game today, want to play again tomorrow after school?")
    assert resp.status_code == 200
    assert resp.json()["risk_level"] == "low"


def test_segment_migrant_real_match_high_risk():
    resp = _evaluate("MIGRANT", "We offer a guaranteed overseas job, no interview required, just pay the visa fee in advance.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["segment_type"] == "MIGRANT"
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_segment_migrant_clean_text_low_risk():
    resp = _evaluate("MIGRANT", "Your interview is scheduled for next Tuesday at 10am, please bring your documents.")
    assert resp.status_code == 200
    assert resp.json()["risk_level"] == "low"


def test_segment_pensioner_real_match_high_risk():
    resp = _evaluate("PENSIONER", "Your pension will stop unless you submit your life certificate immediately, EPF claim is also pending.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["segment_type"] == "PENSIONER"
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_segment_pensioner_clean_text_low_risk():
    resp = _evaluate("PENSIONER", "Your monthly pension has been credited to your account as usual.")
    assert resp.status_code == 200
    assert resp.json()["risk_level"] == "low"


def test_segment_domestic_real_match_high_risk():
    resp = _evaluate("DOMESTIC", "Please pay the police verification fee and the character certificate fee to proceed.")
    assert resp.status_code == 200
    data = resp.json()
    assert data["segment_type"] == "DOMESTIC"
    assert data["risk_level"] == "high"
    assert len(data["flags"]) >= 2


def test_segment_domestic_clean_text_low_risk():
    resp = _evaluate("DOMESTIC", "The candidate's references have been checked and everything looks fine.")
    assert resp.status_code == 200
    assert resp.json()["risk_level"] == "low"


def test_segment_invalid_segment_type_422():
    resp = _evaluate("UNKNOWN_SEGMENT", "some text")
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/json")


# ── Item 42: gamified training score logging ──────────────────────────────────

def test_training_submit_logs_score():
    resp = client.post(
        "/vulnerable/training/submit",
        json={"user_id": "trainee1", "drill_id": "drill_kyc_1", "score": 80, "completed_successfully": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "trainee1"
    assert data["drills_completed_count"] == 1
    assert data["latest_score"] == 80
    assert data["passed"] is True
    assert "does not generate" in data["note"].lower()


def test_training_submit_second_drill_increments_count():
    client.post(
        "/vulnerable/training/submit",
        json={"user_id": "trainee2", "drill_id": "drill_a", "score": 50, "completed_successfully": False},
    )
    resp = client.post(
        "/vulnerable/training/submit",
        json={"user_id": "trainee2", "drill_id": "drill_b", "score": 90, "completed_successfully": True},
    )
    assert resp.status_code == 200
    assert resp.json()["drills_completed_count"] == 2


def test_training_submit_missing_field_422():
    resp = client.post("/vulnerable/training/submit", json={"user_id": "trainee3", "drill_id": "drill_a"})
    assert resp.status_code == 422


def test_training_drill_returns_scenario_without_answer():
    resp = client.get("/vulnerable/training/drill")
    assert resp.status_code == 200
    data = resp.json()
    assert data["drill_id"].startswith("drill_")
    assert data["scenario_type"]
    assert data["scenario_text"]
    assert len(data["options"]) >= 2
    assert "correct_answer" not in data
    assert "explanation" not in data


def test_training_answer_correct_logs_real_attempt():
    resp = client.post(
        "/vulnerable/training/answer",
        json={
            "user_id": "trainee_correct",
            "drill_id": "drill_digital_arrest_1",
            "selected_answer": (
                "This is a 'Digital Arrest' scam — hang up, do not pay anything, and verify "
                "independently via cybercrime.gov.in or 1930."
            ),
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["correct"] is True
    assert data["explanation"]
    assert data["training_score"]["user_id"] == "trainee_correct"
    assert data["training_score"]["drills_completed_count"] == 1
    assert data["training_score"]["latest_score"] == 100
    assert data["training_score"]["passed"] is True
    assert "not a" in data["training_score"]["note"].lower() and "self-report" in data["training_score"]["note"].lower()
    assert "does not generate" not in data["training_score"]["note"].lower()


def test_training_answer_incorrect_logs_failed_attempt():
    resp = client.post(
        "/vulnerable/training/answer",
        json={
            "user_id": "trainee_wrong",
            "drill_id": "drill_kyc_1",
            "selected_answer": "Click the link immediately since your account is about to be blocked.",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["correct"] is False
    assert data["explanation"]
    assert data["training_score"]["latest_score"] == 0
    assert data["training_score"]["passed"] is False


def test_training_answer_invalid_drill_id_404():
    resp = client.post(
        "/vulnerable/training/answer",
        json={"user_id": "trainee_x", "drill_id": "drill_does_not_exist", "selected_answer": "anything"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]


# ── Item 47: smart speaker voice-command webhook ──────────────────────────────

def test_smart_speaker_panic_trigger_unpaired():
    resp = client.post(
        "/surfaces/smart-speaker/command",
        json={"device_id": "speaker_unpaired1", "transcribed_command": "help I need emergency assistance"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action_taken"] == "PANIC_TRIGGERED"
    assert "public emergency" in data["spoken_response"].lower()


def test_smart_speaker_panic_trigger_paired():
    client.post("/vulnerable/pair-devices", json={"protected_id": "speaker_paired1", "protector_id": "childX"})
    resp = client.post(
        "/surfaces/smart-speaker/command",
        json={"device_id": "speaker_paired1", "transcribed_command": "sos please help"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action_taken"] == "PANIC_TRIGGERED"
    assert "family" in data["spoken_response"].lower()


def test_smart_speaker_risk_check_high():
    resp = client.post(
        "/surfaces/smart-speaker/command",
        json={"device_id": "speaker2", "transcribed_command": "This is a digital arrest, you must pay immediately."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action_taken"] == "RISK_CHECK"
    assert data["risk_level"] == "high"
    assert "scam" in data["spoken_response"].lower()


def test_smart_speaker_risk_check_low():
    resp = client.post(
        "/surfaces/smart-speaker/command",
        json={"device_id": "speaker3", "transcribed_command": "what's the weather today"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action_taken"] == "RISK_CHECK"
    assert data["risk_level"] == "low"


def test_smart_speaker_missing_field_422():
    resp = client.post("/surfaces/smart-speaker/command", json={"device_id": "speaker4"})
    assert resp.status_code == 422


# ── Item 69: SDK API key issue + validate ──────────────────────────────────────

def test_sdk_issue_key_returns_raw_key_once():
    resp = client.post("/business/sdk/keys", json={"tier": "premium"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["api_key"]) > 10
    assert data["tier"] == "premium"


def test_sdk_validate_key_success():
    issued = client.post("/business/sdk/keys", json={"tier": "free"}).json()
    resp = client.get("/business/sdk/validate", params={"api_key": issued["api_key"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["tier"] == "free"


def test_sdk_validate_unknown_key_401():
    resp = client.get("/business/sdk/validate", params={"api_key": "totally-bogus-key-value"})
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/json")


def test_sdk_key_hashed_not_stored_raw(isolated_db):
    from app.models.track2_db import SDKApiKey

    issued = client.post("/business/sdk/keys", json={"tier": "premium"}).json()
    raw_key = issued["api_key"]

    session = isolated_db()
    try:
        rows = session.query(SDKApiKey).all()
    finally:
        session.close()
    assert len(rows) == 1
    assert rows[0].key_hash != raw_key
    assert rows[0].key_hash == hashlib.sha256(raw_key.encode()).hexdigest()


def test_sdk_issue_invalid_tier_422():
    resp = client.post("/business/sdk/keys", json={"tier": "enterprise"})
    assert resp.status_code == 422


# ── Item 81: real annual report ────────────────────────────────────────────────

def test_annual_report_zero_counts_when_no_data():
    resp = client.get("/education/annual-report")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_heatmap_incidents_logged"] == 0
    assert data["total_b2b_threat_indicators_flagged"] == 0
    assert "omitted" in data["note"].lower()


def test_annual_report_reflects_real_counts():
    _report(reporter_id="annual_reporter")
    _report(reporter_id="annual_reporter")  # 2nd report contributes to heatmap

    client.post(
        "/business/verify-profile",
        json={
            "platform": "annual_platform",
            "profile_text": "Please pay a verification fee before we proceed with digital arrest clearance.",
            "contact_number": "+919876500000",
        },
    )

    resp = client.get("/education/annual-report")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_heatmap_incidents_logged"] == 1
    assert data["total_b2b_threat_indicators_flagged"] == 1
    assert data["year"] >= 2026


# ── Item 39: target_audience tag on content-library videos ────────────────────

def test_content_library_videos_have_target_audience_field():
    resp = client.get("/education/content-library", params={"language": "all"})
    assert resp.status_code == 200
    videos = resp.json()["videos"]
    assert len(videos) == 3
    assert all(v["target_audience"] == "general" for v in videos)


def test_content_library_filter_by_target_audience_elderly_currently_empty():
    resp = client.get("/education/content-library", params={"language": "all", "target_audience": "elderly"})
    assert resp.status_code == 200
    assert resp.json()["videos"] == []
