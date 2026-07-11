"""
/classify/image, /classify/video, /classify/audio endpoints.

Image/video model: dima806/deepfake_vs_real_image_detection (ViT, Apache-2.0)
Audio model:       Gustking/wav2vec2-large-xlsr-deepfake-audio-classification (wav2vec2-large-xlsr, Apache-2.0)
Both loaded once at startup via lifespan in main.py.
"""
import io
import os
import tempfile
from typing import Optional

import cv2
import numpy as np
import soundfile as sf
import torch
import torchaudio.functional as TAF
from PIL import Image, UnidentifiedImageError
from fastapi import APIRouter, File, HTTPException, UploadFile
from transformers import pipeline as hf_pipeline

from app.models.responses import (
    CONFIDENCE_NOTE,
    DISCLAIMER,
    ClassifyAudioResponse,
    ClassifyImageResponse,
    ClassifyVideoResponse,
    SuspiciousFrame,
)

router = APIRouter(prefix="/classify", tags=["classify"])

IMAGE_MODEL_ID = "dima806/deepfake_vs_real_image_detection"
AUDIO_MODEL_ID = "Gustking/wav2vec2-large-xlsr-deepfake-audio-classification"

# Included in every audio response — explains softmax caveat, window resolution,
# and the known benchmark gap (ASVspoof2019 vs modern voice cloning).
AUDIO_CONFIDENCE_NOTE = (
    "Raw softmax output for the predicted class (0–1); not a calibrated probability. "
    "anomaly_timestamp is the start (in seconds) of the most suspicious 3-second audio "
    "window (window-level resolution, not sample-precise). "
    "Trained on ASVspoof2019 LA — performance on modern voice-cloning systems may be lower."
)

MAX_IMAGE_BYTES = 10 * 1024 * 1024    # 10 MB
MAX_VIDEO_BYTES = 100 * 1024 * 1024   # 100 MB
MAX_AUDIO_BYTES = 25 * 1024 * 1024    # 25 MB

MAX_VIDEO_FRAMES = 16
MAX_AUDIO_CHUNKS = 10

AUDIO_SAMPLE_RATE = 16_000
AUDIO_CHUNK_SECONDS = 3
AUDIO_CHUNK_SAMPLES = AUDIO_CHUNK_SECONDS * AUDIO_SAMPLE_RATE   # 48,000
AUDIO_SILENCE_THRESHOLD = 1e-4  # RMS below this → treat as silent

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}
ALLOWED_VIDEO_TYPES = {
    "video/mp4", "video/avi", "video/quicktime",
    "video/x-msvideo", "video/x-matroska",
}
ALLOWED_AUDIO_TYPES = {
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/flac", "audio/x-flac",
    "audio/ogg",
}

_image_classifier = None
_audio_classifier = None


def load_image_classifier() -> None:
    """Load image/video deepfake classifier. Called once at startup."""
    global _image_classifier
    if _image_classifier is not None:
        return
    _image_classifier = hf_pipeline("image-classification", model=IMAGE_MODEL_ID)


def load_audio_classifier() -> None:
    """Load audio spoof classifier. Called once at startup; fault-tolerant so server still starts."""
    global _audio_classifier
    if _audio_classifier is not None:
        return
    try:
        _audio_classifier = hf_pipeline("audio-classification", model=AUDIO_MODEL_ID)
    except Exception as exc:
        # Server continues without audio classification if model is unavailable.
        print(f"WARNING: Audio classifier failed to load: {exc}")


def get_image_classifier():
    if _image_classifier is None:
        raise HTTPException(
            status_code=503,
            detail="Image classifier not available — server may still be starting.",
        )
    return _image_classifier


def get_audio_classifier():
    if _audio_classifier is None:
        raise HTTPException(
            status_code=503,
            detail="Audio classifier not available — run scripts/download_models.py then restart.",
        )
    return _audio_classifier


# ── Image / video helpers ─────────────────────────────────────────────────────

def _get_image_fake_score(img: Image.Image) -> float:
    results = get_image_classifier()(img)
    return {r["label"]: r["score"] for r in results}.get("Fake", 0.0)


def _image_verdict(fake_score: float) -> tuple[str, float]:
    if fake_score > 0.5:
        return "ai_generated", fake_score
    return "real", 1.0 - fake_score


# ── Audio helpers ─────────────────────────────────────────────────────────────

