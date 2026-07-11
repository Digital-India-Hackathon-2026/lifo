"""
/assist/complaint — Template engine for NCRP cybercrime complaint and bank dispute email.
/legal/templates/ezero-fir — e-Zero FIR scaffold generator (Track 3, item 65).
/legal/dispute/* — Bank Dispute + Ombudsman Auto-Escalation tracking (item 64).

SCOPE: Pure templating over user-provided incident fields. No ML, no external API calls,
no new dependencies. Accepts structured JSON that can be filled in directly by the user
or forwarded from /check/digital-arrest / /classify/document responses.

No router-level prefix: /legal/templates/ezero-fir and /legal/dispute/* live under a
different top-level path than /assist/complaint, so each route declares its own full
path explicitly on this single router object instead — same domain (legal document
templating + tracking), same file, same main.py mount, per the established
one-router-per-domain convention.

ITEM 64 (Bank Dispute + Ombudsman Auto-Escalation): the existing bank-dispute template
(_build_bank_dispute, below) generates a static email with no tracking of whether/when
the bank responds and no escalation when they miss the RBI-mandated deadline — that's
the actual gap this catalog item asks to close. POST /legal/dispute/track reuses
_build_bank_dispute() directly (not a duplicate copy) as the source of truth for what
"raising a dispute" means, then persists a DisputeCase (new legal_db.py) to track it.
rbi_deadline_at is dispute_raised_at + 90 days, per the RBI Master Direction on
Limiting Liability of Customers in Unauthorised Electronic Banking Transactions
(RBI/2017-18/15, already cited in the template below) — that Direction requires banks
to complete resolution of an unauthorised-transaction dispute within 90 days of the
complaint being received. GET /legal/dispute/{case_id}/status computes is_overdue on
demand — there is no scheduler in this stack to auto-flag a case the instant its
deadline passes, same on-demand-only limitation as item 82's purge_expired (see
ARCHITECTURE.md Known Technical Debt). POST /legal/dispute/{case_id}/escalate only
succeeds once is_overdue is true (409 otherwise, never a silent no-op) and references
filing with the RBI Banking Ombudsman via the RBI's Complaint Management System
(cms.rbi.org.in) — the current mechanism under the RBI Integrated Ombudsman Scheme,
2021, which unified the erstwhile Banking Ombudsman Scheme into one online system.

No new router file, no new service module: this file already owns the "legal" domain
and already has _build_bank_dispute() to reuse (same precedent as item 65, added here
rather than a new file — see AGENTS.md Session 22). Logic lives directly in the router
functions below, not a separate service class — matches campaign_timeline.py (item 30),
the most recently built comparably-scoped new feature, which made the same call for the
same reason (four small functions don't need an extra abstraction layer).
"""
import datetime
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import Base, engine, get_db
from app.models.legal_db import DisputeCase
from app.models.responses import (
    DISCLAIMER,
    ComplaintResponse,
    DisputeEscalationResponse,
    DisputeStatusResponse,
    DisputeTrackResponse,
    EZeroFIRResponse,
)
from app.services.legal_templates import generate_ezero_fir

router = APIRouter(tags=["complaint"])

_NEXT_STEPS = [
    "File your complaint online at cybercrime.gov.in — available 24/7.",
    "Call 1930 (National Cyber Crime Helpline) immediately — report the incident verbally and get a reference number.",
    "Report to your bank right away — request an immediate hold on the recipient account; the sooner you report, the better the chance of fund recovery before money is moved further.",
    "Collect and preserve all evidence: screenshots, call recordings, transaction receipts, UPI app history.",
    "Do NOT pay anyone who claims they can help recover the money — this is a common follow-up scam.",
    "Share the NCRP complaint number with your bank to strengthen the dispute.",
]

_DIVIDER = "━" * 50
_LEGAL_NOTE = (
    "NOTE: Legal section references are current as of this writing; verify current "
    "section numbers with the NCRP portal or a legal professional before filing, "
    "as citations can be amended."
)


def _ph(value: Optional[str], label: str) -> str:
    """Return value if present, else a bracketed placeholder."""
    return value.strip() if value and value.strip() else f"[{label}]"


def _fmt_amount(amount: Optional[float]) -> str:
    if amount is None:
        return "[AMOUNT]"
    return f"₹{amount:,.2f}"


def _fmt_patterns(patterns: Optional[list[str]]) -> str:
    if not patterns:
        return "[none recorded]"
    return ", ".join(patterns)


