"""Cryptographic hash helpers for SQL secure object revision metadata."""

from __future__ import annotations

from datetime import datetime

from .....core.external_constants import UTF_8_ENCODING
from .....core.hashing import sha256_hex


def derive_revision_id(
    *,
    namespace: str,
    object_key: bytes,
    schema_version: int,
    written_at: datetime,
    payload_hash: str,
    ciphertext_hash: str,
    previous_revision_id: str | None,
    previous_payload_hash: str | None,
) -> str:
    """Derive a deterministic secure-object revision id from row metadata."""
    parts = (
        namespace,
        object_key.hex(),
        str(schema_version),
        written_at.isoformat(),
        payload_hash,
        ciphertext_hash,
        previous_revision_id or "",
        previous_payload_hash or "",
    )
    return sha256_hex("\x1f".join(parts).encode(UTF_8_ENCODING))
