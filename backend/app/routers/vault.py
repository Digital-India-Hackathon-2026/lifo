"""
/vault — Family Safe-Word Vault.

Stores a salted PBKDF2-SHA256 hash of a household safe word to a local JSON file
so family members can verify they are speaking to a real relative (not a scammer
impersonating them). The original word is never stored or returned.

Storage: backend/data/vault.json (file-based so it survives server restarts).
Hash:     hashlib.pbkdf2_hmac SHA-256, 100,000 iterations, 16-byte random salt.
Auth:     None — single-user demo. Do not expose publicly without rate limiting.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.models.responses import DISCLAIMER, VaultSetResponse, VaultVerifyResponse

router = APIRouter(prefix="/vault", tags=["vault"])

_VAULT_FILE = Path(__file__).parent.parent.parent / "data" / "vault.json"
_ITERATIONS = 100_000
_RATE_LIMIT_NOTE = (
    "No attempt limiting is applied — do not expose this endpoint publicly "
    "without adding rate limiting."
)


class _SetRequest(BaseModel):
    safe_word: str = Field(..., min_length=3, max_length=100)

    @field_validator("safe_word")
    @classmethod
    def not_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Safe word cannot be empty or whitespace only.")
        return v


class _VerifyRequest(BaseModel):
    safe_word: str = Field(..., min_length=1, max_length=100)


def _hash_word(word: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", word.encode("utf-8"), salt, _ITERATIONS).hex()


def _load() -> Optional[dict]:
    if not _VAULT_FILE.exists():
        return None
    try:
        return json.loads(_VAULT_FILE.read_text())
    except Exception:
        return None


def _save(salt_hex: str, hash_hex: str) -> None:
    _VAULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _VAULT_FILE.write_text(json.dumps({"salt": salt_hex, "hash": hash_hex}))


@router.post("/set", response_model=VaultSetResponse)
async def set_safe_word(req: _SetRequest) -> VaultSetResponse:
    """Store a salted hash of the safe word. The original word is never retained."""
    salt = os.urandom(16)
    hash_hex = _hash_word(req.safe_word.strip(), salt)
    _save(salt.hex(), hash_hex)
    return VaultSetResponse(
        message="Safe word stored securely. The original word is not retained.",
        note=_RATE_LIMIT_NOTE,
    )


@router.post("/verify", response_model=VaultVerifyResponse)
async def verify_safe_word(req: _VerifyRequest) -> VaultVerifyResponse:
    """Check a candidate safe word against the stored hash."""
    vault = _load()
    if vault is None:
        raise HTTPException(
            status_code=409,
            detail="No safe word has been set. Use POST /vault/set first.",
        )
    salt = bytes.fromhex(vault["salt"])
    candidate_hash = _hash_word(req.safe_word.strip(), salt)
    # Constant-time comparison — prevents timing-based hash inference
    matches = hmac.compare_digest(candidate_hash, vault["hash"])
    note = (
        "Safe word matches — confirmed real contact."
        if matches else
        "Safe word does not match. If you believe this is an error, try again or reset the safe word."
    )
    return VaultVerifyResponse(matches=matches, note=note, disclaimer=DISCLAIMER)