def _build_ncrp(req: "ComplaintRequest") -> str:
    today = datetime.date.today().strftime("%d %B %Y")
    lines = [
        "COMPLAINT — CYBER FINANCIAL FRAUD (DIGITAL ARREST SCAM)",
        "To: National Cyber Crime Reporting Portal",
        "    cybercrime.gov.in  |  Helpline: 1930",
        "",
        f"Filed On: {today}",
        "",
        _DIVIDER,
        "COMPLAINANT DETAILS",
        _DIVIDER,
        f"Name:    {_ph(req.complainant_name, 'FULL NAME')}",
        f"Phone:   {_ph(req.complainant_phone, 'PHONE NUMBER')}",
        f"Email:   {_ph(req.complainant_email, 'EMAIL ADDRESS')}",
        f"Address: {_ph(req.complainant_address, 'FULL ADDRESS')}",
        "",
        _DIVIDER,
        "INCIDENT DETAILS",
        _DIVIDER,
        f"Date & Time of Fraud:  {_ph(req.incident_date, 'DATE AND TIME')}",
        f"Platform / Mode:       {_ph(req.platform_used, 'e.g. WhatsApp video call / phone call')}",
        "Nature of Fraud:       Digital Arrest — Impersonation of Government Official",
    ]
    if req.matched_patterns:
        lines.append(f"Scam Patterns Detected: {_fmt_patterns(req.matched_patterns)}")
    lines += [
        "",
        _DIVIDER,
        "INCIDENT DESCRIPTION",
        _DIVIDER,
        _ph(req.incident_description, "DESCRIBE WHAT HAPPENED — who contacted you, what they claimed, what threats were made, what you were told to do"),
        "",
        _DIVIDER,
        "FINANCIAL LOSS",
        _DIVIDER,
        f"Amount Lost:                    {_fmt_amount(req.amount_lost)}",
        f"Mode of Payment:                {_ph(req.payment_mode, 'UPI / NEFT / RTGS / IMPS')}",
        f"Transaction Reference / UTR:    {_ph(req.transaction_reference, 'UTR OR REFERENCE NUMBER')}",
        f"Date of Transaction:            {_ph(req.transaction_date, 'DATE OF TRANSFER')}",
        f"Recipient UPI ID / Account:     {_ph(req.recipient_account, 'RECIPIENT UPI ID OR ACCOUNT NUMBER')}",
    ]
    if req.payment_indicators:
        lines.append(f"Payment Indicators:             {_fmt_patterns(req.payment_indicators)}")
    lines += [
        "",
        _DIVIDER,
        "SUSPECT DETAILS (if known)",
        _DIVIDER,
        f"Name Claimed:        {_ph(req.suspect_name, 'NAME GIVEN BY CALLER')}",
        f"Phone Number Used:   {_ph(req.suspect_phone, 'CALLER PHONE NUMBER')}",
        f"UPI ID Provided:     {_ph(req.suspect_upi_id, 'UPI ID GIVEN FOR PAYMENT')}",
        f"Claimed Designation: {_ph(req.suspect_claimed_agency, 'e.g. CBI Officer / TRAI Department')}",
        "",
        _DIVIDER,
        "EVIDENCE AVAILABLE",
        _DIVIDER,
        "[ ] Screenshots of conversation / video call",
        "[ ] Call recording (if available)",
        "[ ] Transaction receipt / UPI app history",
        "[ ] Any documents or notices shared by the fraudster",
        "",
        _DIVIDER,
        "REQUESTED ACTION",
        _DIVIDER,
        "1. Immediate freeze of the fraudulent recipient account(s).",
        "2. Tracing, identification, and arrest of the suspect(s).",
        "3. Recovery and refund of the fraudulently transferred amount.",
        "4. Registration of FIR under relevant sections of the Information",
        "   Technology Act 2000 (§66C identity theft, §66D impersonation) and",
        "   Bharatiya Nyaya Sanhita 2023 (§318 cheating, §319 cheating by impersonation).",
        "",
        "I affirm that the above information is true and correct to the best of my knowledge.",
        "",
        "Signature: _____________________",
        f"Date:      {today}",
        "",
        _LEGAL_NOTE,
    ]
    return "\n".join(lines)


