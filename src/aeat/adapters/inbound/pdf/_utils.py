"""Shared low-level helpers used by every PDF-import family adapter.

Hosts utilities that several inbound parsers (declaracion, borrador,
justificante) consume identically — keeping them here prevents the same
helper being re-implemented in each per-format module.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_HASH_CHUNK_SIZE = 65536


def sha256_file(path: Path) -> str:
    """Return the lowercase hex SHA-256 of the bytes at ``path``.

    Reads in 64 KiB chunks so PDFs larger than process memory still hash
    cleanly. Use this instead of inline ``hashlib.sha256(path.read_bytes())``
    when you need a stable digest of an on-disk artefact.
    """

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["sha256_file"]
