"""Campaign Graph ingestion engine (Track 3, item 31).

Ported algorithm from the Track 3 prototype (kavach-track3-scratch/
app/pipeline/analysis/graph_engine.py) — hashing, get-or-create node lookup,
dedup-before-create edge logic, and commit/rollback handling are unchanged.
See AGENTS.md for provenance.
"""
import hashlib

from sqlalchemy.orm import Session

from app.models.network_intel_db import ScamEntity, ScamRelation
from app.models.responses import ThreatTaxonomy


class GraphIntelligenceEngine:
    @staticmethod
    def _hash_value(raw_value: str) -> str:
        """Cryptographically hashes PII to maintain Zero-Knowledge."""
        return hashlib.sha256(raw_value.encode()).hexdigest()

    @classmethod
    def ingest_scam_relation(
        cls, db: Session, source_raw: str, target_raw: str, taxonomy: ThreatTaxonomy, relation: str
    ) -> dict:
        """
        Core Algorithm: Ingests raw data, hashes it, enforces the strict taxonomy,
        and builds the campaign graph edges in the database.
        """
        source_hash = cls._hash_value(source_raw)
        target_hash = cls._hash_value(target_raw)

        # 1. Retrieve or Create Source Node
        source_node = db.query(ScamEntity).filter(ScamEntity.entity_value == source_hash).first()
        if not source_node:
            source_node = ScamEntity(entity_value=source_hash, taxonomy_node=taxonomy.value)
            db.add(source_node)
            db.flush()  # Flush to get the ID without committing the transaction yet

        # 2. Retrieve or Create Target Node
        target_node = db.query(ScamEntity).filter(ScamEntity.entity_value == target_hash).first()
        if not target_node:
            target_node = ScamEntity(entity_value=target_hash, taxonomy_node=taxonomy.value)
            db.add(target_node)
            db.flush()

        # 3. Create the Edge (Relation)
        existing_edge = db.query(ScamRelation).filter(
            ScamRelation.source_entity_id == source_node.id,
            ScamRelation.target_entity_id == target_node.id,
            ScamRelation.relation_type == relation,
        ).first()

        if not existing_edge:
            new_edge = ScamRelation(
                source_entity_id=source_node.id,
                target_entity_id=target_node.id,
                relation_type=relation,
            )
            db.add(new_edge)
            db.commit()
            edge_status = "CREATED"
        else:
            db.rollback()
            edge_status = "EXISTS"

        return {
            "source_node_id": source_node.id,
            "target_node_id": target_node.id,
            "edge_status": edge_status,
            "taxonomy_enforced": taxonomy.value,
        }
