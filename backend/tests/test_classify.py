"""
Tests for /classify/image, /classify/video, /classify/audio.

Unit tests:   _image_classifier / _audio_classifier patched — no model download needed.
Integration:  require models in local HF cache.
  Download:   cd backend && uv run python scripts/download_models.py
  Run all:    uv run python -m pytest tests/ -v
  Run unit:   uv run python -m pytest tests/ -v -k "not integration"
  Run integ:  uv run python -m pytest tests/ -v -k integration
"""
import io
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.routers.classify import AUDIO_MODEL_ID, AUDIO_SAMPLE_RATE, IMAGE_MODEL_ID

DISCLAIMER = (
    "This tool reduces risk but cannot guarantee 100% accuracy. "
    "Always verify through a second, independent channel before sending money."
)
JSON_CT = "application/json"

# Module-level client — no context manager so lifespan does NOT trigger.
# Unit tests patch _image_classifier / _audio_classifier per-test.
client = TestClient(app, raise_server_exceptions=False)

# Mock return values matching each model's id2label
FAKE_IMAGE = [{"label": "Fake", "score": 0.93}, {"label": "Real", "score": 0.07}]
REAL_IMAGE = [{"label": "Real", "score": 0.91}, {"label": "Fake", "score": 0.09}]
SPOOF_AUDIO = [{"label": "fake", "score": 0.88}, {"label": "real", "score": 0.12}]
GENUINE_AUDIO = [{"label": "real", "score": 0.84}, {"label": "fake", "score": 0.16}]

# 5-second non-silent audio array for mocking _load_audio
_FAKE_AUDIO_NP = np.ones(AUDIO_SAMPLE_RATE * 5, dtype=np.float32) * 0.3


def _img_bytes(color: tuple = (100, 149, 237), fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, format=fmt)
    return buf.getvalue()


def _wav_bytes(duration_s: int = 4, freq: int = 440, sample_rate: int = 16_000) -> bytes:
    """Generate a minimal sine-wave WAV using only stdlib — no extra deps in tests."""
    t = np.linspace(0, duration_s, sample_rate * duration_s, endpoint=False)
    pcm = (np.sin(2 * np.pi * freq * t) * 16_383).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def _assert_json(resp, expected_status: int) -> dict:
    assert resp.status_code == expected_status
    assert resp.headers["content-type"].startswith(JSON_CT)
    return resp.json()


def _is_model_cached(*name_fragments: str) -> bool:
    cache = Path.home() / ".cache" / "huggingface" / "hub"
    if not cache.exists():
        return False
    return any(
        all(frag in p.name for frag in name_fragments) for p in cache.iterdir()
    )


requires_image_model = pytest.mark.skipif(
    not _is_model_cached("dima806"),
    reason="Image model not in HF cache — run: uv run python scripts/download_models.py",
)
requires_audio_model = pytest.mark.skipif(
    not _is_model_cached("Gustking"),
    reason="Audio model not in HF cache — run: uv run python scripts/download_models.py",
)


# ── /classify/image — unit tests ─────────────────────────────────────────────

def test_image_classified_as_ai_generated():
    with patch("app.routers.classify._image_classifier", MagicMock(return_value=FAKE_IMAGE)):
        body = _assert_json(
            client.post("/classify/image", files={"file": ("a.jpg", _img_bytes((200, 100, 50)), "image/jpeg")}),
            200,
        )
    assert body["verdict"] == "ai_generated"
    assert abs(body["confidence_score"] - 0.93) < 0.001
    assert body["disclaimer"] == DISCLAIMER
    assert "note" in body
    assert body["model"] == IMAGE_MODEL_ID


def test_image_classified_as_real():
    with patch("app.routers.classify._image_classifier", MagicMock(return_value=REAL_IMAGE)):
        body = _assert_json(
            client.post("/classify/image", files={"file": ("b.jpg", _img_bytes((50, 150, 200)), "image/jpeg")}),
            200,
        )
    assert body["verdict"] == "real"
    assert abs(body["confidence_score"] - 0.91) < 0.001


