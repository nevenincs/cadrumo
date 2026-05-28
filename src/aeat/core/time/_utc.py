"""Canonical UTC datetime helpers.

Two semantics exist across the codebase for handling naive datetimes:

* :func:`_coerce_utc_aware` — coerce a naive datetime to UTC-aware by
  attaching :data:`datetime.UTC`.  Used where the source produces
  naive datetimes (e.g. PKCS#12 certificate timestamps).

* :func:`_validate_utc_aware` — reject naive datetimes or non-UTC
  datetimes with :class:`aeat.core.errors.CoreValidationError`.  Used
  at persistence and model boundaries where a naive datetime indicates
  a programming error.
"""

from __future__ import annotations

from datetime import UTC, datetime

from aeat.core.errors import CoreValidationError


def _coerce_utc_aware(value: datetime) -> datetime:
    """Return a UTC-aware datetime, coercing a naive one if necessary.

    Naive datetimes have :data:`datetime.UTC` attached.  Timezone-aware
    datetimes whose offset differs from UTC are converted via
    :meth:`datetime.astimezone`.

    Args:
        value: Any :class:`datetime` instance, naive or aware.

    Returns:
        A UTC-aware :class:`datetime` instance.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _validate_utc_aware(value: datetime) -> datetime:
    """Return *value* unchanged if it is a UTC-aware datetime.

    Raises :class:`aeat.core.errors.CoreValidationError` when *value*
    is naive (no :attr:`tzinfo`) or when its UTC offset is not zero
    (i.e. not UTC).

    Args:
        value: The datetime to validate.

    Returns:
        *value* unchanged.

    Raises:
        CoreValidationError: When *value* is naive or not in UTC.
    """
    if value.tzinfo is None:
        raise CoreValidationError("datetime must be timezone-aware UTC")
    if value.utcoffset() != UTC.utcoffset(value):
        raise CoreValidationError("datetime must be in UTC")
    return value
