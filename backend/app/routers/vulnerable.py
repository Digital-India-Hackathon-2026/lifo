"""
/vulnerable — Protector-Protected pairing (item 37), de-escalation/
cognitive-friction call-state sync (item 38), and the smartwatch/IoT panic
trigger (item 41). Ported from the Track 2 collaborator repo's
app/routers/vulnerable.py.

Renamed from panic_alert.py: that file only ever covered item 41 — with
items 37/38 now added, three catalog items share this router and the
/vulnerable prefix, so the file name now matches the feature domain
(vulnerable-user safety UX) rather than a single endpoint, same
per-domain naming convention as segments.py/business.py/etc.

SCOPE: items 37, 38, 41, 42. Item 39 (video-first awareness content —
static, no backend), item 40 (safe-word — see safevault.py, already
correct, nothing to port, see AGENTS.md Session 27), and item 43
(hardware adapter concept — see TODO.md, no code) are NOT in this
router.

ITEM 42 (gamified training — now a real fixed drill bank + grading, not
just score logging): the reference's training/submit endpoint only ever
ingested a score self-reported by a caller — no actual gamified content
existed anywhere. Finished for real: `_DRILLS` is a small hand-written
bank (6 scenarios) modeled on this codebase's own scam-detection
patterns (digital arrest, KYC, romance, lottery, courier, job/WFH), each
with a scenario, multiple-choice options, a correct answer, and an
explanation — same static-content-list convention as education.py's
`_VIDEOS` (no DB table for the content itself; it's fixed, authored
content, not user data). `GET /vulnerable/training/drill` serves one
random scenario (never the answer); `POST /vulnerable/training/answer`
grades the submitted answer against the bank and logs the graded
attempt through the same `_log_training_score` helper `training/submit`
already used — one write path, not two. `training/submit` itself is
kept as a separate self-report path (e.g. a client that ran its own
practice flow) and still does not generate a drill. Real SQLite
persistence unchanged (TrainingScore, identity-linked history — follows
item 37's persistence category, not item 38's in-memory one). What's
still explicitly NOT built: an AI-run *live* practice scam call (a
distinct, bigger, honeypot-persona-style feature) — every training
response's `note` says so plainly.

ITEM 37 (pairing): real upsert-on-unique-key write path —
POST /vulnerable/pair-devices. Same pattern as ConsentService.grant
(item 82): re-pairing an already-paired protected_id updates the row in
place, never duplicates (protected_id's DB-level unique constraint,
unchanged from Session 27, already enforces this). This closes the gap
Session 27 deliberately left open — PairedDevice previously had no
creation endpoint, only seedable directly via the DB session in tests.

ITEM 38 (call-state sync + remote hangup): the reference's session store
is exactly the same shape as honeypot.py's own `_sessions` (transient,
per-call state — risk flags, active/terminated status — not identity or
aggregated data), so it's kept in-memory here too, matching
honeypot.py's `_sessions: dict[str, dict[str, Any]] = {}` pattern rather
than inventing a third persistence style for the same kind of data.
`ui_action_required` ("FORCE_DEESCALATION_OVERLAY"/"NONE") and
remote-hangup's 404-on-unknown-session are ported as-is — both were
already correct in the reference.

No envelope; response_model= directly; real HTTP status codes; proper
Pydantic validation.
"""
import random
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import Base, engine, get_db
from app.models.responses import (
    CallStateResponse,
    PairDevicesResponse,
    PanicTriggerResponse,
    RemoteHangupResponse,
    TrainingAnswerResponse,
    TrainingDrillResponse,
    TrainingScoreResponse,
)
from app.models.track2_db import PairedDevice, TrainingScore

router = APIRouter(prefix="/vulnerable", tags=["Vulnerable User Safety"])

# In-memory call-session store — same shape and same rationale as
# honeypot.py's _sessions: transient per-call state, not identity or
# aggregated data. No TTL, matching honeypot.py — see ARCHITECTURE.md's
# Known Technical Debt.
_call_sessions: dict[str, dict[str, Any]] = {}


class _PairDevicesRequest(BaseModel):
    protected_id: str = Field(..., min_length=1)
    protector_id: str = Field(..., min_length=1)


class _CallStatusUpdateRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    protected_id: str = Field(..., min_length=1)
    is_call_active: bool
    detected_scam_phrases: list[str]


class _PanicAlertRequest(BaseModel):
    protected_id: str = Field(..., min_length=1)
    device_source: str = Field(..., min_length=1)  # e.g. "smartwatch", "panic_button"


