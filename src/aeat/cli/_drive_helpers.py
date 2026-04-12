"""Pure helpers for the Drive CLI sub-app.

Anything in this module must be unit-testable without touching the
Google Drive API. Helpers that need a live service belong in
:mod:`aeat.cli.drive` directly.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path


def escape_drive_query_literal(value: str) -> str:
    """Escape a string literal for inclusion in a Drive ``q=`` parameter.

    Drive query syntax uses single-quoted strings. Inner single quotes
    must be escaped as ``\\'`` and inner backslashes as ``\\\\``. The
    Google client library does not perform this escaping for callers.

    Args:
        value: Raw string to embed inside a ``'...'`` literal.

    Returns:
        The escaped string, ready to drop into a Drive query expression.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


def guess_mime_type(path: Path) -> str:
    """Guess the MIME type for a local file path.

    Falls back to ``application/octet-stream`` for unknown extensions
    so callers can always feed the result into a ``MediaFileUpload``.

    Args:
        path: Path to a local file.

    Returns:
        Best-effort MIME type string.
    """
    guess, _ = mimetypes.guess_type(path.as_posix())
    return guess or "application/octet-stream"


def build_listing_query(folder_id: str | None) -> str:
    """Compose a Drive ``q=`` filter for listing inside an optional folder.

    The filter always excludes trashed files. When ``folder_id`` is
    given the filter scopes the listing to direct children of that
    folder; otherwise it lists everything visible to the caller.

    Args:
        folder_id: Drive folder ID to scope the listing to.

    Returns:
        Drive query string.
    """
    if folder_id:
        return f"'{escape_drive_query_literal(folder_id)}' in parents and trashed=false"
    return "trashed=false"
