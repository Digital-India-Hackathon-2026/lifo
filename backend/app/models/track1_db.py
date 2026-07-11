"""SQLAlchemy models for Track 1 items needing real persistence.

Item 30 (Scam Campaign Timeline) is the first Track 1 item requiring a
database at all — every prior Track 1 port (items 1-29, plus the 6
unscoped bonus fraud detectors) is stateless regex/pattern matching with
no table of its own. A dedicated per-track file matches the established
convention (network_intel_db.py for Track 3, track2_db.py for Track 2)
rather than bolting a Track 1 concept onto another track's models file.
"""
from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base


class CaseFile(Base):
    """Item 30: a user-created container for one suspected scam campaign
    the user manually links events into — never automated cross-app
    tracking (see campaign_timeline.py's module docstring). `case_id` is
    the public-facing identifier (server-generated, unique + indexed),
    kept separate from the internal autoincrement `id`, same pattern as
    Track 3's AssetRecoveryEntity.case_id."""
    __tablename__ = "case_files"
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, unique=True, index=True)
    user_id = Column(String, index=True)
    title = Column(String)
    status = Column(String, default="open")
    created_at = Column(DateTime)


class CampaignEvent(Base):
    """Item 30: one user-linked event (call/whatsapp/upi/document/other)
    inside a CaseFile. `case_id` is a plain indexed string column, not a
    SQLAlchemy ForeignKey — matches this codebase's existing convention
    of flat tables with app-level ID lookups (e.g. vulnerable.py's
    PairedDevice), not ORM relationships, which nothing else here uses
    either. `event_timestamp` is the user-supplied real-world time of
    the event (the actual chronological-ordering key); `logged_at` is
    when this row was actually inserted — kept deliberately separate,
    never conflated, per the catalog's own framing for this item.
    `artifact_id` is an optional opaque string a user can set to
    reference one of this app's own past results (a honeypot report ID,
    a phishing-check result, etc.) — stored as-is, no cross-referencing
    or joins in this version; deeper linking is a future enhancement."""
    __tablename__ = "campaign_events"
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, index=True)
    event_type = Column(String)
    description = Column(Text)
    event_timestamp = Column(DateTime)
    artifact_id = Column(String, nullable=True)
    logged_at = Column(DateTime)
