"""Pure Google Drive v3 query-literal helpers."""

from __future__ import annotations


def escape_google_drive_query_literal(value: str) -> str:
    """Escape string content for a single-quoted Drive v3 query literal.

    Drive v3 query literals escape backslashes and single quotes with a
    preceding backslash. Replace backslashes first so an escape introduced
    for a single quote is not itself re-escaped.

    Args:
        value: String value embedded in a single-quoted query literal.

    Returns:
        Escaped query-literal content.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


__all__ = ["escape_google_drive_query_literal"]