def _build_bank_dispute(req: "ComplaintRequest") -> str:
    today = datetime.date.today().strftime("%d %B %Y")
    acct_last4 = (req.account_number or "")[-4:] or "XXXX"
    subject = (
        f"URGENT — Fraudulent Transaction Dispute | "
        f"Account {acct_last4} | "
        f"Ref: {req.transaction_reference or '[UTR]'}"
    )
    lines = [
        f"Subject: {subject}",
        "",
        f"To: Customer Grievance / Nodal Officer",
        f"    {_ph(req.bank_name, 'BANK NAME')}",
        "",
        f"Date: {today}",
        "",
        "Dear Sir / Madam,",
        "",
        "I am writing to formally dispute a fraudulent transaction on my account",
        "and request immediate action to freeze the recipient account and reverse",
        "the transfer.",
        "",
        _DIVIDER,
        "ACCOUNT HOLDER DETAILS",
        _DIVIDER,
        f"Name:              {_ph(req.complainant_name, 'FULL NAME')}",
        f"Account Number:    {_ph(req.account_number, 'ACCOUNT NUMBER')}",
        f"Registered Phone:  {_ph(req.complainant_phone, 'REGISTERED PHONE')}",
        f"Email:             {_ph(req.complainant_email, 'EMAIL ADDRESS')}",
        "",
        _DIVIDER,
        "DISPUTED TRANSACTION",
        _DIVIDER,
        f"Transaction Date:      {_ph(req.transaction_date, 'DATE OF TRANSFER')}",
        f"Amount:                {_fmt_amount(req.amount_lost)}",
        f"Mode:                  {_ph(req.payment_mode, 'UPI / NEFT / RTGS / IMPS')}",
        f"Transaction Ref / UTR: {_ph(req.transaction_reference, 'UTR OR REFERENCE NUMBER')}",
        f"Transferred To:        {_ph(req.recipient_account, 'RECIPIENT UPI ID OR ACCOUNT')}",
        "",
        _DIVIDER,
        "REASON FOR DISPUTE",
        _DIVIDER,
        (
            f"I am the victim of a 'Digital Arrest' cybercrime fraud, a scheme in which "
            f"criminals impersonating {_ph(req.suspect_claimed_agency, 'government officials')} "
            f"coerced me into making the above payment under duress and threat of arrest. "
            f"This is a known fraud pattern formally flagged by the Ministry of Home Affairs "
            f"and the Reserve Bank of India."
        ),
        "",
        _ph(req.incident_description, "BRIEF DESCRIPTION OF WHAT HAPPENED"),
        "",
        _DIVIDER,
        "NCRP COMPLAINT REFERENCE",
        _DIVIDER,
        f"NCRP Complaint Number: {_ph(req.ncrp_complaint_number, 'FILE AT cybercrime.gov.in / 1930 — ENTER NUMBER HERE')}",
        "(Complaint filed with National Cyber Crime Reporting Portal / 1930 helpline.)",
        "",
        _DIVIDER,
        "REQUESTED ACTION",
        _DIVIDER,
        "1. Immediately freeze / place a hold on the recipient account listed above.",
        "2. Initiate transaction reversal / chargeback under the RBI Master Direction",
        "   on Limiting Liability of Customers in Unauthorised Electronic Banking",
        "   Transactions (RBI/2017-18/15).",
        "3. Coordinate with the receiving bank to freeze the fraudulent account.",
        "4. Provide written acknowledgment of this dispute within 24 hours.",
        "5. Share a complaint tracking number for follow-up.",
        "",
        "Yours faithfully,",
        _ph(req.complainant_name, "FULL NAME"),
        f"Phone: {_ph(req.complainant_phone, 'PHONE')}",
        f"Date:  {today}",
        "",
        _LEGAL_NOTE,
    ]
    return "\n".join(lines)


class ComplaintRequest(BaseModel):
    complaint_type: Literal["ncrp", "bank_dispute", "both"]

    # Complainant identity
    complainant_name: Optional[str] = None
    complainant_phone: Optional[str] = None
    complainant_email: Optional[str] = None
    complainant_address: Optional[str] = None

    # Incident
    incident_date: Optional[str] = None
    incident_description: Optional[str] = Field(None, max_length=2000)
    platform_used: Optional[str] = None
    suspect_name: Optional[str] = None
    suspect_phone: Optional[str] = None
    suspect_upi_id: Optional[str] = None
    suspect_claimed_agency: Optional[str] = None

    # Financial
    amount_lost: Optional[float] = Field(None, ge=0)
    payment_mode: Optional[str] = None
    transaction_reference: Optional[str] = None
    transaction_date: Optional[str] = None
    recipient_account: Optional[str] = None

    # Bank
    bank_name: Optional[str] = None
    account_number: Optional[str] = None

    # Forwarded from prior endpoint responses
    ncrp_complaint_number: Optional[str] = None
    matched_patterns: Optional[list[str]] = None
    payment_indicators: Optional[list[str]] = None


