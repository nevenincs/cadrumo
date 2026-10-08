"""Pure parsing of the Google Drive file references stored attachment records carry."""

from __future__ import annotations

import re
from typing import Final

_FILE_REFERENCE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"/d/(?P<id>[A-Za-z0-9_-]{10,})(?=/|[?#]|$)"),
    re.compile(r"[?&]id=(?P<id>[A-Za-z0-9_-]{10,})(?=[&#]|$)"),
)
_BARE_FILE_ID: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_-]{25,}")


def parse_google_drive_file_id(reference: str) -> str | None:
    """Return a complete Drive file ID from a supported reference shape.

    URL-embedded IDs have an unambiguous path or query context and accept ten
    or more allowed characters. A bare reference needs twenty-five characters
    so ordinary hyphenated words are not mistaken for IDs. URL matches end at a
    real component boundary; a valid prefix before punctuation is not enough.
    """
    candidate = reference.strip()
    for pattern in _FILE_REFERENCE_PATTERNS:
        match = pattern.search(candidate)
        if match is not None:
            drive_id = match.group("id")
            if isinstance(drive_id, str):
                return drive_id
    if _BARE_FILE_ID.fullmatch(candidate) is not None:
        return candidate
    return None


__all__ = [
    "parse_google_drive_file_id",
]
