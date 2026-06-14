"""Canonical file-hashing utilities for the AEAT codebase.

Provides :func:`sha256_hex`, :func:`sha256_file`, :func:`hash_file`,
:func:`canonical_json_bytes`, and :func:`content_hash_hex` as the single
authoritative SHA-256 implementations.  All adapters, application services, and
domain modules import from here rather than inlining
``hashlib.sha256(data).hexdigest()``, duplicating the chunked-read loop, or
re-deriving the canonical-JSON content-hash serialisation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

# Local UTF-8 constant rather than importing ``UTF_8_ENCODING`` from
# ``external_constants``: that module imports ``core.errors``, which pulls in
# ``core.redaction`` -> ``core.hashing``, so the import would close a cycle.
_UTF_8: Final[str] = "utf-8"

_HASH_CHUNK_SIZE = 65536


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of ``data``.

    Use this for in-memory payloads (serialised JSON, string keys, etc.).
    For file-path inputs use :func:`sha256_file` or :func:`hash_file`.
    """
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(payload: object) -> bytes:
    """Return deterministic canonical-JSON bytes for content hashing.

    Sorted keys, compact separators, UTF-8 — the single serialisation the
    content-hash helpers feed into SHA-256 so two semantically equal payloads
    produce the same bytes (and therefore the same content hash / id).
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(_UTF_8)


def content_hash_hex(payload: object) -> str:
    """Return the SHA-256 hex digest of the canonical-JSON form of ``payload``.

    The canonical content-addressing primitive: equivalent to
    ``sha256_hex(canonical_json_bytes(payload))``. Callers that need a truncated
    id slice the returned digest (``content_hash_hex(payload)[:16]``).
    """
    return sha256_hex(canonical_json_bytes(payload))


def hash_file(path: Path) -> tuple[str, int]:
    """Return ``(sha256_hex, byte_count)`` for the file at ``path``.

    Reads in 64 KiB chunks so large files (PDFs, export artefacts) hash
    cleanly without loading the entire file into memory.  Use this variant
    when the caller needs both the digest and the content length.
    """
    digest = hashlib.sha256()
    length = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
            length += len(chunk)
    return digest.hexdigest(), length


def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 of the bytes at ``path``.

    Reads in 64 KiB chunks so large files (PDFs, export artefacts) hash
    cleanly without loading the entire file into memory.  Use :func:`hash_file`
    when the byte count is also needed.
    """
    hex_digest, _ = hash_file(path)
    return hex_digest


__all__ = ["canonical_json_bytes", "content_hash_hex", "hash_file", "sha256_file", "sha256_hex"]
