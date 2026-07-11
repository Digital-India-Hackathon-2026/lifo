"""
/scams/romance — Romance / pig-butchering scam detector (catalog item 1).

Phrase and structural signals ported from the Track 1 collaborator repo's
romance.yaml pack (kavach-track1-audit/app/engines/pattern_engine/packs/
romance.yaml) — the reference has no dedicated router for this item, only
the YAML pack, so this router (and its weighted-signal scoring) is built
fresh from that pack's actual patterns and risk_bands. See AGENTS.md for
provenance and TODO.md for why the reference's YAML-pack engine itself
was not adopted.

Unlike items 2/4/5/6 (simple flag-count routers, ported as-is from their
own reference routers), this item's source material is a *weighted*
signal pack, so its risk banding is a weighted sum against thresholds
(low/medium/high), not a flag count — that's what the reference actually
specifies for this item, ported faithfully rather than forced into the
other four's flag-count shape.
"""
import re
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, model_validator

from app.models.responses import ScamPatternResponse, flat_evidence_trail
from app.routers.document import _BANK_ACCOUNT_RE, _UPI_RE
from app.services.honeypot_pipeline import _PHONE_RE

router = APIRouter(prefix="/scams/romance", tags=["Fraud Coverage"])


class TranscriptRequest(BaseModel):
    """Shared request shape for all 5 fraud-type detectors in this batch.

    The reference's version let both fields default to empty strings with
    no validation, so an empty POST silently scored "Low risk" instead of
    rejecting. Fixed here: at least one of the two must be non-empty.
    """
    transcript: Optional[str] = None
    email_body: Optional[str] = None

    @model_validator(mode="after")
    def _require_one(self):
        if not (self.transcript or "").strip() and not (self.email_body or "").strip():
            raise ValueError("Provide at least one of 'transcript' or 'email_body'.")
        return self


# Not covered by any existing shared regex — new for this item.
_CRYPTO_WALLET_RE = re.compile(r"\b(?:0x[a-fA-F0-9]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{25,39})\b")
_URL_RE = re.compile(r"https?://\S+")

