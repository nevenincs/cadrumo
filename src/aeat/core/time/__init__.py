"""Canonical time and datetime helpers for the AEAT domain.

Public surface
--------------

* :func:`_now` — return the current UTC-aware :class:`datetime`.
* :func:`_coerce_utc_aware` — coerce naive or offset-aware datetimes to UTC.
* :func:`_validate_utc_aware` — assert UTC-awareness or raise
  :class:`aeat.core.errors.CoreValidationError`.
"""

from __future__ import annotations

from ._clock import _now
from ._utc import _coerce_utc_aware, _validate_utc_aware

__all__ = [
    "_coerce_utc_aware",
    "_now",
    "_validate_utc_aware",
]