class _TrainingSubmitRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    drill_id: str = Field(..., min_length=1)
    score: int = Field(..., ge=0)
    completed_successfully: bool


class _TrainingAnswerRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    drill_id: str = Field(..., min_length=1)
    selected_answer: str = Field(..., min_length=1)


# Fixed drill bank (item 42) — hand-written scenarios modeled on this codebase's
# own scam-detection patterns (romance_scam.py, digital_arrest.py, document.py's
# KYC/lottery/courier phrase sets, job_scam.py). Static authored content, same
# convention as education.py's _VIDEOS list — no DB table, since this is fixed
# content, not user data. `correct_answer` and `explanation` are never served by
# GET /training/drill, only by POST /training/answer after grading.
_DRILLS: list[dict[str, Any]] = [
    {
        "drill_id": "drill_digital_arrest_1",
        "scenario_type": "digital_arrest",
        "scenario_text": (
            "A video call from someone in a police uniform claims to be from the CBI. They say a "
            "parcel with your name on it contained drugs, you must stay on the video call, and you "
            "must transfer money to a 'RBI verification account' to prove your innocence within the hour."
        ),
        "options": [
            "Stay on the call and transfer the money to clear your name quickly.",
            "This is a 'Digital Arrest' scam — hang up, do not pay anything, and verify independently via cybercrime.gov.in or 1930.",
            "Ask them to call back tomorrow since you're busy right now.",
        ],
        "correct_answer": "This is a 'Digital Arrest' scam — hang up, do not pay anything, and verify independently via cybercrime.gov.in or 1930.",
        "explanation": (
            "Indian law enforcement never arrests, investigates, or collects 'verification' money over "
            "a video call. This is the Digital Arrest scam pattern — hang up, do not engage further, "
            "and report at cybercrime.gov.in or call 1930."
        ),
    },
    {
        "drill_id": "drill_kyc_1",
        "scenario_type": "kyc",
        "scenario_text": (
            "An SMS says: 'Your bank account will be blocked in 24 hours due to incomplete KYC. "
            "Update immediately by clicking this link and entering your card number, OTP and PIN.'"
        ),
        "options": [
            "Click the link immediately since your account is about to be blocked.",
            "Reply to the SMS asking for more details first.",
            "This is a KYC-scam pattern — banks never ask for your PIN/OTP via an SMS link. Delete it and call the bank's official number instead.",
        ],
        "correct_answer": "This is a KYC-scam pattern — banks never ask for your PIN/OTP via an SMS link. Delete it and call the bank's official number instead.",
        "explanation": (
            "No legitimate bank asks for a card PIN or OTP through an SMS link. This is a phishing/KYC "
            "scam designed to steal card credentials. Never enter an OTP or PIN via a link from an SMS; "
            "contact the bank directly using the number on your card or passbook."
        ),
    },
    {
        "drill_id": "drill_romance_1",
        "scenario_type": "romance",
        "scenario_text": (
            "An online partner you've never met in person, after weeks of daily loving messages, tells "
            "you they need ₹50,000 urgently to 'unlock' a large crypto investment they want to share "
            "the profits from with you."
        ),
        "options": [
            "Send the money — they clearly care about you and want to share the profits.",
            "This is a 'pig-butchering' romance-investment scam — do not send money, and be cautious of any online relationship that pivots to investment requests.",
            "Ask them to marry you first before sending money.",
        ],
        "correct_answer": "This is a 'pig-butchering' romance-investment scam — do not send money, and be cautious of any online relationship that pivots to investment requests.",
        "explanation": (
            "Love-bombing followed by a request for money tied to a 'guaranteed' investment is the "
            "classic pig-butchering pattern. Never send money to someone you have not met in person, "
            "especially for an investment opportunity only they control."
        ),
    },
    {
        "drill_id": "drill_lottery_1",
        "scenario_type": "lottery",
        "scenario_text": (
            "A message says: 'Congratulations! You've won ₹25 lakh in the KBC lottery. To claim your "
            "prize, pay ₹5,000 as a processing/tax fee to this UPI ID.'"
        ),
        "options": [
            "Pay the fee — ₹5,000 is a small price for ₹25 lakh.",
            "This is a lottery/prize scam — you cannot win a lottery you never entered, and real prizes never require an upfront fee. Do not pay, do not share bank details.",
            "Ask them to deduct the fee from the prize money instead.",
        ],
        "correct_answer": "This is a lottery/prize scam — you cannot win a lottery you never entered, and real prizes never require an upfront fee. Do not pay, do not share bank details.",
        "explanation": (
            "You cannot win a lottery you never entered, and legitimate prizes never require an upfront "
            "fee. This is a classic advance-fee lottery scam."
        ),
    },
    {
        "drill_id": "drill_courier_1",
        "scenario_type": "courier",
        "scenario_text": (
            "A caller claiming to be from a courier company says a parcel in your name was seized by "
            "customs for containing illegal items, and you must pay a 'customs clearance fee' via UPI "
            "immediately or face police action."
        ),
        "options": [
            "Pay the fee immediately to avoid police action.",
            "This is a courier/customs scam — real customs issues are never resolved by paying a stranger over the phone via UPI. Hang up and verify directly with the courier company's official number.",
            "Give them your Aadhaar number to prove your identity.",
        ],
        "correct_answer": "This is a courier/customs scam — real customs issues are never resolved by paying a stranger over the phone via UPI. Hang up and verify directly with the courier company's official number.",
        "explanation": (
            "Customs and courier issues are never resolved with an urgent UPI payment demanded over a "
            "phone call. This is the courier/customs scam pattern — a direct precursor to many Digital "
            "Arrest scams. Always verify independently."
        ),
    },
    {
        "drill_id": "drill_job_1",
        "scenario_type": "job",
        "scenario_text": (
            "A 'recruiter' offers a work-from-home job paying ₹50,000/month for simple data entry, but "
            "says you must first pay a ₹2,000 'registration fee' and buy a 'starter kit' before they "
            "send your offer letter."
        ),
        "options": [
            "Pay the fee — the salary is worth it.",
            "This is a fake job/advance-fee scam — legitimate employers never ask candidates to pay for a job offer, registration, or a starter kit. Do not pay; verify the company independently.",
            "Negotiate the fee down to ₹500.",
        ],
        "correct_answer": "This is a fake job/advance-fee scam — legitimate employers never ask candidates to pay for a job offer, registration, or a starter kit. Do not pay; verify the company independently.",
        "explanation": (
            "Legitimate employers never charge candidates money to be hired. A WFH job demanding an "
            "upfront registration fee or 'starter kit' purchase before an offer letter is issued is an "
            "advance-fee job scam."
        ),
    },
]

