"""Canonical SHA-256 utilities for bytes, files, and JSON content ids.

Provides :func:`sha256_hex`, :func:`sha256_file`, :func:`hash_file`,
:func:`canonical_json_bytes`, and :func:`content_hash_hex` as the single
authoritative SHA-256 implementations. Byte callers hash in memory; file
callers pass a :class:`~pathlib.Path` and share the chunked-read loop. All
adapters, application services, and domain modules import from here rather than
inlining ``hashlib.sha256(data).hexdigest()`` or re-deriving the canonical-JSON
content-hash serialisation.

This module owns digest mechanics only. Domain identities such as profile
snapshots, calculation revisions, evidence bundles, and filing records own the
payload schema, value normalisation, contract-change policy, and pinned digest tests
that make a digest semantically stable.
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

    Use this for in-memory payloads once the caller has already chosen the byte
    representation (serialised JSON, string keys, ciphertext, etc.). It does
    not normalise text or domain values. For file-path inputs use
    :func:`sha256_file` or :func:`hash_file`.
    """
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(payload: object) -> bytes:
    """Return deterministic canonical-JSON bytes for content hashing.

    Sorted keys, compact separators, UTF-8 — the single serialisation the
    content-hash helpers feed into SHA-256 so two semantically equal payloads
    produce the same bytes (and therefore the same content hash / id).

    The payload must already be JSON-compatible. Callers normalise
    ``Decimal``, :class:`~pathlib.Path`, datetimes, enums, and domain objects
    into stable strings or dictionaries before entering this helper; any change
    to that projection is a caller-owned identity change.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(_UTF_8)


def content_hash_hex(payload: object) -> str:
    """Return the SHA-256 hex digest of the canonical-JSON form of ``payload``.

    The canonical content-addressing primitive: equivalent to
    ``sha256_hex(canonical_json_bytes(payload))``. Callers that need a truncated
    id slice the returned digest (``content_hash_hex(payload)[:16]``).

    Use this only after the caller's payload shape is part of that domain's
    identity contract. Changing keys, value normalisation, or included fields
    changes the digest and should be handled as an explicit identity contract change
    backed by pinned fixtures.
    """
    return sha256_hex(canonical_json_bytes(payload))


def hash_file(path: Path) -> tuple[str, int]:
    """Return ``(sha256_hex, byte_count)`` for the file at ``path``.

    Reads in 64 KiB chunks so large files (PDFs, export artefacts) hash
    cleanly without loading the entire file into memory. Hashes file contents
    exactly; path metadata, permissions, archive member names, and manifest
    normalisation stay outside this helper. Use this variant when the caller
    needs both the digest and the content length.
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
    cleanly without loading the entire file into memory. Hashes file contents
    exactly, not the file's path or metadata. Use :func:`hash_file` when the
    byte count is also needed.
    """
    hex_digest, _ = hash_file(path)
    return hex_digest


__all__ = ["canonical_json_bytes", "content_hash_hex", "hash_file", "sha256_file", "sha256_hex"]
