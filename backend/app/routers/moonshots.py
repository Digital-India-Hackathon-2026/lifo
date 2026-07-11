"""
/poc/moonshots — Proof-of-concept moonshot scaffolds (Track 3, item 87:
Distributed Honeypot Grid).

Explicitly a moonshot PoC per the original catalog brief: "a working
prototype or clear architecture document... not a production system."
Every response here says so in its own `note` field — PoC endpoints are
never presented as real telemetry, matching this project's existing
convention of never overclaiming certainty (see CONFIDENCE_NOTE
distinguishing raw classifier score from calibrated probability).
Ported from the Track 3 prototype's `poc_honeypot_grid` scaffold as-is —
hardcoded values, no DB, no live logic.
"""
from fastapi import APIRouter

from app.models.responses import MoonshotPoCResponse

router = APIRouter(prefix="/poc/moonshots", tags=["moonshots"])

_HONEYPOT_GRID_NOTE = (
    "Hardcoded proof-of-concept scaffold — not live telemetry. "
    "See catalog item 87 / ARCHITECTURE.md."
)


@router.get("/distributed-honeypot", response_model=MoonshotPoCResponse)
async def distributed_honeypot_grid() -> MoonshotPoCResponse:
    """Distributed Honeypot Grid moonshot PoC — hardcoded scaffold values, not real telemetry."""
    return MoonshotPoCResponse(active_nodes=42, intercepted_payloads=105, note=_HONEYPOT_GRID_NOTE)
