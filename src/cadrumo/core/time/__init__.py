"""Canonical time and :class:`~datetime.datetime` helpers for the AEAT domain.

Public surface
--------------

* :func:`now` — return the current UTC-aware :class:`~datetime.datetime`.
* :func:`today_madrid` — the current Europe/Madrid civil date (the authority for
  regulated date-boundary reference-date defaults), derived from :func:`now`.
* :data:`MADRID_TZ` — Spain's peninsular civil timezone (Europe/Madrid).
* :func:`frozen_clock` — replay/test-scoped seam that freezes :func:`now`.
* :func:`clock_is_frozen` — whether a :func:`frozen_clock` scope is active.
* :func:`parse_iso_datetime` — parse ISO-8601 text before applying the
  caller's UTC policy.
* :func:`coerce_utc_aware` — coerce naive or offset-aware datetimes to UTC.
* :func:`validate_utc_aware` — assert UTC-awareness or raise
  :class:`core.errors.CoreValidationError`.
* :data:`UtcInstant` — the same contract as a pydantic field annotation, for
  models that declare an instant.
* :func:`validate_inclusive_date_range` — assert a ``since``/``until`` pair
  names a non-empty closed interval.
* :func:`validate_inclusive_iso_date_range` — the same invariant applied to the
  serialised ``YYYY-MM-DD`` bounds carried on wire payloads.
"""

from __future__ import annotations

from ._clock import MADRID_TZ, clock_is_frozen, frozen_clock, now, today_madrid
from ._range import validate_inclusive_date_range, validate_inclusive_iso_date_range
from ._utc import UtcInstant, coerce_utc_aware, parse_iso_datetime, validate_utc_aware

__all__ = [
    "MADRID_TZ",
    "UtcInstant",
    "clock_is_frozen",
    "coerce_utc_aware",
    "frozen_clock",
    "now",
    "parse_iso_datetime",
    "today_madrid",
    "validate_inclusive_date_range",
    "validate_inclusive_iso_date_range",
    "validate_utc_aware",
]
