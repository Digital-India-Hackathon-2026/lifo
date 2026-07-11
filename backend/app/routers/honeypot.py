"""
/honeypot — session-based conversation simulator.

Scammer audio in (upload or browser mic) → Whisper STT → Gemini persona → GCP TTS out.
No telephony; sessions are in-memory, keyed by UUID.
"""
import time
import uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.responses import (
    ConverseResponse,
    CumulativeIntel,
    ReportResponse,
    StartSessionResponse,
    TurnHistoryItem,
    TurnSignals,
)
from app.services.honeypot_pipeline import (
    extract_signals,
    generate_persona_reply,
    synthesize_speech,
    transcribe_audio,
)

router = APIRouter(prefix="/honeypot", tags=["honeypot"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/flac", "audio/x-flac",
    "audio/ogg",
    "audio/webm",         # browser MediaRecorder (Chrome)
    "audio/mp4", "audio/x-m4a",  # iOS Safari
}

# In-memory session store — fine for demo; no TTL needed
_sessions: dict[str, dict[str, Any]] = {}


def _empty_intel() -> dict[str, list[str]]:
    return {"upi_ids": [], "phone_numbers": [], "bank_accounts": [], "scripted_phrases": []}


def _merge_intel(cumulative: dict, new: dict) -> None:
    """Deduplicated union: accumulate new signals into cumulative in-place."""
    for key in ("upi_ids", "phone_numbers", "bank_accounts", "scripted_phrases"):
        existing = set(cumulative[key])
        for val in new[key]:
            if val not in existing:
                cumulative[key].append(val)
                existing.add(val)


def _get_session(session_id: str) -> dict[str, Any]:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    return _sessions[session_id]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start", response_model=StartSessionResponse)
async def start_session() -> StartSessionResponse:
    """Create a new honeypot conversation session."""
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "session_id": session_id,
        "created_at": time.time(),
        "turns": [],
        "cumulative_intel": _empty_intel(),
    }
    return StartSessionResponse(session_id=session_id)


@router.post("/converse", response_model=ConverseResponse)
async def converse(
    session_id: str = Form(...),
    file: UploadFile = File(...),
) -> ConverseResponse:
    """
    Submit one audio turn from the scammer. Returns the persona reply and
    any signals extracted from this turn and accumulated across all turns.
    """
    session = _get_session(session_id)

    if file.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported audio type '{file.content_type}'. "
                f"Allowed: {sorted(ALLOWED_AUDIO_TYPES)}"
            ),
        )

    data = await file.read()
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(data):,} bytes). Max: {MAX_AUDIO_BYTES:,} (25 MB).",
        )

    stage_log: list[str] = []
    suffix = "." + (file.filename or "audio.wav").rsplit(".", 1)[-1]

    # Stage 1 — STT
    transcript, stt_err = transcribe_audio(data, suffix=suffix)
    stage_log.append(
        f"STT: ok ({len(transcript.split())} words)" if transcript
        else f"STT: FAILED — {stt_err}"
    )

    # Stage 2 — Persona (skipped if no transcript)
    persona_reply: str | None = None
    if transcript:
        persona_reply, persona_err = generate_persona_reply(session["turns"], transcript)
        stage_log.append(
            "Persona: ok" if persona_reply
            else f"Persona: FAILED — {persona_err}"
        )
    else:
        stage_log.append("Persona: skipped (no transcript)")

    # Stage 3 — TTS (skipped if no reply)
    audio_b64: str | None = None
    if persona_reply:
        audio_b64, tts_err = synthesize_speech(persona_reply)
        stage_log.append(
            "TTS: ok" if audio_b64
            else f"TTS: FAILED — {tts_err}"
        )
    else:
        stage_log.append("TTS: skipped (no persona reply)")

    # Stage 4 — Signal extraction (runs even on partial transcripts)
    try:
        signals = extract_signals(transcript or "")
        n = sum(len(v) for v in signals.values())
        stage_log.append(f"Extraction: ok ({n} signal{'s' if n != 1 else ''} found)")
    except Exception as exc:
        signals = _empty_intel()
        stage_log.append(f"Extraction: FAILED — {exc}")

    # Update session
    session["turns"].append({"transcript": transcript, "persona_reply": persona_reply})
    _merge_intel(session["cumulative_intel"], signals)

    turn_num = len(session["turns"])
    cum = session["cumulative_intel"]

    return ConverseResponse(
        session_id=session_id,
        turn=turn_num,
        transcript=transcript,
        persona_reply_text=persona_reply,
        persona_reply_audio=audio_b64,
        signals_this_turn=TurnSignals(**signals),
        cumulative_intel=CumulativeIntel(**cum),
        stage_log=stage_log,
    )


@router.get("/report/{session_id}", response_model=ReportResponse)
async def get_report(session_id: str) -> ReportResponse:
    """Return the full intelligence report for a session."""
    session = _get_session(session_id)
    cum = session["cumulative_intel"]
    turns = session["turns"]
    return ReportResponse(
        session_id=session_id,
        turn_count=len(turns),
        cumulative_intel=CumulativeIntel(**cum),
        turn_history=[
            TurnHistoryItem(
                turn=i + 1,
                transcript=t["transcript"],
                persona_reply=t["persona_reply"],
            )
            for i, t in enumerate(turns)
        ],
    )
