"""
/check/social-profile — Heuristic scoring for fake/impersonation social media profiles.

SCOPE: Scores only manually-provided profile attributes — no network calls, no scraping,
no unofficial APIs. The user copies what they see from the profile. A well-resourced fake
with purchased followers, an aged account, and a stolen real photo will score LOW here.
This is a coarse heuristic filter for obviously sloppy fakes, not a definitive detector.
"""
import re
from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.models.responses import (
    DISCLAIMER,
    CheckSocialProfileResponse,
    EvidenceItem,
    EvidenceTrail,
    ScoreEntry,
)

_HIGH_SCORE = 7
_MEDIUM_SCORE = 4

# A genuine new account normally follows people before anyone follows back —
# only flag once "following" count is high enough to look automated rather than curious.
_MASS_FOLLOWING_MIN_FOLLOWING = 400
_LOW_FOLLOWER_RATIO_MIN_FOLLOWING = 250

router = APIRouter(prefix="/check", tags=["social-profile"])

_LIMITATION_NOTE = (
    "Scores only manually-provided attributes — cannot fetch live data. "
    "A well-resourced fake with purchased followers, an aged account, and a stolen real photo "
    "will score LOW here. This is a coarse filter for obviously sloppy fakes, not a definitive detector."
)
_SCAM_ANCHOR = (
    "No Indian government agency conducts arrests via video call or demands payment verification online."
)

_GOV_RE = re.compile(
    r"\b(cbi|ips|ias|rbi|trai|sebi|ncb|enforcement|customs|income.?tax|narcotics|police)\b", re.I
)
_LEGITIMACY_RE = re.compile(r"\b(official|verified|real|authentic|genuine)\b", re.I)
_URGENCY_RE = re.compile(
    r"\b(urgent|emergency|pay now|upi|arrest|case registered|verification fee)\b", re.I
)
_GENERIC_BIO_PHRASES = ("dm for business", "follow for follow", "f4f", "l4l", "collab dm")
_FINANCIAL_REGULATOR_RE = re.compile(r"\b(rbi|sebi|trai)\b", re.I)
_REGULATORY_DISCLAIMER_RE = re.compile(
    r"\b(licensed|regulated|grievance redressal|nbfc|registration no\.?|licence no\.?)\b", re.I
)


class _SocialProfileRequest(BaseModel):
    platform: Literal["instagram", "facebook", "twitter", "whatsapp", "telegram", "other"]
    has_profile_photo: bool
    profile_photo_is_stock: Optional[bool] = None
    account_age_days: Optional[int] = Field(None, ge=0)
    follower_count: Optional[int] = Field(None, ge=0)
    following_count: Optional[int] = Field(None, ge=0)
    post_count: Optional[int] = Field(None, ge=0)
    bio_text: Optional[str] = Field(None, max_length=500)
    display_name: Optional[str] = Field(None, max_length=100)
    is_verified: bool = False


