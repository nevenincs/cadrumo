"""Canonical file-hashing utilities for the AEAT codebase.

Provides :func:`sha256_file` as the single authoritative SHA-256 file-hash
implementation.  All adapters, application services, and domain modules that
need a stable file digest import from here rather than implementing inline
``hashlib.sha256(path.read_bytes())`` or duplicating the chunked-read loop.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_HASH_CHUNK_SIZE = 65536


def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 of the bytes at ``path``.

    Reads in 64 KiB chunks so large files (PDFs, export artefacts) hash
    cleanly without loading the entire file into memory.
    """

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["sha256_file"]
