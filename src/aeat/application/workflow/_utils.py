"""Shared utilities for the workflow application layer."""

from __future__ import annotations

from datetime import UTC, datetime

from ...domain.profile._normalise import _normalise_key


def utc_now() -> datetime:
    """Return an aware UTC timestamp for user-CLI workflow events."""

    return datetime.now(tz=UTC)


__all__ = ["_normalise_key", "utc_now"]
