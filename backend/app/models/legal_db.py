"""SQLAlchemy models for the Legal-Tech domain (catalog item 64 — Bank
Dispute + Ombudsman Auto-Escalation). Genuinely new work, not ported from
any of the three collaborator repos (Track 1/2/3) — none of them cover
this catalog item. A dedicated legal_db.py rather than folding into
network_intel_db.py (Track 3's grouping), track1_db.py, or track2_db.py
(also per-collaborator-repo groupings item 64 doesn't belong to) — same
reasoning track1_db.py's own docstring already gives for not bolting an
unrelated item onto the wrong track's models file. Pairs naturally with
legal_templates.py (item 65's service module for this same "legal"
domain).
"""
from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base


class DisputeCase(Base):
    """Item 64: tracks a bank-dispute email raised via complaint.py's
    _build_bank_dispute() through to bank response or escalation to the
    RBI Ombudsman. `case_id` is server-generated ("DISP-" + a 12-char
    uuid4 hex, same prefixed-hash style as legal_templates.py's fir_hash
    and track1_db.py's CaseFile.case_id). `rbi_deadline_at` is computed
    once at creation (dispute_raised_at + the RBI Master Direction's
    90-day resolution window, RBI/2017-18/15) and never recomputed — a
    case's deadline is fixed at the moment the dispute is raised, not a
    moving target. `bank_response` is free text, optional, populated
    only once the bank actually responds."""
    __tablename__ = "dispute_cases"
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, unique=True, index=True)
    user_id = Column(String, index=True)
    bank_name = Column(String)
    transaction_reference = Column(String)
    dispute_raised_at = Column(DateTime)
    rbi_deadline_at = Column(DateTime)
    status = Column(String, default="open")
    bank_response = Column(Text, nullable=True)
