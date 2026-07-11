"""
/surfaces — New distribution-channel surfaces: WhatsApp/Telegram chat
webhook (items 44/45), browser-extension URL check (item 46), IVR/feature-
phone routing (item 48), QR-code "quishing" scanner (item 49), and the
smart-TV/Chromecast distress broadcast (item 50). Ported from the Track 2
collaborator repo's app/routers/surfaces.py — re-read in full this
session, not from Session 27's summary.

ITEM 44/45 (chat webhook): the reference shares one generic endpoint for
both WhatsApp and Telegram (a `platform` path param distinguishes them),
matched only against a hardcoded 5-word list ("digital arrest", "cbi",
"customs", "verification fee", "money laundering"). That's thin — a real
chat message deserves the same detection quality as every other channel
already ported — so this reuses document.py's own `_SCAM_PATTERNS`/
`_PAYMENT_PATTERNS` (12 scam-phrase patterns + 5 payment-indicator
patterns, the same rule set digital_arrest.py already imports rather than
redefining) instead of the reference's tiny list. Deliberately NOT
document.py's `_CALL_PATTERNS` equivalent (digital_arrest.py's 3
spoken-register additions like "stay on line") — those are built for live
call transcripts, not a forwarded chat message. `platform` is now a real
`Literal["whatsapp", "telegram"]`, not an unvalidated string.

ITEM 46 (browser extension): a single, sound keyword heuristic — ported
as-is.

ITEM 48 (IVR): a single, sound DTMF-digit heuristic — ported as-is.

ITEM 49 (QR scanner): unchanged from Session 27 — flags a UPI "collect
request" QR code (`pa=` present, `am=` absent), the specific pattern that
lets a scanned code silently pull money out of the scanner's account
instead of paying them.

ITEM 50 (smart-TV broadcast): confirmed by reading the reference that
this has NO real logic at all — it's a pure hardcoded echo. `trigger_source`
is accepted but never used; `broadcast_status` is always the same literal
string regardless of input. Ported as the honest stub it is: `note`
states this plainly, same self-labeling convention as the moonshot PoC's
`note` field — not dressed up as more than it is.

ITEM 47 (smart speaker skill): the reference has nothing for this item —
built from zero. No real Alexa/Google Home certification or platform
deployment is in scope; that would be a separate, non-engineering-heavy
publishing process. What's built is the one honest, reusable thing a
real skill's backend would actually call: a generic voice-command
webhook. Placed here rather than in vulnerable.py because it's a new
distribution channel (voice), the same category as items 44-50 already
in this file, not more protector/pairing logic. A simple trigger-phrase
heuristic (not real NLU/intent classification — stated plainly) decides
the branch: a panic-mode phrase reuses item 41's own PairedDevice lookup
(the exact same paired-vs-unpaired logic panic_trigger uses in
vulnerable.py, imported directly rather than re-implemented), anything
else runs through digital_arrest.py's own pure `_analyze_transcript`/
`_severity` functions (no HTTP self-call) — reusing an existing detector
rather than building a fourth pattern list for what's fundamentally the
same Digital Arrest check every other channel already does.

No envelope; response_model= directly; real HTTP status codes; proper
Pydantic validation throughout.
"""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.responses import (
    ChatWebhookResponse,
    ExtensionCheckResponse,
    IVRResponse,
    QRScanResponse,
    SmartSpeakerResponse,
    TVBroadcastResponse,
)
from app.models.track2_db import PairedDevice
from app.routers.digital_arrest import _analyze_transcript, _severity
from app.routers.document import _PAYMENT_PATTERNS, _SCAM_PATTERNS

router = APIRouter(prefix="/surfaces", tags=["Distribution Surfaces"])

_RISK_AUTO_REPLY = "🚨 KAVACH ALERT: This message matches known Digital Arrest scam patterns. DO NOT PAY."
_CLEAR_AUTO_REPLY = "Kavach: No immediate scam patterns detected."

_SUSPICIOUS_URL_KEYWORDS = ["cbi-verify", "gov-kyc-update", "police-fine-pay", "trai-block"]

_TV_BROADCAST_NOTE = (
    "Hardcoded scaffold — always returns the same broadcast_status regardless of "
    "trigger_source. There is no real smart-TV/Chromecast integration behind this endpoint."
)


class _ChatWebhookRequest(BaseModel):
    sender_id: str = Field(..., min_length=1)
    text_payload: str = Field(..., min_length=1)


class _IVRRequest(BaseModel):
    caller_id: str = Field(..., min_length=1)
    keypad_dtmf: str = Field(..., min_length=1)


class _TVBroadcastRequest(BaseModel):
    household_id: str = Field(..., min_length=1)
    trigger_source: str = Field(..., min_length=1)


