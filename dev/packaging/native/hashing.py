"""Content hashes shared by native packaging operations."""

import hashlib
from pathlib import Path


def digest(path: Path) -> str:
    """Hash one build input or delivered file."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
