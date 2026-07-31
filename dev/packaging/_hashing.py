"""Import-light streamed digest helpers for packaging artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

_CHUNK_SIZE: Final[int] = 1024 * 1024


def sha256_path(path: Path) -> str:
    """Return the lowercase SHA-256 digest of ``path`` without buffering it whole."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["sha256_path"]
