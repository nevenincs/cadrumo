"""Shared utilities for the workflow application layer."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return an aware UTC timestamp for user-CLI workflow events."""

    return datetime.now(tz=UTC)


def _normalise_key(value: str) -> str:
    """Return the canonical key form used by setup/edit commands.

    Strips surrounding whitespace, lowercases, and folds dashes into
    dots. Underscores are preserved verbatim so registry-canonical
    keys (e.g. ``does_intracomunitario`` and ``iva.roi_enrolled``)
    survive the round-trip through the user-cli store and reach the
    deadline engine, which looks values up by exact key.
    """

    return value.strip().lower().replace("-", ".")
