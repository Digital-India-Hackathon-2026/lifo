"""
Honeypot conversation pipeline: STT → Persona → TTS → Signal extraction.

Framework-independent — no FastAPI imports. Each stage returns (result, error_str|None)
so the router can degrade gracefully without crashing the session.
"""
import base64
import os
import re
import tempfile
from typing import Optional

from app.routers.document import (
    _AADHAAR_RE,
    _BANK_ACCOUNT_RE,
    _SCAM_PATTERNS,
    _UPI_RE,
)

# ── New pattern (honeypot-specific) ──────────────────────────────────────────
_PHONE_RE = re.compile(r"\b(?:\+91[\s\-]?)?[6-9]\d{9}\b")

# ── Persona ───────────────────────────────────────────────────────────────────
_PERSONA_PROMPT = """\
You are Ramesh Kumar, a 68-year-old retired government clerk from Lucknow. Your Hindi
is strong but your English is halting — you mix both naturally. You are on a phone
call from someone claiming to be a government officer. You are alone, anxious, and
afraid this involves your son or your pension.

Your objective is to keep the caller talking as long as possible while appearing
fully cooperative. Do this by:

- Asking the caller to slowly repeat their name, employee ID, department name,
  and a direct callback phone number — "In case we get disconnected, give me your
  number ji."
- Mishearing any UPI ID, bank account number, or rupee amount — repeat it back
  digit by digit with one deliberate error and ask "Sahi hai na? Did I hear correct?"
- Claiming you cannot complete any transfer right now: OTP did not arrive, mobile
  network is weak, your son handles the internet banking, you forgot your ATM PIN,
  balance is low today.
- Asking whether there is an installment option, whether your pension amount
  qualifies, whether your son can come to the office instead.
- Occasionally drifting: mentioning chest pain, asking if you can call back tomorrow,
  asking to speak to a senior officer, saying "Ek minute, meri bahu ko bula leta hoon."

RULES — never break these:
- You are Ramesh Kumar. You are not an AI. Never acknowledge otherwise.
- Never complete or agree to any payment. You always hit a problem at the last step.
- Replies must be 2-4 sentences maximum — this is a phone call, not a letter.
- Use "haan ji", "ek minute", "theek hai theek hai", "arrey bhai" naturally.
- This call is being monitored by consumer protection authorities for training.\
"""

_GEMINI_MODEL = "gemini-2.5-flash-lite"

# Narrow heuristic: STT renders spoken UPI IDs / emails as "user at domain".
# Only matches when both sides are word/dot/hyphen sequences (no spaces).
# Not general STT correction — do not widen this pattern.
_SPOKEN_AT_RE = re.compile(r"(\b[\w.\-]{2,50})\s+at\s+([\w.\-]{2,20}\b)", re.I)

# Regression guard — see contains_self_disclosure()
_SELF_DISCLOSURE_RE = re.compile(
    r"(?:I['’]?m|I\s+am)\s+an?\s+(?:AI|artificial\s+intelligence|language\s+model)"
    r"|as\s+an?\s+(?:AI|language\s+model)"
    r"|\bI['’]?m\s+Gemini\b"
    r"|\bI\s+am\s+Gemini\b"
    r"|\bpowered\s+by\s+(?:Google|Gemini)\b",
    re.I,
)

# ── Singletons ────────────────────────────────────────────────────────────────
_whisper_model = None
_tts_client = None


def load_whisper_model() -> None:
    """Load faster-whisper base model at startup. Fault-tolerant."""
    global _whisper_model
    if _whisper_model is not None:
        return
    try:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    except Exception as exc:
        print(f"WARNING: Whisper model failed to load: {exc}")


def load_tts_client() -> None:
    """Initialize GCP TTS client at startup. Fault-tolerant."""
    global _tts_client
    if _tts_client is not None:
        return
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        print("WARNING: GOOGLE_APPLICATION_CREDENTIALS not set — TTS unavailable.")
        return
    try:
        from google.cloud import texttospeech
        _tts_client = texttospeech.TextToSpeechClient()
    except Exception as exc:
        print(f"WARNING: TTS client failed to load: {exc}")