def _load_audio(path: str) -> np.ndarray:
    """Load audio file → 16 kHz mono float32 numpy array."""
    try:
        data, sr = sf.read(path, dtype="float32", always_2d=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not decode audio file: {exc}")
    if data.ndim > 1:
        data = data.mean(axis=1)  # stereo → mono
    if sr != AUDIO_SAMPLE_RATE:
        waveform = torch.from_numpy(data).unsqueeze(0)
        waveform = TAF.resample(waveform, sr, AUDIO_SAMPLE_RATE)
        return waveform.squeeze().numpy()
    return data


def _get_audio_spoof_score(chunk_np: np.ndarray) -> float:
    """Score one audio window. Returns spoof score (higher = more likely fake)."""
    results = get_audio_classifier()({"array": chunk_np, "sampling_rate": AUDIO_SAMPLE_RATE})
    return {r["label"]: r["score"] for r in results}.get("fake", 0.0)


def _run_windowed_inference(audio_np: np.ndarray) -> list[tuple[float, float]]:
    """
    Split audio into AUDIO_CHUNK_SECONDS windows (up to MAX_AUDIO_CHUNKS evenly sampled).
    Returns [(timestamp_seconds, spoof_score), ...].
    Runs on the whole clip as a single window when audio is shorter than AUDIO_CHUNK_SECONDS.
    """
    total_chunks = len(audio_np) // AUDIO_CHUNK_SAMPLES

    if total_chunks == 0:
        return [(0.0, _get_audio_spoof_score(audio_np))]

    n = min(total_chunks, MAX_AUDIO_CHUNKS)
    results = []
    for i in range(n):
        chunk_idx = int(i * total_chunks / n)
        start = chunk_idx * AUDIO_CHUNK_SAMPLES
        chunk = audio_np[start : start + AUDIO_CHUNK_SAMPLES]
        score = _get_audio_spoof_score(chunk)
        results.append((start / AUDIO_SAMPLE_RATE, score))

    return results


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/image", response_model=ClassifyImageResponse)
async def classify_image(file: UploadFile = File(...)) -> ClassifyImageResponse:
    """Classify an uploaded image as real or AI-generated."""

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported type '{file.content_type}'. Allowed: {sorted(ALLOWED_IMAGE_TYPES)}",
        )

    data = await file.read()

    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(data):,} bytes). Max: {MAX_IMAGE_BYTES:,} (10 MB).",
        )

    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="File is not a valid image or is corrupted.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not decode image: {exc}")

    fake_score = _get_image_fake_score(img)
    verdict, confidence_score = _image_verdict(fake_score)

    return ClassifyImageResponse(
        verdict=verdict,
        confidence_score=round(confidence_score, 4),
        note=CONFIDENCE_NOTE,
        model=IMAGE_MODEL_ID,
        disclaimer=DISCLAIMER,
    )


@router.post("/video", response_model=ClassifyVideoResponse)
async def classify_video(file: UploadFile = File(...)) -> ClassifyVideoResponse:
    """Sample frames from an uploaded video and classify as real or AI-generated."""

    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported type '{file.content_type}'. Allowed: {sorted(ALLOWED_VIDEO_TYPES)}",
        )

    data = await file.read()

    if len(data) > MAX_VIDEO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(data):,} bytes). Max: {MAX_VIDEO_BYTES:,} (100 MB).",
        )

    suffix = os.path.splitext(file.filename or ".mp4")[1] or ".mp4"
    tmp_path: Optional[str] = None
    cap: Optional[cv2.VideoCapture] = None

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        cap = cv2.VideoCapture(tmp_path)

        if not cap.isOpened():
            raise HTTPException(
                status_code=400,
                detail="Could not open video. It may be corrupted or use an unsupported codec.",
            )

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            raise HTTPException(status_code=400, detail="Video contains no readable frames.")

        n_samples = min(total_frames, MAX_VIDEO_FRAMES)
        sample_indices = [int(i * total_frames / n_samples) for i in range(n_samples)]

        frame_scores: list[tuple[int, float]] = []
        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            frame_scores.append((idx, _get_image_fake_score(img)))

    except HTTPException:
        raise
    except cv2.error as exc:
        raise HTTPException(status_code=400, detail=f"OpenCV error reading video: {exc}")
    finally:
        if cap is not None:
            cap.release()
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    if not frame_scores:
        raise HTTPException(
            status_code=400, detail="Could not extract any readable frames from the video."
        )

    mean_fake = sum(s for _, s in frame_scores) / len(frame_scores)
    verdict, confidence_score = _image_verdict(mean_fake)
    worst_idx, worst_score = max(frame_scores, key=lambda x: x[1])

    return ClassifyVideoResponse(
        verdict=verdict,
        confidence_score=round(confidence_score, 4),
        note=CONFIDENCE_NOTE,
        frames_sampled=len(frame_scores),
        most_suspicious_frame=SuspiciousFrame(
            frame_index=worst_idx,
            fake_score=round(worst_score, 4),
        ),
        model=IMAGE_MODEL_ID,
        disclaimer=DISCLAIMER,
    )


@router.post("/audio", response_model=ClassifyAudioResponse)
async def classify_audio(file: UploadFile = File(...)) -> ClassifyAudioResponse:
    """
    Classify an uploaded audio clip as genuine or AI-spoofed.

    Uses sliding-window inference (3-second windows, up to 10 evenly sampled) to
    produce both a whole-clip verdict and an anomaly_timestamp pointing to the most
    suspicious segment. The model itself is whole-clip only; the timestamp is derived
    by running it on each window independently.
    """

    if file.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported type '{file.content_type}'. "
                f"Allowed: {sorted(ALLOWED_AUDIO_TYPES)}. MP3 requires ffmpeg."
            ),
        )

    data = await file.read()

    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(data):,} bytes). Max: {MAX_AUDIO_BYTES:,} (25 MB).",
        )

    suffix = os.path.splitext(file.filename or ".wav")[1] or ".wav"
    tmp_path: Optional[str] = None

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        audio_np = _load_audio(tmp_path)
    except HTTPException:
        raise
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    rms = float(np.sqrt(np.mean(audio_np ** 2)))
    if rms < AUDIO_SILENCE_THRESHOLD:
        raise HTTPException(
            status_code=400, detail="Audio appears to be silent or contains no signal."
        )

    chunk_results = _run_windowed_inference(audio_np)

    mean_spoof = sum(s for _, s in chunk_results) / len(chunk_results)

    if mean_spoof > 0.5:
        verdict = "spoof"
        confidence_score = mean_spoof
    else:
        verdict = "genuine"
        confidence_score = 1.0 - mean_spoof

    worst_ts, _ = max(chunk_results, key=lambda x: x[1])

    return ClassifyAudioResponse(
        verdict=verdict,
        confidence_score=round(confidence_score, 4),
        note=AUDIO_CONFIDENCE_NOTE,
        anomaly_timestamp=round(worst_ts, 2),
        model=AUDIO_MODEL_ID,
        disclaimer=DISCLAIMER,
    )