def test_image_corrupted_file_returns_400():
    body = _assert_json(
        client.post("/classify/image", files={"file": ("bad.jpg", b"not_an_image", "image/jpeg")}),
        400,
    )
    assert "error" in body


def test_image_wrong_content_type_returns_415():
    body = _assert_json(
        client.post("/classify/image", files={"file": ("doc.txt", b"hello", "text/plain")}),
        415,
    )
    assert "error" in body


def test_image_oversized_returns_413():
    body = _assert_json(
        client.post("/classify/image", files={"file": ("big.jpg", b"x" * (10 * 1024 * 1024 + 1), "image/jpeg")}),
        413,
    )
    assert "error" in body


# ── /classify/video — unit tests ─────────────────────────────────────────────

def _mock_cap(n_frames: int = 4) -> MagicMock:
    cap = MagicMock()
    cap.isOpened.return_value = True
    cap.get.return_value = float(n_frames)
    cap.read.return_value = (True, np.zeros((64, 64, 3), dtype=np.uint8))
    return cap


def test_video_returns_correct_schema():
    with patch("app.routers.classify._image_classifier", MagicMock(return_value=FAKE_IMAGE)), \
         patch("app.routers.classify.cv2.VideoCapture", return_value=_mock_cap()):
        body = _assert_json(
            client.post("/classify/video", files={"file": ("v.mp4", b"bytes", "video/mp4")}),
            200,
        )
    assert body["verdict"] == "ai_generated"
    assert body["disclaimer"] == DISCLAIMER
    assert "frames_sampled" in body
    sf = body["most_suspicious_frame"]
    assert "frame_index" in sf and "fake_score" in sf


def test_video_wrong_content_type_returns_415():
    body = _assert_json(
        client.post("/classify/video", files={"file": ("f.txt", b"hello", "text/plain")}),
        415,
    )
    assert "error" in body


def test_video_oversized_returns_413():
    body = _assert_json(
        client.post("/classify/video", files={"file": ("big.mp4", b"x" * (100 * 1024 * 1024 + 1), "video/mp4")}),
        413,
    )
    assert "error" in body


def test_video_unreadable_returns_400():
    bad_cap = MagicMock()
    bad_cap.isOpened.return_value = False
    with patch("app.routers.classify.cv2.VideoCapture", return_value=bad_cap):
        body = _assert_json(
            client.post("/classify/video", files={"file": ("bad.mp4", b"garbage", "video/mp4")}),
            400,
        )
    assert "error" in body


def test_video_zero_frames_returns_400():
    cap = MagicMock()
    cap.isOpened.return_value = True
    cap.get.return_value = 0.0
    with patch("app.routers.classify.cv2.VideoCapture", return_value=cap):
        body = _assert_json(
            client.post("/classify/video", files={"file": ("empty.mp4", b"x", "video/mp4")}),
            400,
        )
    assert "error" in body


# ── /classify/audio — unit tests ─────────────────────────────────────────────

def test_audio_classified_as_spoof():
    with patch("app.routers.classify._audio_classifier", MagicMock(return_value=SPOOF_AUDIO)), \
         patch("app.routers.classify._load_audio", return_value=_FAKE_AUDIO_NP):
        body = _assert_json(
            client.post("/classify/audio", files={"file": ("a.wav", b"dummy", "audio/wav")}),
            200,
        )
    assert body["verdict"] == "spoof"
    assert abs(body["confidence_score"] - 0.88) < 0.001
    assert body["disclaimer"] == DISCLAIMER
    assert "note" in body
    assert "anomaly_timestamp" in body
    assert body["model"] == AUDIO_MODEL_ID


def test_audio_classified_as_genuine():
    with patch("app.routers.classify._audio_classifier", MagicMock(return_value=GENUINE_AUDIO)), \
         patch("app.routers.classify._load_audio", return_value=_FAKE_AUDIO_NP):
        body = _assert_json(
            client.post("/classify/audio", files={"file": ("b.wav", b"dummy", "audio/wav")}),
            200,
        )
    assert body["verdict"] == "genuine"
    assert abs(body["confidence_score"] - 0.84) < 0.001