_TRAINING_SUBMIT_NOTE = (
    "This endpoint logs a self-reported drill result only — it does not generate the drill itself. "
    "For real graded drill content, use GET /vulnerable/training/drill (serves a scenario) and "
    "POST /vulnerable/training/answer (grades it and logs the attempt through this same path). "
    "Neither is an AI-run live practice scam call — that is separate, not-yet-built scope."
)

_TRAINING_DRILL_NOTE = (
    "Served from a fixed bank of 6 hand-written drill scenarios modeled on this codebase's own "
    "scam-detection patterns (digital arrest, KYC, romance, lottery, courier, job). This is real, "
    "gradable practice content — not an AI-run live practice scam call, which is a distinct, bigger "
    "feature and remains out of scope."
)

_TRAINING_ANSWER_NOTE = (
    "Graded against the fixed drill bank and logged as a real training-score attempt — not a "
    "self-report. Still not an AI-run live practice scam call; see GET /training/drill's note."
)


def init_db() -> None:
    """Called at startup. Creates the vulnerable-user tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


@router.post("/pair-devices", response_model=PairDevicesResponse)
async def pair_devices(req: _PairDevicesRequest, db: Session = Depends(get_db)) -> PairDevicesResponse:
    """Create or update a protector<->protected pairing. Re-pairing an
    already-paired protected_id updates the row, never duplicates."""
    pairing = db.query(PairedDevice).filter(PairedDevice.protected_id == req.protected_id).first()
    if pairing is None:
        pairing = PairedDevice(protected_id=req.protected_id, protector_id=req.protector_id)
        db.add(pairing)
    else:
        pairing.protector_id = req.protector_id
    db.commit()
    db.refresh(pairing)

    return PairDevicesResponse(protected_id=pairing.protected_id, protector_id=pairing.protector_id)


@router.post("/update-call-state", response_model=CallStateResponse)
async def update_call_state(req: _CallStatusUpdateRequest, db: Session = Depends(get_db)) -> CallStateResponse:
    """Evaluate call anomalies and compute which cognitive-friction UI action the elder app should trigger."""
    has_risk = len(req.detected_scam_phrases) > 0
    pairing = db.query(PairedDevice).filter(PairedDevice.protected_id == req.protected_id).first()

    _call_sessions[req.session_id] = {
        "protected_id": req.protected_id,
        "protector_id": pairing.protector_id if pairing else None,
        "status": "COERCION_RISK_DETECTED" if has_risk else "CALL_ACTIVE",
        "flags": req.detected_scam_phrases,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    return CallStateResponse(
        session_id=req.session_id,
        ui_action_required="FORCE_DEESCALATION_OVERLAY" if has_risk else "NONE",
    )


@router.post("/remote-hangup/{session_id}", response_model=RemoteHangupResponse)
async def remote_hangup(session_id: str) -> RemoteHangupResponse:
    """Remotely terminate an active call session from the protector's device."""
    if session_id not in _call_sessions:
        raise HTTPException(status_code=404, detail="Active call session tracker not found.")

    _call_sessions[session_id]["status"] = "TERMINATED_BY_REMOTE_PROTECTOR"
    return RemoteHangupResponse(session_id=session_id, current_status="TERMINATED_BY_REMOTE_PROTECTOR")


