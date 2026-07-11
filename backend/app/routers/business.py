"""
/business — B2B2C SDK licensing (item 69), freemium feature-gating (item
70), B2B matrimony/job-portal verification (item 76), and aggregated
threat-intel feed (item 77). Ported from the Track 2 collaborator repo's
app/routers/business.py.

ITEM 69 (SDK license check) rebuilt for real: the reference's version was
`len(api_key) > 10` with no registry at all — any 11-character string
"validated". Built a real one: a small `SDKApiKey` table of issued keys,
SHA256-hashed (never the raw key — same convention as B2BThreatIndicator
below), with a `tier` field reusing item 70's own `Literal["free","premium"]`
taxonomy. `POST /business/sdk/keys` issues/registers a key — dev-only
concept, no payment processing, same freemium-logic-not-payment-processing
scope as item 70 — and returns the raw key exactly once (it can never be
retrieved again, only re-validated by hash). `GET /business/sdk/validate`
gives a real HTTP 401 on an invalid/unregistered key, not a decorative
field riding on a 200.

FIXED during the port: the reference's /threat-intel endpoint
(`data={"indicators": list(THREAT_DATABASE)}`) returned RAW flagged phone
numbers in a supposedly "aggregated" feed — a real PII leak, and exactly
the kind of raw-PII storage this codebase's established convention
(SHA256-hash before persisting, see network_intel_db.py) exists to
prevent. Fixed: flagged contact numbers are SHA256-hashed before storage,
and the feed returns counts/platform breakdown only, never the numbers
themselves. Stored in a new dedicated table (B2BThreatIndicator), not
Track 3's PrivacyPreservingBlocklist/ThreatTaxonomy — none of the 4
existing taxonomy values (PHISHING_URL/MULE_ACCOUNT/VOICE_SPOOF/
MALICIOUS_APK) honestly describe a flagged listing/profile contact
number, and mislabeling it under one of those would be worse than a small
dedicated table. Needs real persistence — in-memory state defeats the
point of an "aggregated" feed, and this repo has zero tests.

No envelope; response_model= directly; `tier` validated as a real
Literal query param instead of the reference's un-validated free string
that silently treats anything other than "premium" as "free".
"""
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import Base, engine, get_db
from app.models.responses import (
    B2BProfileCheckResponse,
    FeatureGateResponse,
    SDKKeyIssueResponse,
    SDKKeyValidateResponse,
    ThreatIntelResponse,
)
from app.models.track2_db import B2BThreatIndicator, SDKApiKey

router = APIRouter(prefix="/business", tags=["B2B & SDK"])

_PREMIUM_FEATURES = {"remote_hangup", "multi_member"}

# Reused as-is from the reference — same phrase set as Kavach's own Digital Arrest logic.
_SCAM_PATTERNS = ["verification fee", "digital arrest", "pay for kit", "customs clearance", "ncrp complaint transfer"]


class _ProfileCheckRequest(BaseModel):
    platform: str = Field(..., min_length=1)
    profile_text: str = Field(..., min_length=1)
    contact_number: Optional[str] = None


class _SDKKeyIssueRequest(BaseModel):
    tier: Literal["free", "premium"] = "free"


_SDK_KEY_ISSUE_NOTE = "This raw key is shown once and cannot be retrieved again — store it securely."


def init_db() -> None:
    """Called at startup. Creates the B2B threat-intel table if it doesn't exist yet."""
    Base.metadata.create_all(bind=engine)


@router.post("/sdk/keys", response_model=SDKKeyIssueResponse)
async def issue_sdk_key(req: _SDKKeyIssueRequest, db: Session = Depends(get_db)) -> SDKKeyIssueResponse:
    """Issue a new SDK API key — dev-only concept, no payment processing behind `tier`."""
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    db.add(SDKApiKey(
        key_hash=key_hash,
        tier=req.tier,
        issued_at_utc=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db.commit()

    return SDKKeyIssueResponse(api_key=raw_key, tier=req.tier, note=_SDK_KEY_ISSUE_NOTE)


@router.get("/sdk/validate", response_model=SDKKeyValidateResponse)
async def validate_sdk_key(api_key: str = Query(..., min_length=1), db: Session = Depends(get_db)) -> SDKKeyValidateResponse:
    """Validate an SDK API key by its hash and return its tier. Real 401 on an unknown key."""
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    row = db.query(SDKApiKey).filter(SDKApiKey.key_hash == key_hash).first()
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid or unregistered SDK key.")

    return SDKKeyValidateResponse(valid=True, tier=row.tier)


@router.get("/sdk/feature-gate/{feature_name}", response_model=FeatureGateResponse)
async def freemium_gate(
    feature_name: str, tier: Literal["free", "premium"] = Query("free")
) -> FeatureGateResponse:
    """Feature-gating logic for the freemium family plan — no payment processing."""
    has_access = tier == "premium" or feature_name not in _PREMIUM_FEATURES
    return FeatureGateResponse(feature=feature_name, access_granted=has_access, requires_upgrade=not has_access)


@router.post("/verify-profile", response_model=B2BProfileCheckResponse)
async def verify_b2b_profile(req: _ProfileCheckRequest, db: Session = Depends(get_db)) -> B2BProfileCheckResponse:
    """Matrimony/job-portal listing pre-screen — reuses Kavach's own Digital Arrest phrase set."""
    text_lower = req.profile_text.lower()
    found_patterns = [p for p in _SCAM_PATTERNS if p in text_lower]
    risk_level = "high" if found_patterns else "low"

    if risk_level == "high" and req.contact_number:
        indicator_hash = hashlib.sha256(req.contact_number.encode()).hexdigest()
        existing = db.query(B2BThreatIndicator).filter(B2BThreatIndicator.sha256_hash == indicator_hash).first()
        if existing is None:
            db.add(B2BThreatIndicator(sha256_hash=indicator_hash, platform=req.platform))
            db.commit()

    return B2BProfileCheckResponse(risk_level=risk_level, flags_detected=found_patterns, platform=req.platform)


@router.get("/threat-intel", response_model=ThreatIntelResponse)
async def get_threat_intel(db: Session = Depends(get_db)) -> ThreatIntelResponse:
    """Aggregated threat-intel feed — counts and platform breakdown only, never raw contact numbers."""
    rows = db.query(B2BThreatIndicator).all()
    platforms = sorted({r.platform for r in rows})
    return ThreatIntelResponse(indicators_count=len(rows), platforms_represented=platforms)
