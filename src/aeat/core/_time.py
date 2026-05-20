"""Canonical time helpers shared across the project."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp.

    The single canonical source for the current instant. Tests patch or
    freeze this one definition rather than each subpackage's local copy.
    """
    return datetime.now(tz=UTC)
