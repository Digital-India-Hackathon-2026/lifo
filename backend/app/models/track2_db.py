"""SQLAlchemy models for Track 2 items ported into the real backend:
crowdsourced reporting + heatmap (items 34/35), the panic-trigger's
paired-device lookup (item 41), the B2B threat-intel feed (items
76/77), gamified-training score history (item 42), and issued SDK API
keys (item 69). Grouped in one file, matching Track 3's per-track
convention (network_intel_db.py) rather than one file per small table.
"""
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from app.core.database import Base


class ReporterReputation(Base):
    """Items 34/35: tracks how many reports a given reporter_id has submitted."""
    __tablename__ = "reporter_reputation"
    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(String, unique=True, index=True)
    report_count = Column(Integer, default=0)


class HeatmapPoint(Base):
    """Items 34/35: a point on the public community heatmap. Only created
    once a reporter has passed the reputation threshold — see segments.py."""
    __tablename__ = "heatmap_points"
    id = Column(Integer, primary_key=True, index=True)
    lat = Column(Float)
    lng = Column(Float)
    scam_type = Column(String)
    weight = Column(Integer)


class PairedDevice(Base):
    """Item 41: protected<->protector device pairing, read by panic_trigger
    to decide the paired-vs-unpaired branch. Creating a pairing (items
    37/38's full protector-protected UX) is out of scope for this session —
    this table exists purely as the dependency item 41 needs."""
    __tablename__ = "paired_devices"
    id = Column(Integer, primary_key=True, index=True)
    protected_id = Column(String, unique=True, index=True)
    protector_id = Column(String)


class B2BThreatIndicator(Base):
    """Items 76/77: SHA256-hashed contact numbers flagged HIGH risk by the
    B2B profile-verification check — never the raw number. A dedicated
    table rather than reusing Track 3's PrivacyPreservingBlocklist/
    ThreatTaxonomy, since none of the 4 existing taxonomy values
    (PHISHING_URL/MULE_ACCOUNT/VOICE_SPOOF/MALICIOUS_APK) honestly
    describe a flagged matrimony/job-portal contact number."""
    __tablename__ = "b2b_threat_indicators"
    id = Column(Integer, primary_key=True, index=True)
    sha256_hash = Column(String, unique=True, index=True)
    platform = Column(String)


class TrainingScore(Base):
    """Item 42: append-only log of gamified scam-training drill scores per
    user_id — identity-linked history, not transient per-call state, so
    this follows item 37's real-SQLite persistence category rather than
    item 38's in-memory _call_sessions category. This table is a
    telemetry sink only — it does not represent or generate the drill
    content/practice-call itself, see vulnerable.py."""
    __tablename__ = "training_scores"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    drill_id = Column(String)
    score = Column(Integer)
    passed = Column(Boolean)
    submitted_at_utc = Column(DateTime)


class SDKApiKey(Base):
    """Item 69: issued SDK API keys, SHA256-hashed — never the raw key,
    same hash-before-store convention as B2BThreatIndicator above and
    Track 3's hashed entities. tier reuses item 70's free/premium
    taxonomy so a validated key's tier can feed the same freemium gate."""
    __tablename__ = "sdk_api_keys"
    id = Column(Integer, primary_key=True, index=True)
    key_hash = Column(String, unique=True, index=True)
    tier = Column(String)
    issued_at_utc = Column(DateTime)
