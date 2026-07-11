"""
Tests for /honeypot/start, /honeypot/converse, /honeypot/report.

Unit tests:    All STT/Persona/TTS calls are mocked — no network or model access needed.
Integration:   Require real services:
  - test_integration_tts_*         → needs GOOGLE_APPLICATION_CREDENTIALS
  - test_integration_full_pipeline → needs GOOGLE_APPLICATION_CREDENTIALS + GOOGLE_CLOUD_PROJECT
                                     + faster-whisper base model in HF cache
  Run: GOOGLE_APPLICATION_CREDENTIALS=... uv run python -m pytest tests/test_honeypot.py -v
"""
import base64
import io
import os
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.honeypot import _sessions
from app.services.honeypot_pipeline import (
    contains_self_disclosure,
    extract_signals,
)

_HF_CACHE = Path.home() / ".cache" / "huggingface" / "hub"
_whisper_cached = (_HF_CACHE / "models--Systran--faster-whisper-base").exists()

requires_gcp = pytest.mark.skipif(
    not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    reason="GOOGLE_APPLICATION_CREDENTIALS not set",
)
requires_full_pipeline = pytest.mark.skipif(
    not os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    or not os.getenv("GOOGLE_CLOUD_PROJECT")
    or not _whisper_cached,
    reason="Requires GOOGLE_APPLICATION_CREDENTIALS + GOOGLE_CLOUD_PROJECT + cached faster-whisper base model",
)

JSON_CT = "application/json"
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def clear_sessions():
    """Isolate session state between tests."""
    _sessions.clear()
    yield
    _sessions.clear()


def _wav_bytes(duration_s: int = 2) -> bytes:
    t = np.linspace(0, duration_s, 16_000 * duration_s, endpoint=False)
    pcm = (np.sin(2 * np.pi * 440 * t) * 16_383).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16_000)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def _assert_json(resp, expected_status: int) -> dict:
    assert resp.status_code == expected_status, resp.text
    assert resp.headers["content-type"].startswith(JSON_CT)
    return resp.json()


def _start_session() -> str:
    body = _assert_json(client.post("/honeypot/start"), 200)
    return body["session_id"]


def _converse(session_id: str, transcript_mock: str, reply_mock: str, audio_mock: str | None = "AUDIO_B64") -> dict:
    """One mocked turn through the pipeline."""
    with patch("app.routers.honeypot.transcribe_audio", return_value=(transcript_mock, None)), \
         patch("app.routers.honeypot.generate_persona_reply", return_value=(reply_mock, None)), \
         patch("app.routers.honeypot.synthesize_speech", return_value=(audio_mock, None if audio_mock else "TTS unavailable")):
        return _assert_json(
            client.post(
                "/honeypot/converse",
                data={"session_id": session_id},
                files={"file": ("turn.wav", _wav_bytes(), "audio/wav")},
            ),
            200,
        )


# ── /honeypot/start ───────────────────────────────────────────────────────────

def test_start_session_returns_session_id():
    body = _assert_json(client.post("/honeypot/start"), 200)
    assert "session_id" in body
    assert len(body["session_id"]) == 36  # UUID4 format


def test_start_session_creates_distinct_ids():
    a = client.post("/honeypot/start").json()["session_id"]
    b = client.post("/honeypot/start").json()["session_id"]
    assert a != b


# ── /honeypot/converse — schema and basic flow ────────────────────────────────

def test_converse_returns_full_schema():
    sid = _start_session()
    body = _converse(sid, "You are under digital arrest", "Haan ji, ek minute...")
    assert body["session_id"] == sid
    assert body["turn"] == 1
    assert body["transcript"] == "You are under digital arrest"
    assert body["persona_reply_text"] == "Haan ji, ek minute..."
    assert body["persona_reply_audio"] == "AUDIO_B64"
    assert "signals_this_turn" in body
    assert "cumulative_intel" in body
    assert len(body["stage_log"]) == 4
    assert body["stage_log"][0].startswith("STT: ok")
    assert body["stage_log"][1] == "Persona: ok"
    assert body["stage_log"][2] == "TTS: ok"
    assert body["stage_log"][3].startswith("Extraction: ok")