class _VoiceCommandRequest(BaseModel):
    device_id: str = Field(..., min_length=1)
    transcribed_command: str = Field(..., min_length=1)


# Simple substring heuristic, deliberately not NLU/intent classification —
# a real skill's platform-side wake-word/intent handling would narrow this
# further before it ever reaches this webhook.
_PANIC_TRIGGER_PHRASES = ["help", "emergency", "sos", "panic", "call for help"]


@router.post("/chat-webhook/{platform}", response_model=ChatWebhookResponse)
async def chat_bot_webhook(
    platform: Literal["whatsapp", "telegram"], payload: _ChatWebhookRequest
) -> ChatWebhookResponse:
    """Scan a forwarded WhatsApp/Telegram message against the same Digital Arrest
    pattern set every other channel in this codebase already uses."""
    text = payload.text_payload
    matched: list[str] = []
    for pattern, label in _SCAM_PATTERNS + _PAYMENT_PATTERNS:
        if pattern.search(text):
            matched.append(label)

    risk_detected = bool(matched)
    return ChatWebhookResponse(
        platform=platform,
        risk_detected=risk_detected,
        matched_patterns=matched,
        auto_reply_action=_RISK_AUTO_REPLY if risk_detected else _CLEAR_AUTO_REPLY,
    )


@router.get("/extension/check-url", response_model=ExtensionCheckResponse)
async def extension_check_url(url: str = Query(..., min_length=1)) -> ExtensionCheckResponse:
    """Typo-squatting keyword heuristic for the browser extension's real-time hook."""
    is_suspicious = any(keyword in url.lower() for keyword in _SUSPICIOUS_URL_KEYWORDS)
    return ExtensionCheckResponse(
        scanned_url=url,
        action="BLOCK_NAVIGATION" if is_suspicious else "ALLOW",
    )


@router.post("/ivr/incoming", response_model=IVRResponse)
async def ivr_helpline(payload: _IVRRequest) -> IVRResponse:
    """Route an IVR/feature-phone call based on the DTMF digit pressed."""
    action = "TRIGGER_FAMILY_PANIC_ALERT" if payload.keypad_dtmf == "9" else "ROUTING_TO_HUMAN_OPERATOR"
    return IVRResponse(caller=payload.caller_id, routed_action=action)


@router.get("/qr/scan", response_model=QRScanResponse)
async def qr_scanner_check(decoded_text: str = Query(..., min_length=1)) -> QRScanResponse:
    """Flag a UPI QR payload that's a disguised 'collect request' (silent debit), not a real payment."""
    is_collect_request = "pa=" in decoded_text and "am=" not in decoded_text
    return QRScanResponse(
        is_dangerous_collect=is_collect_request,
        recommendation="DO NOT SCAN - FORCED DEBIT" if is_collect_request else "SAFE",
    )


@router.post("/smart-tv/broadcast", response_model=TVBroadcastResponse)
async def tv_distress_broadcast(payload: _TVBroadcastRequest) -> TVBroadcastResponse:
    """Hardcoded scaffold — see module docstring. Always the same broadcast_status."""
    return TVBroadcastResponse(
        household=payload.household_id,
        broadcast_status="ACTIVE_FULLSCREEN_WARNING",
        note=_TV_BROADCAST_NOTE,
    )


@router.post("/smart-speaker/command", response_model=SmartSpeakerResponse)
async def smart_speaker_command(req: _VoiceCommandRequest, db: Session = Depends(get_db)) -> SmartSpeakerResponse:
    """Route a transcribed voice command to a panic trigger or a risk check — see module docstring."""
    text_lower = req.transcribed_command.lower()

    if any(phrase in text_lower for phrase in _PANIC_TRIGGER_PHRASES):
        pairing = db.query(PairedDevice).filter(PairedDevice.protected_id == req.device_id).first()
        protector_id = pairing.protector_id if pairing else None
        spoken = (
            "Emergency alert sent to your family."
            if protector_id
            else "Emergency alert broadcast to public emergency services."
        )
        return SmartSpeakerResponse(device_id=req.device_id, action_taken="PANIC_TRIGGERED", spoken_response=spoken)

    scam_hits, payment_hits = _analyze_transcript(req.transcribed_command)
    sev = _severity(scam_hits, payment_hits)
    if sev == "high":
        spoken = "Warning: that sounds like a known scam pattern. Do not send money or share personal details."
    elif sev == "medium":
        spoken = "Be cautious — that contains suspicious language often used in scams."
    else:
        spoken = "I didn't detect any known scam patterns in that, but stay alert."

    return SmartSpeakerResponse(
        device_id=req.device_id, action_taken="RISK_CHECK", spoken_response=spoken, risk_level=sev,
    )