@router.post("/assist/complaint", response_model=ComplaintResponse)
async def generate_complaint(req: ComplaintRequest) -> ComplaintResponse:
    """Generate a ready-to-file NCRP complaint text and/or bank dispute email.

    Pure templating — no ML, no external API. Accepts incident fields entered
    directly or forwarded from /check/digital-arrest and /classify/document responses.
    """
    ncrp_text = _build_ncrp(req) if req.complaint_type in ("ncrp", "both") else None
    bank_text = _build_bank_dispute(req) if req.complaint_type in ("bank_dispute", "both") else None

    return ComplaintResponse(
        ncrp_complaint_text=ncrp_text,
        bank_dispute_text=bank_text,
        next_steps=_NEXT_STEPS,
        disclaimer=DISCLAIMER,
    )


class _EZeroFIRRequest(BaseModel):
    category: str = Field(..., min_length=1)


@router.post("/legal/templates/ezero-fir", response_model=EZeroFIRResponse)
async def ezero_fir(req: _EZeroFIRRequest) -> EZeroFIRResponse:
    """Generate an e-Zero FIR scaffold (BNSS Sec 457) for electronic submission.

    Pure templating — no ML, no external API, no DB. Ported directly from the
    Track 3 prototype's generate_ezero_fir; see AGENTS.md for provenance.
    """
    result = generate_ezero_fir(req.category)
    return EZeroFIRResponse(**result)


# ── Item 64: Bank Dispute + Ombudsman Auto-Escalation ─────────────────────────

_RBI_RESOLUTION_WINDOW_DAYS = 90
# RBI Master Direction on Limiting Liability of Customers in Unauthorised Electronic
# Banking Transactions (RBI/2017-18/15) — already cited in _build_bank_dispute() above
# — requires banks to complete resolution of an unauthorised-transaction dispute
# (crediting the disputed amount, or a reasoned rejection) within 90 days of the
# complaint being received. Verify the current RBI circular before relying on this for
# an actual legal deadline — citations/circulars can be amended, same caution as
# _LEGAL_NOTE above.

_DISPUTE_STATUS_NOTE = (
    "is_overdue is computed on demand when this endpoint is called — there is no "
    "background scheduler in this stack to auto-flag an overdue case the moment its "
    "deadline passes (same on-demand-only limitation as POST /compliance/consent/"
    "purge-expired; see ARCHITECTURE.md Known Technical Debt). Call this endpoint again "
    "later to get a current answer."
)

_ESCALATION_NOTE = (
    "Escalation path and RBI Ombudsman details are accurate as of this writing (RBI "
    "Integrated Ombudsman Scheme, 2021, which unified the erstwhile Banking Ombudsman "
    "Scheme into one online system) — verify current procedure at https://cms.rbi.org.in "
    "before filing, as schemes and portals can be updated."
)


class DisputeTrackRequest(ComplaintRequest):
    """Same fields as a bank-dispute ComplaintRequest, plus the identity/tracking
    fields a DisputeCase needs. bank_name and transaction_reference are required
    here (optional on the base ComplaintRequest) since a tracked case can't exist
    without them."""
    complaint_type: Literal["ncrp", "bank_dispute", "both"] = "bank_dispute"
    user_id: str = Field(..., min_length=1)
    bank_name: str = Field(..., min_length=1)
    transaction_reference: str = Field(..., min_length=1)


class _BankResponseRequest(BaseModel):
    response_text: str = Field(..., min_length=1)


def init_db() -> None:
    """Called at startup. Creates the dispute-tracking table if it doesn't exist yet."""
    Base.metadata.create_all(bind=engine)


def _dispute_or_404(case_id: str, db: Session) -> DisputeCase:
    case = db.query(DisputeCase).filter(DisputeCase.case_id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail=f"No tracked dispute found for case_id '{case_id}'.")
    return case


def _is_overdue(case: DisputeCase) -> bool:
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    return case.status == "open" and now > case.rbi_deadline_at


