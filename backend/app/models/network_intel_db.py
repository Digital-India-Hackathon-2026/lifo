"""SQLAlchemy models for the Campaign Graph (Track 3, item 31), the
Federated Privacy-Preserving Blocklist (Track 3, item 32), DPDP consent
records (Track 3, item 82), and Asset-Recovery Status Tracking (Track 3,
item 68).

Entities are content-addressed by SHA256 hash of the raw value (phone number,
UPI ID, domain, APK hash, ...) — the raw value itself is never stored, only
its hash and its taxonomy classification. Ported field-for-field from the
Track 3 prototype (kavach-track3-scratch/app/domains/core_models.py);
see AGENTS.md for provenance.

DPDPConsent and AssetRecoveryEntity are exceptions: only field names were
salvaged from the prototype (DPDPOSConsent had no unique constraint on
(user_id, purpose); the prototype's asset ledger had no write path at all —
see AGENTS.md Sessions 19 and 20).
"""
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint

from app.core.database import Base


class ScamEntity(Base):
    __tablename__ = "scam_entities"
    id = Column(Integer, primary_key=True, index=True)
    entity_value = Column(String, unique=True)
    taxonomy_node = Column(String)


class ScamRelation(Base):
    __tablename__ = "scam_relations"
    id = Column(Integer, primary_key=True, index=True)
    source_entity_id = Column(Integer, ForeignKey("scam_entities.id"))
    target_entity_id = Column(Integer, ForeignKey("scam_entities.id"))
    relation_type = Column(String)


class PrivacyPreservingBlocklist(Base):
    __tablename__ = "hashed_blocklist"
    id = Column(Integer, primary_key=True, index=True)
    sha256_hash = Column(String, unique=True, index=True)


class DPDPConsent(Base):
    __tablename__ = "dpdp_consents"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    purpose = Column(String)
    granted_at = Column(DateTime)
    expires_at = Column(DateTime, nullable=True)
    revoked = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("user_id", "purpose", name="uq_dpdp_consent_user_purpose"),
    )


class AssetRecoveryEntity(Base):
    __tablename__ = "asset_recovery_ledgers"
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, unique=True, index=True)
    frozen_amount = Column(Float)
    bank_node = Column(String)
    status = Column(String)
    hold_timestamp_utc = Column(DateTime)
    last_updated_utc = Column(DateTime)