# (compiled pattern, label, weight) — ported verbatim from romance.yaml's
# phrase_signals (14 entries).
_PHRASE_SIGNALS: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r'soulmate|destined to be together|never felt this way|fell in love with you instantly|you are my everything|my heart belongs to you|love you already', re.I),
     "Love bombing — instant intimacy", 0.12),
    (re.compile(r'deployed overseas|peacekeeping mission|stationed in|serving abroad|military base|on a rig|oil rig|working offshore|un mission|nato mission|doctor without borders', re.I),
     "Fake military or professional overseas identity", 0.14),
    (re.compile(r'camera.{0,25}broken|cannot.{0,10}video|can.t.{0,10}video|video.{0,25}not working|connection.{0,20}bad|poor.{0,10}signal|mic.{0,15}broken|phone.{0,15}damaged', re.I),
     "Video call avoidance", 0.15),
    (re.compile(r'medical emergency|stranded.{0,30}airport|stuck.{0,20}customs|passport.{0,20}seized|luggage.{0,20}stolen|accident.{0,30}hospital|surgery.{0,20}urgent|operation.{0,20}money', re.I),
     "Fabricated medical or travel emergency", 0.20),
    (re.compile(r'itunes.{0,15}card|google play.{0,15}card|steam.{0,15}card|amazon.{0,15}gift card|gift card.{0,25}code|send.{0,20}card.{0,20}number|voucher.{0,15}code', re.I),
     "Gift card payment demand", 0.28),
    (re.compile(r'western union|moneygram|wire.{0,20}transfer|wire me|transfer.{0,20}money|send.{0,15}money|remit.{0,15}fund|ria money', re.I),
     "Wire transfer or money service demand", 0.28),
    (re.compile(r"don.t tell|keep.{0,25}secret|between us only|tell nobody|no one must know|our little secret|don.t mention|hide.{0,15}from", re.I),
     "Secrecy and isolation instruction", 0.15),
    (re.compile(r'send.{0,25}bitcoin|bitcoin.{0,25}wallet|send.{0,25}crypto|usdt|tether.{0,20}pay|binance.{0,20}send|ethereum.{0,20}send|coinbase.{0,15}transfer', re.I),
     "Cryptocurrency payment demand", 0.26),
    (re.compile(r'customs.{0,25}fee|clearance.{0,25}fee|release.{0,25}fee|duty.{0,20}pay|tax.{0,25}before.{0,20}release|diplomatic.{0,15}fee|security.{0,15}deposit.{0,15}package', re.I),
     "Customs or clearance fee demand", 0.25),
    (re.compile(r'pay you back|return the money|reimburse you|as soon as i.{0,20}(arrive|return|land|get back)|once i.{0,15}(arrive|return)|when i.{0,15}(arrive|return|get back)', re.I),
     "False promise of repayment", 0.12),
    (re.compile(r'god sent you|meant to meet|our destiny|destiny.{0,20}together|true love.{0,20}(find|found)|you are the one|meant for each other', re.I),
     "Emotional manipulation — fate and destiny", 0.10),
    (re.compile(r'large inheritance|gold.{0,25}stored|unclaimed.{0,20}fund|widow.{0,20}inheritance|late husband.{0,20}million|million.{0,20}dollar.{0,20}transfer|diplomat.{0,20}box', re.I),
     "Large inheritance or gold storage story", 0.18),
    (re.compile(r'trading platform|crypto.{0,20}platform|investment app|my mentor.{0,20}taught|trading.{0,15}account.{0,15}open|sure profit|profit.{0,15}guaranteed', re.I),
     "Pig-butchering hybrid — trading platform push", 0.20),
    (re.compile(r'share.{0,20}bank.{0,20}detail|send.{0,20}account.{0,20}number|your.{0,20}ifsc|your.{0,20}pan|login.{0,15}detail.{0,15}send', re.I),
     "Request for personal financial credentials", 0.22),
]

# (compiled pattern, label, weight) — ported from romance.yaml's
# structural_signals (5 entries). The reference's "contextual" gating
# (only counting upi_id/bank_account near payment language) belongs to
# the YAML-pack engine we're deliberately not adopting here — flattened
# to plain presence checks, matching the simplicity level of items 2/4/5/6.
_STRUCTURAL_SIGNALS: list[tuple[re.Pattern, str, float]] = [
    (_UPI_RE, "UPI payment address present", 0.22),
    (_BANK_ACCOUNT_RE, "Bank account number present", 0.18),
    (_CRYPTO_WALLET_RE, "Cryptocurrency wallet address present", 0.22),
    (_PHONE_RE, "Phone number present", 0.06),
    (_URL_RE, "URL present", 0.08),
]

_RISK_BANDS = {"low": 0.0, "medium": 0.25, "high": 0.55}  # ported from romance.yaml risk_bands


@router.post("/check", response_model=ScamPatternResponse)
async def check_romance_scam(req: TranscriptRequest) -> ScamPatternResponse:
    """Weighted phrase + structural signal scan for romance / pig-butchering scams."""
    text = req.transcript or req.email_body or ""
    flags: list[str] = []
    score = 0.0

    for pattern, label, weight in _PHRASE_SIGNALS + _STRUCTURAL_SIGNALS:
        if pattern.search(text):
            flags.append(label)
            score += weight

    score = min(score, 1.0)
    if score >= _RISK_BANDS["high"]:
        risk_level = "high"
    elif score >= _RISK_BANDS["medium"]:
        risk_level = "medium"
    else:
        risk_level = "low"

    return ScamPatternResponse(risk_level=risk_level, flags=flags, confidence_score=round(score, 2), evidence_trail=flat_evidence_trail(flags))