@router.post("/legal/dispute/track", response_model=DisputeTrackResponse, status_code=201)
async def track_dispute(req: DisputeTrackRequest, db: Session = Depends(get_db)) -> DisputeTrackResponse:
    """Raise a bank dispute — reusing _build_bank_dispute() as the source of truth
    for what "raising a dispute" means — and persist a DisputeCase to track its
    RBI-mandated resolution deadline through to bank response or escalation."""
    dispute_text = _build_bank_dispute(req)
    raised_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    case = DisputeCase(
        case_id=f"DISP-{uuid.uuid4().hex[:12].upper()}",
        user_id=req.user_id,
        bank_name=req.bank_name,
        transaction_reference=req.transaction_reference,
        dispute_raised_at=raised_at,
        rbi_deadline_at=raised_at + datetime.timedelta(days=_RBI_RESOLUTION_WINDOW_DAYS),
        status="open",
        bank_response=None,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    return DisputeTrackResponse(
        case_id=case.case_id,
        user_id=case.user_id,
        bank_name=case.bank_name,
        transaction_reference=case.transaction_reference,
        dispute_raised_at=case.dispute_raised_at,
        rbi_deadline_at=case.rbi_deadline_at,
        status=case.status,
        dispute_text=dispute_text,
        note=(
            f"rbi_deadline_at is dispute_raised_at + {_RBI_RESOLUTION_WINDOW_DAYS} days, per the RBI "
            "Master Direction on Limiting Liability of Customers in Unauthorised Electronic Banking "
            "Transactions (RBI/2017-18/15). Verify current circular text before relying on this as a "
            "legal deadline."
        ),
    )


@router.post("/legal/dispute/{case_id}/bank-response", response_model=DisputeStatusResponse)
async def log_bank_response(
    case_id: str, req: _BankResponseRequest, db: Session = Depends(get_db)
) -> DisputeStatusResponse:
    """Log that the bank responded to a tracked dispute, moving its status to bank_responded."""
    case = _dispute_or_404(case_id, db)
    case.bank_response = req.response_text
    case.status = "bank_responded"
    db.commit()
    db.refresh(case)

    return DisputeStatusResponse(
        case_id=case.case_id,
        status=case.status,
        bank_response=case.bank_response,
        rbi_deadline_at=case.rbi_deadline_at,
        is_overdue=_is_overdue(case),
        note=_DISPUTE_STATUS_NOTE,
    )


@router.get("/legal/dispute/{case_id}/status", response_model=DisputeStatusResponse)
async def get_dispute_status(case_id: str, db: Session = Depends(get_db)) -> DisputeStatusResponse:
    """Return a tracked dispute's current status and a computed is_overdue signal —
    the actual "auto-escalation" trigger, checked on demand (see note)."""
    case = _dispute_or_404(case_id, db)
    return DisputeStatusResponse(
        case_id=case.case_id,
        status=case.status,
        bank_response=case.bank_response,
        rbi_deadline_at=case.rbi_deadline_at,
        is_overdue=_is_overdue(case),
        note=_DISPUTE_STATUS_NOTE,
    )


@router.post("/legal/dispute/{case_id}/escalate", response_model=DisputeEscalationResponse)
async def escalate_dispute(case_id: str, db: Session = Depends(get_db)) -> DisputeEscalationResponse:
    """Escalate an overdue dispute to the RBI Banking Ombudsman. Only allowed once
    is_overdue is true — escalating a dispute still within its RBI-mandated window
    is a real 409, not a silent no-op."""
    case = _dispute_or_404(case_id, db)
    if not _is_overdue(case):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Case '{case_id}' is not yet overdue (rbi_deadline_at: "
                f"{case.rbi_deadline_at.isoformat()}) — escalation is only available once the "
                "RBI-mandated resolution window has actually passed."
            ),
        )
    case.status = "escalated"
    db.commit()
    db.refresh(case)

    escalation_text = (
        f"Bank '{case.bank_name}' did not resolve dispute {case.case_id} "
        f"(transaction ref: {case.transaction_reference}) within the RBI Master Direction's "
        f"{_RBI_RESOLUTION_WINDOW_DAYS}-day window (deadline was {case.rbi_deadline_at.isoformat()} UTC). "
        "File a complaint with the RBI Banking Ombudsman via the RBI's Complaint Management System "
        "at https://cms.rbi.org.in, citing this case reference and the bank's failure to respond "
        "within the mandated timeframe under RBI/2017-18/15."
    )

    return DisputeEscalationResponse(
        case_id=case.case_id,
        status=case.status,
        escalation_text=escalation_text,
        rbi_deadline_at=case.rbi_deadline_at,
        note=_ESCALATION_NOTE,
    )
