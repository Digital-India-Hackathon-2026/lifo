"""
/check/phishing — PhishTank blocklist lookup + typosquat similarity scoring.

Blocklist: PhishTank online-valid CSV, cached locally for 24 hours.
Similarity: difflib.SequenceMatcher against a curated list of Indian government
and banking domains — the primary impersonation targets in Digital Arrest scams.
Homoglyph substitution (0→o, rn→m, etc.) is NOT applied; SequenceMatcher treats
visually similar chars as different. Known limitation — acceptable for demo scope.
"""
import csv
import io
import re
import time
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.responses import DISCLAIMER, CheckPhishingResponse

_PHISHTANK_URL = "http://data.phishtank.com/data/online-valid.csv"
_CACHE_DIR = Path(__file__).parent.parent.parent / "data"
_CACHE_FILE = _CACHE_DIR / "phishtank_cache.txt"
_CACHE_TTL_SECONDS = 86_400   # 24 hours
_FETCH_TIMEOUT = 30

# Domains that Digital Arrest scammers impersonate. Similarity is scored against
# each entry; the highest ratio determines risk level.
_CURATED_DOMAINS: list[str] = [
    # Law enforcement / government
    "cbi.gov.in", "cbic.gov.in", "incometax.gov.in", "income-tax.gov.in",
    "india.gov.in", "mha.gov.in", "uidai.gov.in", "npci.org.in",
    "sebi.gov.in", "rbi.org.in", "trai.gov.in", "nic.in", "meity.gov.in",
    # Major Indian banks
    "sbi.co.in", "hdfcbank.com", "icicibank.com", "axisbank.com", "kotak.com",
    "pnbindia.in", "bankofbaroda.in", "canarabank.in", "unionbankofindia.co.in",
    # Payment platforms (googlepay/amazonpay omitted — too short to distinguish from google/amazon)
    "paytm.com", "phonepe.com",
]

_HIGH_SIMILARITY = 0.75
_MEDIUM_SIMILARITY = 0.55

_blocklist_domains: set[str] = set()

router = APIRouter(prefix="/check", tags=["phishing"])


class _PhishingRequest(BaseModel):
    url: str


def _extract_domain(raw: str) -> str:
    """Normalise URL or bare domain to lowercase hostname, www. stripped."""
    raw = raw.strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    hostname = urlparse(raw).hostname or ""
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname.lower()


def _extract_sld(domain: str) -> str:
    """Strip TLD to get the meaningful second-level label (e.g. 'sbi.co.in' → 'sbi')."""
    for compound_tld in ("gov.in", "co.in", "org.in", "net.in", "ac.in"):
        if domain.endswith("." + compound_tld):
            return domain[:-(len(compound_tld) + 1)]
    parts = domain.rsplit(".", 1)
    return parts[0] if len(parts) > 1 else domain


def _score_similarity(domain: str) -> tuple[float, Optional[str]]:
    """Return (best_score, best_curated_match) using SLD-level comparison + containment.

    Comparing SLD-to-SLD (not full domain) avoids false positives from shared TLDs:
    e.g. 'google.com' vs 'googlepay.com' scored 0.87 on full-domain; SLD 'google'
    vs 'googlepay' scores 0.77 — but googlepay is excluded from the curated list anyway.
    Containment catches short brand names hidden inside longer fakes ('cbi-verify').
    """
    submitted_sld = _extract_sld(domain)
    best, best_match = 0.0, None
    for curated in _CURATED_DOMAINS:
        curated_sld = _extract_sld(curated)
        sld_ratio = SequenceMatcher(None, submitted_sld, curated_sld).ratio()
        # Word-boundary containment: "cbi-verify" contains "cbi" at word boundary → 0.85
        word_contained = bool(
            re.search(r"(?:^|[-_.])" + re.escape(curated_sld) + r"(?:[-_.]|$)", submitted_sld)
        )
        # Prefix/suffix containment (no separator): "cbigov" starts with "cbi" → 0.75
        affix_contained = len(curated_sld) >= 3 and (
            submitted_sld.startswith(curated_sld) or submitted_sld.endswith(curated_sld)
        )
        score = max(
            sld_ratio,
            0.85 if word_contained else 0.0,
            0.75 if affix_contained else 0.0,
        )
        if score > best:
            best, best_match = score, curated
    return best, best_match


