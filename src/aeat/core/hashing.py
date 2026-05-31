"""Canonical file-hashing utilities for the AEAT codebase.

Provides :func:`sha256_hex`, :func:`sha256_file`, and :func:`hash_file` as
the single authoritative SHA-256 implementations.  All adapters, application
services, and domain modules import from here rather than inlining
``hashlib.sha256(data).hexdigest()`` or duplicating the chunked-read loop.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_HASH_CHUNK_SIZE = 65536


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of ``data``.

    Use this for in-memory payloads (serialised JSON, string keys, etc.).
    For file-path inputs use :func:`sha256_file` or :func:`hash_file`.
    """
    return hashlib.sha256(data).hexdigest()


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


__all__ = ["hash_file", "sha256_file", "sha256_hex"]
