"""
/classify/document — OCR + rule-based scam indicator detection.

SCOPE: OCR via Google Cloud Vision API + rule-based text analysis for Digital Arrest
scam patterns and PII exposure. Does NOT perform forensic image manipulation detection
(metadata tampering, font consistency checks, compression artifact analysis).
"""
import io
import os
import re

from fastapi import APIRouter, File, HTTPException, UploadFile
from google.cloud import vision as _gcp_vision
from PIL import Image, UnidentifiedImageError

from app.models.responses import (
    DISCLAIMER,
    ClassifyDocumentResponse,
    EvidenceItem,
    EvidenceTrail,
    PIIMatch,
    ScamIndicator,
)

router = APIRouter(prefix="/classify", tags=["classify"])

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
ALLOWED_DOCUMENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}

_SCOPE_NOTE = (
    "OCR and rule-based text analysis only. "
    "Does not detect image manipulation or forgery. "
    "A low-risk result does not certify the document is genuine."
)
_ANCHOR = (
    " No Indian government agency (CBI, ED, RBI, TRAI, Police) arrests citizens "
    "via video call or demands payment for 'verification' or 'bail'."
)

# ── Rule patterns ─────────────────────────────────────────────────────────────

_SCAM_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"digital\s+arrest", re.I), "digital_arrest"),
    (re.compile(r"video\s+call\s+arrest", re.I), "video_call_arrest"),
    (re.compile(r"arrested\s+(?:over|via|on)\s+(?:video|phone|online|call)", re.I), "arrested_via_call"),
    (re.compile(r"verification\s+(?:fee|amount|payment|charge)", re.I), "verification_payment"),
    (re.compile(r"bail\s+(?:amount|money|payment|fee)", re.I), "bail_payment"),
    (re.compile(r"(?:RBI|TRAI|CBI|ED|Income\s*Tax|Narcotics)\s+(?:warrant|notice|order)", re.I), "fake_agency_order"),
    (re.compile(r"money\s+laundering", re.I), "money_laundering_claim"),
    (re.compile(r"(?:account|assets?)\s+(?:will\s+be\s+)?(?:frozen|blocked|seized)", re.I), "asset_freeze_threat"),
    (re.compile(r"do\s+not\s+(?:tell|inform|contact)\s+(?:anyone|family|relatives|friends)", re.I), "isolation_tactic"),
    (re.compile(r"keep\s+(?:this|it)\s+(?:confidential|secret)", re.I), "secrecy_demand"),
    (re.compile(r"cyber\s+crime\s+(?:branch|division|department|cell|unit)", re.I), "fake_cybercrime_unit"),
    (re.compile(r"(?:appear|report)\s+(?:online|virtually|on\s+video\s+call)", re.I), "virtual_summons"),
]

# Named for direct import by honeypot_pipeline (ponytail: reuse before write-new)
_UPI_RE = re.compile(r"\b[\w.\-]{3,50}@[a-zA-Z]{3,20}\b")
_BANK_ACCOUNT_RE = re.compile(r"(?:account|a/?c|ifsc|acc\.?\s*no)\D{0,15}\d{9,18}", re.I)

_PAYMENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (_UPI_RE, "upi_id_or_email"),
    # Context-anchored: requires keyword within 15 non-digit chars before the number.
    # Aadhaar (12 digits) detected first and suppresses overlap — see _analyze_text.
    (_BANK_ACCOUNT_RE, "bank_account"),
    (re.compile(r"within\s+(?:24|48|2|4|6|12)\s*hours?", re.I), "urgent_deadline"),
    (re.compile(r"pay\s+(?:immediately|now|urgently)", re.I), "immediate_payment"),
    (re.compile(r"(?:send|transfer|deposit)\s+(?:money|amount|funds|cash)", re.I), "transfer_demand"),
]

_AADHAAR_RE = re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")
_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_PAYMENT_TYPES = frozenset(label for _, label in _PAYMENT_PATTERNS)

_vision_client = None


def load_vision_client() -> None:
    """Initialize Vision client at startup. Fault-tolerant — server starts without it."""
    global _vision_client
    if _vision_client is not None:
        return
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        print("WARNING: GOOGLE_APPLICATION_CREDENTIALS not set — document OCR unavailable.")
        return
    try:
        _vision_client = _gcp_vision.ImageAnnotatorClient()
    except Exception as exc:
        print(f"WARNING: Vision client init failed: {exc}")


def get_vision_client():
    if _vision_client is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Document OCR unavailable — GOOGLE_APPLICATION_CREDENTIALS not set "
                "or invalid. Set the env var and restart."
            ),
        )
    return _vision_client