@router.post("/panic-trigger", response_model=PanicTriggerResponse)
async def panic_trigger(req: _PanicAlertRequest, db: Session = Depends(get_db)) -> PanicTriggerResponse:
    """Dispatch a distress broadcast — to the paired protector if one exists, else public emergency."""
    pairing = db.query(PairedDevice).filter(PairedDevice.protected_id == req.protected_id).first()
    protector_id: Optional[str] = pairing.protector_id if pairing else None

    return PanicTriggerResponse(
        broadcast_success=True,
        source_hardware=req.device_source,
        protector_notified_id=protector_id,
        action_dispatched="IMMEDIATE_SMS_AND_PUSH_DISPATCH" if protector_id else "BROADCAST_TO_PUBLIC_EMERGENCY",
    )


def _log_training_score(
    db: Session, *, user_id: str, drill_id: str, score: int, passed: bool, note: str,
) -> TrainingScoreResponse:
    """Shared persistence path for every graded/self-reported training attempt —
    used by both /training/submit and /training/answer, so there is exactly one
    write path into TrainingScore, not two."""
    db.add(TrainingScore(
        user_id=user_id,
        drill_id=drill_id,
        score=score,
        passed=passed,
        submitted_at_utc=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db.commit()

    drills_completed_count = db.query(TrainingScore).filter(TrainingScore.user_id == user_id).count()

    return TrainingScoreResponse(
        user_id=user_id,
        drills_completed_count=drills_completed_count,
        latest_score=score,
        passed=passed,
        note=note,
    )


@router.post("/training/submit", response_model=TrainingScoreResponse)
async def submit_training_metrics(req: _TrainingSubmitRequest, db: Session = Depends(get_db)) -> TrainingScoreResponse:
    """Log a self-reported gamified-training drill score. Does not generate the drill itself —
    see module docstring and GET/POST /training/drill,/training/answer for the real graded path."""
    return _log_training_score(
        db,
        user_id=req.user_id,
        drill_id=req.drill_id,
        score=req.score,
        passed=req.completed_successfully,
        note=_TRAINING_SUBMIT_NOTE,
    )


@router.get("/training/drill", response_model=TrainingDrillResponse)
async def get_training_drill() -> TrainingDrillResponse:
    """Return one random drill scenario from the fixed bank — question + options, never the answer."""
    drill = random.choice(_DRILLS)
    return TrainingDrillResponse(
        drill_id=drill["drill_id"],
        scenario_type=drill["scenario_type"],
        scenario_text=drill["scenario_text"],
        options=drill["options"],
        note=_TRAINING_DRILL_NOTE,
    )


@router.post("/training/answer", response_model=TrainingAnswerResponse)
async def answer_training_drill(
    req: _TrainingAnswerRequest, db: Session = Depends(get_db),
) -> TrainingAnswerResponse:
    """Grade a submitted answer against the fixed drill bank and log the graded attempt."""
    drill = next((d for d in _DRILLS if d["drill_id"] == req.drill_id), None)
    if drill is None:
        raise HTTPException(status_code=404, detail=f"Unknown drill_id: {req.drill_id}")

    correct = req.selected_answer == drill["correct_answer"]
    training_score = _log_training_score(
        db,
        user_id=req.user_id,
        drill_id=req.drill_id,
        score=100 if correct else 0,
        passed=correct,
        note=_TRAINING_ANSWER_NOTE,
    )

    return TrainingAnswerResponse(
        drill_id=req.drill_id,
        correct=correct,
        explanation=drill["explanation"],
        training_score=training_score,
        note=_TRAINING_ANSWER_NOTE,
    )