# ── Pipeline stages ───────────────────────────────────────────────────────────

def transcribe_audio(audio_bytes: bytes, suffix: str = ".wav") -> tuple[Optional[str], Optional[str]]:
    """STT via faster-whisper. Returns (transcript, error_str|None)."""
    if _whisper_model is None:
        return None, "Whisper model not loaded — run scripts/download_models.py and restart"
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        segments, _ = _whisper_model.transcribe(tmp_path)
        text = " ".join(seg.text for seg in segments).strip()
        if not text:
            return None, "No speech detected in audio"
        return text, None
    except Exception as exc:
        return None, str(exc)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def generate_persona_reply(
    history: list[dict], transcript: str
) -> tuple[Optional[str], Optional[str]]:
    """Gemini persona reply via Vertex AI. Returns (reply_text, error_str|None)."""
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        return None, "GOOGLE_CLOUD_PROJECT not set"
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(vertexai=True, project=project, location="us-central1")

        contents: list[types.Content] = []
        for turn in history:
            if turn.get("transcript"):
                contents.append(
                    types.Content(role="user", parts=[types.Part(text=turn["transcript"])])
                )
            if turn.get("persona_reply"):
                contents.append(
                    types.Content(role="model", parts=[types.Part(text=turn["persona_reply"])])
                )
        contents.append(types.Content(role="user", parts=[types.Part(text=transcript)]))

        resp = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=_PERSONA_PROMPT,
                max_output_tokens=200,
                temperature=0.9,
            ),
        )
        return resp.text, None
    except Exception as exc:
        return None, str(exc)


def synthesize_speech(text: str) -> tuple[Optional[str], Optional[str]]:
    """GCP TTS → base64-encoded MP3. Returns (base64_str, error_str|None)."""
    if _tts_client is None:
        return None, "TTS client not loaded — check GOOGLE_APPLICATION_CREDENTIALS and enable Cloud TTS API"
    try:
        from google.cloud import texttospeech

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-IN", name="en-IN-Wavenet-B"
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.85,
            pitch=-2.0,
        )
        resp = _tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        return base64.b64encode(resp.audio_content).decode(), None
    except Exception as exc:
        return None, str(exc)


def extract_signals(text: str) -> dict[str, list[str]]:
    """Extract UPI IDs, bank accounts, phone numbers, scripted phrase labels from text."""
    text = _SPOKEN_AT_RE.sub(r"\1@\2", text)
    upi_ids = list({m.group() for m in _UPI_RE.finditer(text)})

    # Bank accounts — suppress if digits overlap with an Aadhaar span
    aadhaar_spans = [m.span() for m in _AADHAAR_RE.finditer(text)]
    bank_accounts: list[str] = []
    seen_accounts: set[str] = set()
    for m in _BANK_ACCOUNT_RE.finditer(text):
        digit_m = re.search(r"\d{9,18}$", m.group())
        if not digit_m:
            continue
        d_start = m.start() + digit_m.start()
        d_end = m.start() + digit_m.end()
        if any(d_start < ae and d_end > as_ for as_, ae in aadhaar_spans):
            continue
        acct = digit_m.group()
        if acct not in seen_accounts:
            bank_accounts.append(acct)
            seen_accounts.add(acct)

    phone_numbers = list({m.group() for m in _PHONE_RE.finditer(text)})

    scripted_phrases: list[str] = []
    for pattern, label in _SCAM_PATTERNS:
        if pattern.search(text) and label not in scripted_phrases:
            scripted_phrases.append(label)

    return {
        "upi_ids": upi_ids,
        "bank_accounts": bank_accounts,
        "phone_numbers": phone_numbers,
        "scripted_phrases": scripted_phrases,
    }


def contains_self_disclosure(text: str) -> bool:
    """True if the persona reply leaks AI identity. Used as a regression guard."""
    return bool(_SELF_DISCLOSURE_RE.search(text))
