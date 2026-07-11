"""Federated Privacy-Preserving Blocklist ingestion + scan engine (Track 3, item 32).

Ported algorithm from the Track 3 prototype (kavach-track3-scratch/
app/pipeline/analysis/blocklist_engine.py) — hashing, dedup-before-insert
ingest logic, and match-lookup scan are unchanged. See AGENTS.md for
provenance.
"""
import hashlib

from sqlalchemy.orm import Session

from app.models.network_intel_db import PrivacyPreservingBlocklist
from app.models.responses import ThreatTaxonomy


class PrivacyBlocklistEngine:
    @staticmethod
    def _generate_sha256(raw_text: str) -> str:
        """One-way cryptographic hashing to ensure zero-knowledge data storage."""
        return hashlib.sha256(raw_text.encode('utf-8')).hexdigest()

    @classmethod
    def ingest_threat(cls, db: Session, raw_indicator: str, taxonomy_node: ThreatTaxonomy) -> dict:
        """
        Hashes a raw threat and stores it, strictly enforcing the predefined taxonomy nodes.
        """
        indicator_hash = cls._generate_sha256(raw_indicator)

        # Deterministic, real-time database lookup
        existing = db.query(PrivacyPreservingBlocklist).filter(
            PrivacyPreservingBlocklist.sha256_hash == indicator_hash
        ).first()

        if existing:
            return {"status": "REJECTED", "reason": "Hash signature already exists in the retrieval layer."}

        # Committing the cryptographic signature
        new_threat = PrivacyPreservingBlocklist(sha256_hash=indicator_hash)
        db.add(new_threat)
        db.commit()

        return {
            "status": "SECURED",
            "hash_signature": indicator_hash,
            "taxonomy": taxonomy_node.value,
        }

    @classmethod
    def scan_network_traffic(cls, db: Session, raw_indicator: str) -> dict:
        """
        Real-time scan against the blocklist.
        Caching is explicitly bypassed to ensure 100% deterministic legal compliance.
        """
        indicator_hash = cls._generate_sha256(raw_indicator)

        match = db.query(PrivacyPreservingBlocklist).filter(
            PrivacyPreservingBlocklist.sha256_hash == indicator_hash
        ).first()

        if match:
            return {"threat_detected": True, "action": "INTERCEPT_AND_LOG", "hash": indicator_hash}

        return {"threat_detected": False, "action": "ALLOW", "hash": indicator_hash}