def test_converse_unknown_session_returns_404():
    body = _assert_json(
        client.post(
            "/honeypot/converse",
            data={"session_id": "00000000-0000-0000-0000-000000000000"},
            files={"file": ("t.wav", _wav_bytes(), "audio/wav")},
        ),
        404,
    )
    assert "error" in body


def test_converse_wrong_audio_type_returns_415():
    sid = _start_session()
    body = _assert_json(
        client.post(
            "/honeypot/converse",
            data={"session_id": sid},
            files={"file": ("t.mp3", b"data", "audio/mpeg")},
        ),
        415,
    )
    assert "error" in body


def test_converse_oversized_returns_413():
    sid = _start_session()
    body = _assert_json(
        client.post(
            "/honeypot/converse",
            data={"session_id": sid},
            files={"file": ("big.wav", b"x" * (25 * 1024 * 1024 + 1), "audio/wav")},
        ),
        413,
    )
    assert "error" in body


# ── Graceful degradation ──────────────────────────────────────────────────────

def test_stt_failure_degrades_gracefully():
    sid = _start_session()
    with patch("app.routers.honeypot.transcribe_audio", return_value=(None, "ffmpeg missing")):
        body = _assert_json(
            client.post(
                "/honeypot/converse",
                data={"session_id": sid},
                files={"file": ("t.wav", _wav_bytes(), "audio/wav")},
            ),
            200,
        )
    assert body["transcript"] is None
    assert body["persona_reply_text"] is None
    assert body["persona_reply_audio"] is None
    assert "STT: FAILED" in body["stage_log"][0]
    assert "skipped" in body["stage_log"][1]
    assert "skipped" in body["stage_log"][2]


def test_gemini_failure_degrades_gracefully():
    sid = _start_session()
    with patch("app.routers.honeypot.transcribe_audio", return_value=("Hello scammer", None)), \
         patch("app.routers.honeypot.generate_persona_reply", return_value=(None, "quota exceeded")):
        body = _assert_json(
            client.post(
                "/honeypot/converse",
                data={"session_id": sid},
                files={"file": ("t.wav", _wav_bytes(), "audio/wav")},
            ),
            200,
        )
    assert body["transcript"] == "Hello scammer"
    assert body["persona_reply_text"] is None
    assert body["persona_reply_audio"] is None
    assert "Persona: FAILED" in body["stage_log"][1]
    assert "skipped" in body["stage_log"][2]


def test_tts_failure_degrades_gracefully():
    sid = _start_session()
    with patch("app.routers.honeypot.transcribe_audio", return_value=("Pay now", None)), \
         patch("app.routers.honeypot.generate_persona_reply", return_value=("Haan ji", None)), \
         patch("app.routers.honeypot.synthesize_speech", return_value=(None, "API disabled")):
        body = _assert_json(
            client.post(
                "/honeypot/converse",
                data={"session_id": sid},
                files={"file": ("t.wav", _wav_bytes(), "audio/wav")},
            ),
            200,
        )
    assert body["transcript"] == "Pay now"
    assert body["persona_reply_text"] == "Haan ji"
    assert body["persona_reply_audio"] is None
    assert "TTS: FAILED" in body["stage_log"][2]


# ── Multi-turn state accumulation ─────────────────────────────────────────────

def test_full_3_turn_conversation_cumulative_intel_grows():
    """
    3 turns each contribute a distinct UPI ID.
    cumulative_intel must grow turn-by-turn and contain all 3 by the end.
    """
    sid = _start_session()

    turn1_transcript = "Send Rs 5000 to scam1@okicici"
    turn2_transcript = "Or use scam2@ybl for payment"
    turn3_transcript = "This is a digital arrest case, pay scam3@paytm within 24 hours"

    body1 = _converse(sid, turn1_transcript, "Haan ji, ek minute...")
    assert body1["turn"] == 1
    assert "scam1@okicici" in body1["signals_this_turn"]["upi_ids"]
    assert len(body1["cumulative_intel"]["upi_ids"]) == 1

    body2 = _converse(sid, turn2_transcript, "Theek hai theek hai...")
    assert body2["turn"] == 2
    assert "scam2@ybl" in body2["signals_this_turn"]["upi_ids"]
    assert len(body2["cumulative_intel"]["upi_ids"]) == 2

    body3 = _converse(sid, turn3_transcript, "OTP did not come ji...")
    assert body3["turn"] == 3
    assert "scam3@paytm" in body3["signals_this_turn"]["upi_ids"]
    cum = body3["cumulative_intel"]
    assert len(cum["upi_ids"]) == 3
    assert set(cum["upi_ids"]) == {"scam1@okicici", "scam2@ybl", "scam3@paytm"}
    # digital_arrest scam phrase from turn3 transcript
    assert "digital_arrest" in cum["scripted_phrases"]