def test_audio_wrong_content_type_returns_415():
    body = _assert_json(
        client.post("/classify/audio", files={"file": ("f.mp3", b"hello", "audio/mpeg")}),
        415,
    )
    assert "error" in body


def test_audio_oversized_returns_413():
    body = _assert_json(
        client.post("/classify/audio", files={"file": ("big.wav", b"x" * (25 * 1024 * 1024 + 1), "audio/wav")}),
        413,
    )
    assert "error" in body


def test_audio_corrupted_returns_400():
    # _load_audio wraps torchaudio failures as HTTPException(400) — match that here
    from fastapi import HTTPException as FastHTTPException
    with patch("app.routers.classify._load_audio", side_effect=FastHTTPException(status_code=400, detail="Cannot decode")):
        body = _assert_json(
            client.post("/classify/audio", files={"file": ("bad.wav", b"garbage", "audio/wav")}),
            400,
        )
    assert "error" in body


def test_audio_silent_returns_400():
    silent = np.zeros(AUDIO_SAMPLE_RATE * 3, dtype=np.float32)
    with patch("app.routers.classify._load_audio", return_value=silent):
        body = _assert_json(
            client.post("/classify/audio", files={"file": ("silent.wav", b"dummy", "audio/wav")}),
            400,
        )
    assert "error" in body


def test_audio_anomaly_timestamp_is_float():
    with patch("app.routers.classify._audio_classifier", MagicMock(return_value=SPOOF_AUDIO)), \
         patch("app.routers.classify._load_audio", return_value=_FAKE_AUDIO_NP):
        body = _assert_json(
            client.post("/classify/audio", files={"file": ("c.wav", b"dummy", "audio/wav")}),
            200,
        )
    assert isinstance(body["anomaly_timestamp"], (int, float))
    assert body["anomaly_timestamp"] >= 0.0


# ── Integration tests — require real models ───────────────────────────────────

@requires_image_model
def test_integration_image_schema_with_real_model():
    with TestClient(app) as live:
        body = _assert_json(
            live.post("/classify/image", files={"file": ("t.jpg", _img_bytes((180, 140, 120)), "image/jpeg")}),
            200,
        )
    assert body["verdict"] in ("real", "ai_generated")
    assert 0.0 <= body["confidence_score"] <= 1.0
    assert body["disclaimer"] == DISCLAIMER
    assert body["model"] == IMAGE_MODEL_ID


@requires_image_model
def test_integration_image_known_real_and_fake():
    real_img = _img_bytes(color=(100, 149, 237))
    buf = io.BytesIO()
    Image.fromarray(np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)).save(buf, format="JPEG")
    noisy_img = buf.getvalue()

    with TestClient(app) as live:
        for label, data in [("real-like", real_img), ("noisy", noisy_img)]:
            body = _assert_json(
                live.post("/classify/image", files={"file": (f"{label}.jpg", data, "image/jpeg")}),
                200,
            )
            assert body["verdict"] in ("real", "ai_generated"), f"{label}: unexpected verdict"
            assert 0.0 <= body["confidence_score"] <= 1.0


@requires_audio_model
def test_integration_audio_schema_with_real_model():
    """Upload a real sine-wave WAV and confirm the full response schema."""
    wav_data = _wav_bytes(duration_s=4)
    with TestClient(app) as live:
        body = _assert_json(
            live.post("/classify/audio", files={"file": ("test.wav", wav_data, "audio/wav")}),
            200,
        )
    assert body["verdict"] in ("genuine", "spoof")
    assert 0.0 <= body["confidence_score"] <= 1.0
    assert body["disclaimer"] == DISCLAIMER
    assert "anomaly_timestamp" in body
    assert body["model"] == AUDIO_MODEL_ID
    assert "note" in body
