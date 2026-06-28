"""Canonical time and :class:`~datetime.datetime` helpers for the AEAT domain.

Public surface
--------------

* :func:`now` — return the current UTC-aware :class:`~datetime.datetime`.
* :func:`parse_iso_datetime` — parse ISO-8601 text before applying the
  caller's UTC policy.
* :func:`coerce_utc_aware` — coerce naive or offset-aware datetimes to UTC.
* :func:`validate_utc_aware` — assert UTC-awareness or raise
  :class:`~aeat.core.errors.CoreValidationError`.
"""

from __future__ import annotations

from ._clock import now
from ._utc import coerce_utc_aware, parse_iso_datetime, validate_utc_aware

__all__ = [
    "coerce_utc_aware",
    "now",
    "parse_iso_datetime",
    "validate_utc_aware",
]