def test_duplicate_signals_not_double_counted():
    """Same UPI ID appearing in two turns should appear once in cumulative."""
    sid = _start_session()
    _converse(sid, "Pay to dup@okicici now", "Ek minute...")
    body = _converse(sid, "I said pay dup@okicici", "Haan ji...")
    assert body["cumulative_intel"]["upi_ids"].count("dup@okicici") == 1


# ── /honeypot/report ──────────────────────────────────────────────────────────

def test_report_returns_full_history():
    sid = _start_session()
    _converse(sid, "Turn one text", "Reply one")
    _converse(sid, "Turn two text", "Reply two")
    _converse(sid, "Turn three text", "Reply three")

    body = _assert_json(client.get(f"/honeypot/report/{sid}"), 200)
    assert body["session_id"] == sid
    assert body["turn_count"] == 3
    assert len(body["turn_history"]) == 3
    assert body["turn_history"][0]["turn"] == 1
    assert body["turn_history"][0]["transcript"] == "Turn one text"
    assert body["turn_history"][2]["persona_reply"] == "Reply three"


def test_report_unknown_session_returns_404():
    body = _assert_json(
        client.get("/honeypot/report/00000000-0000-0000-0000-000000000000"),
        404,
    )
    assert "error" in body


# ── Persona self-disclosure regression ───────────────────────────────────────

_GOOD_REPLIES = [
    "Haan ji, ek minute... I did not catch the number. Can you repeat?",
    "Theek hai theek hai, but my son handles the internet banking, not me.",
    "Arrey bhai, OTP is not coming on my phone. Battery is also low today.",
    "I am Ramesh Kumar. Please give me your employee ID and callback number ji.",
]
_BAD_REPLIES = [
    "As an AI language model, I cannot complete this transaction.",
    "I'm Gemini, how can I assist you today?",
    "I am an AI assistant designed to help users.",
    "As an AI, I don't have access to real bank accounts.",
]


def test_persona_no_self_disclosure():
    """Regression: Ramesh Kumar character replies must not contain AI identity disclosures."""
    for reply in _GOOD_REPLIES:
        assert not contains_self_disclosure(reply), (
            f"False positive — good reply incorrectly flagged: {reply!r}"
        )
    for reply in _BAD_REPLIES:
        assert contains_self_disclosure(reply), (
            f"Missed self-disclosure: {reply!r}"
        )


# ── extract_signals unit tests ────────────────────────────────────────────────

def test_extract_signals_detects_upi():
    signals = extract_signals("Send money to cbi.verify@okicici now.")
    assert "cbi.verify@okicici" in signals["upi_ids"]


def test_extract_signals_detects_phone():
    signals = extract_signals("Call us back on +91 9876543210 for confirmation.")
    assert any("9876543210" in p for p in signals["phone_numbers"])


def test_extract_signals_detects_bank_account():
    signals = extract_signals("Deposit to Account No: 98765432101 immediately.")
    assert "98765432101" in signals["bank_accounts"]


def test_extract_signals_detects_scripted_phrase():
    signals = extract_signals("This is a digital arrest situation, pay the bail amount.")
    assert "digital_arrest" in signals["scripted_phrases"]
    assert "bail_payment" in signals["scripted_phrases"]


def test_extract_signals_no_false_positives_on_plain_numbers():
    """Plain invoice/reference numbers without anchor keyword must not trigger bank_account."""
    signals = extract_signals("Invoice #98765432101. Ref: 123456789. Date: 01-Jan-2026.")
    assert signals["bank_accounts"] == []
    assert signals["scripted_phrases"] == []
    assert signals["upi_ids"] == []


