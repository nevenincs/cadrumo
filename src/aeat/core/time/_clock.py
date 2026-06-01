"""Canonical wall-clock helpers for the AEAT domain.

A single, testable entry-point for obtaining the current UTC time.
Call-sites must import :func:`now` from :mod:`aeat.core.time` rather
than inlining ``datetime.now(tz=UTC)`` directly, so the production
clock can be traced and call-sites stay uniform.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..logging import get_logger

_logger = get_logger(__name__)


def now() -> datetime:
    """Return the current UTC-aware datetime.

    Returns:
        A :class:`datetime.datetime` instance with :data:`datetime.UTC` as its
        ``tzinfo``.
    """
    return datetime.now(tz=UTC)