def _fetch_blocklist() -> set[str]:
    """Download PhishTank CSV, extract one domain per URL, write cache, return set."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        _PHISHTANK_URL, headers={"User-Agent": "Kavach/1.0"}
    )
    with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
        content = resp.read().decode("utf-8", errors="replace")
    domains: set[str] = set()
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        domain = _extract_domain(row.get("url", ""))
        if domain:
            domains.add(domain)
    _CACHE_FILE.write_text("\n".join(sorted(domains)))
    return domains


def load_phishing_blocklist() -> None:
    """Called at startup. Loads from local cache if fresh, otherwise fetches."""
    global _blocklist_domains
    cache_fresh = (
        _CACHE_FILE.exists()
        and (time.time() - _CACHE_FILE.stat().st_mtime) < _CACHE_TTL_SECONDS
    )
    if cache_fresh:
        _blocklist_domains = set(_CACHE_FILE.read_text().splitlines())
        print(f"INFO: Phishing blocklist loaded from cache ({len(_blocklist_domains):,} domains)")
        return
    try:
        _blocklist_domains = _fetch_blocklist()
        print(f"INFO: Phishing blocklist fetched ({len(_blocklist_domains):,} domains)")
    except Exception as exc:
        print(f"WARNING: PhishTank fetch failed ({exc}) — blocklist unavailable; similarity scoring still active")
        if _CACHE_FILE.exists():
            # Serve stale cache rather than nothing
            _blocklist_domains = set(_CACHE_FILE.read_text().splitlines())
            print(f"INFO: Loaded stale cache as fallback ({len(_blocklist_domains):,} domains)")


def _risk_level(in_blocklist: bool, similarity: float) -> str:
    if in_blocklist or similarity >= _HIGH_SIMILARITY:
        return "high"
    if similarity >= _MEDIUM_SIMILARITY:
        return "medium"
    return "low"


def _build_note(
    domain: str,
    in_blocklist: bool,
    blocklist_unavailable: bool,
    similarity: float,
    matched: Optional[str],
    risk: str,
) -> str:
    parts: list[str] = []
    if in_blocklist:
        parts.append(f"'{domain}' is confirmed in the PhishTank active phishing database.")
    if similarity >= _HIGH_SIMILARITY and matched:
        parts.append(
            f"Closely resembles '{matched}' ({similarity:.0%} similarity) — possible typosquat or impersonation."
        )
    elif similarity >= _MEDIUM_SIMILARITY and matched:
        parts.append(
            f"Shows partial similarity to '{matched}' ({similarity:.0%}) — verify independently."
        )
    if blocklist_unavailable:
        parts.append("PhishTank blocklist unavailable at startup — scored by similarity only.")
    if not parts:
        parts.append("No strong match found against known Indian government or banking domains.")
    if risk in ("medium", "high"):
        parts.append(
            "No Indian government agency arrests via video call or demands payment verification via an online link."
        )
    return " ".join(parts)


@router.post("/phishing", response_model=CheckPhishingResponse)
async def check_phishing(req: _PhishingRequest) -> CheckPhishingResponse:
    """Check a domain or URL against PhishTank + typosquat scoring."""
    domain = _extract_domain(req.url)
    if not domain:
        raise HTTPException(
            status_code=400, detail="Empty or invalid URL — could not extract a domain."
        )
    in_blocklist = domain in _blocklist_domains
    blocklist_match: Optional[str] = domain if in_blocklist else None
    blocklist_unavailable = len(_blocklist_domains) == 0
    similarity, best_curated = _score_similarity(domain)
    matched_against = best_curated if similarity >= _MEDIUM_SIMILARITY else None
    risk = _risk_level(in_blocklist, similarity)
    note = _build_note(domain, in_blocklist, blocklist_unavailable, similarity, matched_against, risk)
    return CheckPhishingResponse(
        domain=domain,
        in_blocklist=in_blocklist,
        blocklist_match=blocklist_match,
        similarity_score=round(similarity, 4),
        matched_against=matched_against,
        risk_level=risk,
        note=note,
        disclaimer=DISCLAIMER,
    )