def _score_profile(req: _SocialProfileRequest) -> list[ScoreEntry]:
    """Return scored entries for each signal found. Points > 0 = red flag; < 0 = mitigating."""
    entries: list[ScoreEntry] = []

    def add(flag: str, points: int, reason: str) -> None:
        entries.append(ScoreEntry(flag=flag, points=points, reason=reason))

    # --- Profile photo
    if not req.has_profile_photo:
        add("no_profile_photo", 3, "No profile photo — common in freshly created fake accounts")
    elif req.profile_photo_is_stock:
        add("stock_photo", 3, "Profile photo appears stock or AI-generated — possible stolen or synthesised identity")

    # --- Account age
    if req.account_age_days is not None:
        if req.account_age_days < 30:
            add("very_new_account", 3, f"Account only {req.account_age_days} day(s) old — brand new")
        elif req.account_age_days < 90:
            add("recently_created", 2, f"Account created {req.account_age_days} days ago — relatively new")

    # --- Follower / following ratio (divide-by-zero safe)
    if req.follower_count is not None and req.following_count is not None:
        fc, fg = req.follower_count, req.following_count
        if fg > 0:
            ratio = fc / fg
            if ratio < 0.1 and fg >= _MASS_FOLLOWING_MIN_FOLLOWING:
                add("mass_following", 3, f"Follows {fg} but only {fc} follower(s) back (ratio {ratio:.2f}) — mass-following bot pattern")
            elif ratio < 0.3 and fg >= _LOW_FOLLOWER_RATIO_MIN_FOLLOWING:
                add("low_follower_ratio", 2, f"Follower/following ratio {ratio:.2f} with {fg} following — possible follow-to-get-followed behaviour")
        else:
            if fc == 0:
                add("no_social_presence", 2, "Zero followers and zero following — socially inactive account")
    elif req.follower_count is not None and req.follower_count == 0:
        add("no_followers", 2, "Zero followers on the account")

    # --- Post count (not applicable to WhatsApp / Telegram)
    if req.post_count is not None and req.platform not in ("whatsapp", "telegram"):
        if req.post_count == 0:
            add("no_posts", 3, "No posts — account exists but has never posted")
        elif req.post_count < 5 and (req.account_age_days is None or req.account_age_days >= 30):
            add("very_few_posts", 2, f"Only {req.post_count} post(s) for an account that is not brand new")

    # --- Display name signals
    if req.display_name:
        digit_count = sum(c.isdigit() for c in req.display_name)
        if digit_count >= 3:
            add("digits_in_name", 1, f"Display name contains {digit_count} digits — common in auto-generated accounts")
        m = _LEGITIMACY_RE.search(req.display_name)
        if m:
            add("self_claimed_legitimacy", 2, f"Name contains '{m.group()}' — legitimate accounts rarely assert this")
        m = _GOV_RE.search(req.display_name)
        if m:
            add("gov_impersonation_in_name", 4, f"Name suggests impersonation of '{m.group().upper()}' — primary Digital Arrest scam tactic")

    # --- Bio text signals
    if req.bio_text:
        m = _GOV_RE.search(req.bio_text)
        if m and not (
            _FINANCIAL_REGULATOR_RE.fullmatch(m.group()) and _REGULATORY_DISCLAIMER_RE.search(req.bio_text)
        ):
            add("gov_impersonation_in_bio", 4, f"Bio claims association with '{m.group().upper()}' — verify through official channels only")
        m = _URGENCY_RE.search(req.bio_text)
        if m:
            add("urgency_in_bio", 4, f"Bio contains suspicious keyword: '{m.group()}' — payment/arrest language in a social profile bio is a red flag")
        for phrase in _GENERIC_BIO_PHRASES:
            if phrase in req.bio_text.lower():
                add("generic_bio", 1, f"Bio contains generic placeholder phrase: '{phrase}'")
                break

    # --- Verification (mitigation — not exoneration)
    if req.is_verified:
        add("verified_badge", -2, "Account has a verified badge — reduces but does not eliminate risk")

    return entries


def _evidence_trail(entries: list[ScoreEntry]) -> EvidenceTrail:
    """Same score_breakdown entries, normalized: positive-point entries are the ones that raised risk."""
    return EvidenceTrail(items=[
        EvidenceItem(signal=e.flag, weight=float(e.points), contributed_to_verdict=e.points > 0)
        for e in entries
    ])


def _build_note(risk: str, red_flags: list[str]) -> str:
    parts: list[str] = []
    if red_flags:
        shown = red_flags[:3]
        suffix = "..." if len(red_flags) > 3 else ""
        parts.append(f"Red flags detected: {', '.join(shown)}{suffix}.")
    if risk in ("medium", "high"):
        parts.append(_SCAM_ANCHOR)
    parts.append(_LIMITATION_NOTE)
    return " ".join(parts)


@router.post("/social-profile", response_model=CheckSocialProfileResponse)
async def check_social_profile(req: _SocialProfileRequest) -> CheckSocialProfileResponse:
    """Score a social media profile for fake/impersonation indicators from manually-entered attributes."""
    entries = _score_profile(req)
    raw_total = sum(e.points for e in entries)
    total = max(0, raw_total)
    red_flags = [e.flag for e in entries if e.points > 0]
    risk: Literal["low", "medium", "high"] = (
        "high" if total >= _HIGH_SCORE else "medium" if total >= _MEDIUM_SCORE else "low"
    )
    return CheckSocialProfileResponse(
        risk_level=risk,
        total_score=total,
        red_flags=red_flags,
        score_breakdown=entries,
        note=_build_note(risk, red_flags),
        disclaimer=DISCLAIMER,
        evidence_trail=_evidence_trail(entries),
    )
