"""Legal document templating (Track 3, item 65).

Ported directly from the Track 3 prototype (kavach-track3-scratch/
app/pipeline/analysis/legal_engines.py) — generate_ezero_fir is genuine
dynamic templating logic (uuid-based hash, real UTC timestamp, fixed
statute/jurisdiction strings), not a stub; copied as-is, only adapted to
take `category` directly instead of a `details` dict. See AGENTS.md for
provenance. (route_psychological_aid from the same reference file is item
67 — out of scope here, not ported.)
"""
import uuid
from datetime import datetime, timezone


def generate_ezero_fir(category: str) -> dict:
    """
    Generates a legally structured e-Zero FIR.
    Compliant with BNSS Section 457 for electronic submission.
    """
    return {
        "fir_hash": f"FIR-{uuid.uuid4().hex[:12].upper()}",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "statute": "Bhartiya Nagarik Suraksha Sanhita (BNSS) Sec 457",
        "jurisdiction": "NCRP_CENTRAL_NODE",
        "threat_category": category or "UNCLASSIFIED",
        "status": "AWAITING_CRYPTOGRAPHIC_SIGNATURE",
    }