def test_extract_signals_upi_stt_normalization():
    """STT transcribes 'user@domain' as 'user at domain' — normalize before matching."""
    signals = extract_signals(
        "pay verification fee immediately on UPICBI.verify at okicici within 24 hours"
    )
    assert "UPICBI.verify@okicici" in signals["upi_ids"]


# ── Integration tests (real GCP / Gemini / Whisper) ──────────────────────────


def _make_scammer_audio() -> bytes:
    """Synthesize scammer speech as LINEAR16 WAV using GCP TTS (en-IN-Standard-C)."""
    from google.cloud import texttospeech  # type: ignore[import]

    tc = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(
        text=(
            "Sir this is CBI officer. Digital arrest case registered against you. "
            "Pay verification fee immediately on UPI cbi.verify@okicici "
            "within 24 hours or we will cancel your Aadhaar card."
        )
    )
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-IN", name="en-IN-Standard-C"
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )
    resp = tc.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    return resp.audio_content  # WAV bytes (RIFF header included in LINEAR16 output)


@requires_gcp
def test_integration_tts_synthesizes_real_mp3():
    """TTS integration: synthesize_speech() returns valid base64 MP3 from live GCP TTS API."""
    import app.services.honeypot_pipeline as _pipeline

    _pipeline._tts_client = None
    _pipeline.load_tts_client()
    assert _pipeline._tts_client is not None, "TTS client failed to load with current credentials"

    b64, err = _pipeline.synthesize_speech("Haan ji, ek minute. Can you give me your employee ID number?")
    assert err is None, f"TTS error: {err}"
    assert b64 is not None

    mp3 = base64.b64decode(b64)
    assert len(mp3) > 1000, f"MP3 suspiciously small: {len(mp3)} bytes"
    # Valid MPEG sync word (0xFF + high 3 bits of second byte set) or ID3 header
    assert (mp3[0] == 0xFF and (mp3[1] & 0xE0) == 0xE0) or mp3[:3] == b"ID3", (
        f"Not a valid MP3 — header bytes: {mp3[:4].hex()}"
    )


@requires_full_pipeline
def test_integration_honeypot_full_pipeline():
    """End-to-end: real WAV in → STT → Gemini persona → TTS → base64 MP3 out.

    All 4 stage_log entries must report success. persona_reply_audio must be non-null.
    Scammer speech contains 'cbi.verify@okicici' — at least one UPI signal should fire.
    """
    scammer_wav = _make_scammer_audio()

    with TestClient(app) as live:
        start_body = live.post("/honeypot/start").json()
        assert "session_id" in start_body, f"Start failed: {start_body}"
        sid = start_body["session_id"]

        resp = live.post(
            "/honeypot/converse",
            data={"session_id": sid},
            files={"file": ("scammer.wav", scammer_wav, "audio/wav")},
        )

    assert resp.status_code == 200, f"converse returned {resp.status_code}: {resp.text}"
    body = resp.json()

    assert body["transcript"] is not None, f"STT failed — stage_log: {body['stage_log']}"
    assert body["persona_reply_text"] is not None, f"Persona failed — stage_log: {body['stage_log']}"
    assert body["persona_reply_audio"] is not None, f"TTS failed — stage_log: {body['stage_log']}"

    log = body["stage_log"]
    assert len(log) == 4, f"Expected 4 stage_log entries, got {len(log)}: {log}"
    assert log[0].startswith("STT: ok"), f"Stage 0 not ok: {log[0]}"
    assert log[1] == "Persona: ok", f"Stage 1 not ok: {log[1]}"
    assert log[2] == "TTS: ok", f"Stage 2 not ok: {log[2]}"
    assert log[3].startswith("Extraction: ok"), f"Stage 3 not ok: {log[3]}"

    mp3 = base64.b64decode(body["persona_reply_audio"])
    assert len(mp3) > 1000, f"Persona audio too small: {len(mp3)} bytes"
    assert (mp3[0] == 0xFF and (mp3[1] & 0xE0) == 0xE0) or mp3[:3] == b"ID3", (
        f"Persona audio is not valid MP3 — header: {mp3[:4].hex()}"
    )

    cum = body["cumulative_intel"]
    assert len(cum["upi_ids"]) > 0 or len(body["signals_this_turn"]["scripted_phrases"]) > 0, (
        f"No signals extracted from scammer speech — transcript was: {body['transcript']!r}"
    )
