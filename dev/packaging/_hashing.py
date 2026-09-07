"""Import-light digest helpers for packaging artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

_CHUNK_SIZE: Final[int] = 1024 * 1024

#: The codec every digested string is measured in. A digest is a fact about
#: BYTES, so the codec is part of the rule and not a caller's detail: two sides
#: that agree on the text and disagree on the encoding compute different
#: digests and report it as a mismatch of the thing being attested.
_TEXT_CODEC: Final[str] = "utf-8"


def sha256_path(path: Path) -> str:
    """Return the lowercase SHA-256 digest of ``path`` without buffering it whole."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    """Return the lowercase SHA-256 digest of ``value`` encoded as UTF-8.

    The codec lives here rather than at each caller. Every site that hashed a
    string chose its own encoding argument -- three spellings of ``utf-8``
    across five modules -- and every one of them was correct, which is exactly
    what makes the arrangement fragile: a caller that picks a different codec,
    or omits the argument on a platform whose default is not UTF-8, produces a
    digest that disagrees with its verifier and is reported as the ATTESTED
    ARTEFACT having changed. Owning the codec here means a caller cannot get it
    wrong by doing nothing.
    """
    return hashlib.sha256(value.encode(_TEXT_CODEC)).hexdigest()


__all__ = ["sha256_path", "sha256_text"]