# ── Rule engine ───────────────────────────────────────────────────────────────

def _analyze_text(text: str) -> tuple[list[ScamIndicator], list[PIIMatch]]:
    """Pure rule-based analysis of OCR text. Returns (scam_indicators, pii_matches)."""
    indicators: list[ScamIndicator] = []
    pii: list[PIIMatch] = []
    seen: set[str] = set()

    # Aadhaar first — spans used below to suppress bank_account overlap
    aadhaar_spans: list[tuple[int, int]] = []
    for m in _AADHAAR_RE.finditer(text):
        aadhaar_spans.append(m.span())
        last4 = re.sub(r"\D", "", m.group())[-4:]
        pii.append(PIIMatch(type="aadhaar", masked_value=f"XXXX-XXXX-{last4}"))

    for m in _PAN_RE.finditer(text):
        raw = m.group()
        pii.append(PIIMatch(type="pan", masked_value=raw[:3] + "XXXXXX" + raw[-1]))

    for pattern, label in _SCAM_PATTERNS:
        if label not in seen:
            m = pattern.search(text)
            if m:
                indicators.append(ScamIndicator(type=label, matched_text=m.group()[:120]))
                seen.add(label)

    for pattern, label in _PAYMENT_PATTERNS:
        if label in seen:
            continue
        if label == "bank_account":
            for m in pattern.finditer(text):
                digit_m = re.search(r"\d{9,18}$", m.group())
                if not digit_m:
                    continue
                d_start = m.start() + digit_m.start()
                d_end = m.start() + digit_m.end()
                overlaps = any(d_start < ae and d_end > as_ for as_, ae in aadhaar_spans)
                if not overlaps:
                    indicators.append(ScamIndicator(type=label, matched_text=m.group()[:120]))
                    seen.add(label)
                    break
        else:
            m = pattern.search(text)
            if m:
                indicators.append(ScamIndicator(type=label, matched_text=m.group()[:120]))
                seen.add(label)

    return indicators, pii


def _evidence_trail(indicators: list[ScamIndicator], pii: list[PIIMatch]) -> EvidenceTrail:
    """Normalized view of the same indicators/pii already returned — every match present raised risk."""
    items = [EvidenceItem(signal=ind.type, weight=1.0, contributed_to_verdict=True) for ind in indicators]
    items += [EvidenceItem(signal=f"pii:{p.type}", weight=1.0, contributed_to_verdict=True) for p in pii]
    return EvidenceTrail(items=items)


def _risk_level(indicators: list[ScamIndicator], pii: list[PIIMatch]) -> str:
    types = {ind.type for ind in indicators}
    has_scam = bool(types - _PAYMENT_TYPES)
    has_payment = bool(types & _PAYMENT_TYPES)
    if has_scam and has_payment:
        return "high"
    if has_scam or pii:
        return "medium"
    return "low"


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/document", response_model=ClassifyDocumentResponse)
async def classify_document(file: UploadFile = File(...)) -> ClassifyDocumentResponse:
    """
    Extract text from a document image via Google Cloud Vision OCR and analyse for
    Digital Arrest scam patterns and PII exposure.

    SCOPE: OCR + rule-based text analysis only. Does not detect image manipulation
    or forensic forgery. A low-risk result does not certify the document is genuine.
    """
    if file.content_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported type '{file.content_type}'. Allowed: {sorted(ALLOWED_DOCUMENT_TYPES)}",
        )

    data = await file.read()

    if len(data) > MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(data):,} bytes). Max: {MAX_DOCUMENT_BYTES:,} (10 MB).",
        )

    try:
        Image.open(io.BytesIO(data)).verify()
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="File is not a valid image or is corrupted.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not decode image: {exc}")

    client = get_vision_client()

    try:
        image = _gcp_vision.Image(content=data)
        response = client.text_detection(image=image)
        if response.error.message:
            raise HTTPException(
                status_code=503,
                detail=f"Google Vision API error: {response.error.message}",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Google Vision API unavailable: {exc}")

    texts = response.text_annotations
    ocr_text = texts[0].description if texts else ""

    if not ocr_text.strip():
        raise HTTPException(status_code=400, detail="No text detected in the document.")

    indicators, pii = _analyze_text(ocr_text)
    risk = _risk_level(indicators, pii)
    note = _SCOPE_NOTE + (_ANCHOR if risk in ("medium", "high") else "")

    return ClassifyDocumentResponse(
        ocr_text=ocr_text,
        pii_detected=pii,
        scam_indicators=indicators,
        risk_level=risk,
        note=note,
        disclaimer=DISCLAIMER,
        evidence_trail=_evidence_trail(indicators, pii),
    )
