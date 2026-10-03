"""Pure parsing and construction for Google Drive file and folder references."""

from __future__ import annotations

import re
from typing import Final

_URL_FILE_ID: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_-]{10,}")
_FILE_REFERENCE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"/d/(?P<id>[A-Za-z0-9_-]{10,})(?=/|[?#]|$)"),
    re.compile(r"[?&]id=(?P<id>[A-Za-z0-9_-]{10,})(?=[&#]|$)"),
)
_BARE_FILE_ID: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_-]{25,}")
_FOLDER_REFERENCE: Final[re.Pattern[str]] = re.compile(r"/folders/(?P<id>[A-Za-z0-9_-]{10,})(?=/|[?#]|$)")


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


def parse_google_drive_folder_id(reference: str) -> str | None:
    """Return a complete folder ID, preserving the file-reference fallback.

    Folder URLs use a ten-character minimum. Bare IDs and the file URL/query
    forms retain the file parser's context-specific admission rules because a
    Drive folder and file ID have the same provider shape.
    """
    match = _FOLDER_REFERENCE.search(reference.strip())
    if match is not None:
        folder_id = match.group("id")
        if isinstance(folder_id, str):
            return folder_id
    return parse_google_drive_file_id(reference)


def build_google_drive_file_reference(file_id: str) -> str:
    """Build the canonical URL for a complete URL-context Drive file ID.

    Raises:
        ValueError: ``file_id`` is not a ten-or-more-character Drive ID.
    """
    if _URL_FILE_ID.fullmatch(file_id) is None:
        raise ValueError("Google Drive file ID has an invalid URL-context shape")
    return f"https://drive.google.com/file/d/{file_id}"


__all__ = [
    "build_google_drive_file_reference",
    "parse_google_drive_file_id",
    "parse_google_drive_folder_id",
]
