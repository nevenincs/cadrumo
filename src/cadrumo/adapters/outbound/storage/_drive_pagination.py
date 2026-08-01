"""Shared containment for Google Drive ``nextPageToken`` pagination."""

from __future__ import annotations

from ._errors import OutboundStorageNetworkError


def next_drive_page_token(value: object, *, seen_tokens: set[str], action: str) -> str | None:
    """Validate the next Drive page token and refuse pagination cycles."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise OutboundStorageNetworkError(
            "Drive returned a non-string nextPageToken",
            context={"action": action, "token_type": type(value).__name__},
        )
    if value in seen_tokens:
        raise OutboundStorageNetworkError(
            "Drive returned a repeated nextPageToken",
            context={"action": action, "page_token": value},
        )
    seen_tokens.add(value)
    return value
