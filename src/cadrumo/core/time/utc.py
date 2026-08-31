"""Canonical UTC :class:`~datetime.datetime` helpers.

Two semantics exist across the codebase for handling naive datetimes:

* :func:`coerce_utc_aware` — coerce a naive datetime to UTC-aware by
  attaching :data:`~datetime.UTC`.  Used where the source produces
  naive datetimes (e.g. PKCS#12 certificate timestamps).

* :func:`validate_utc_aware` — reject naive datetimes or non-UTC
  datetimes with :class:`~cadrumo.core.errors.CoreValidationError`.  Used
  at persistence and model boundaries where a naive datetime indicates
  a programming error.

:func:`parse_iso_datetime` is deliberately policy-neutral: it normalises the
``Z`` suffix and returns the parsed :class:`~datetime.datetime`, leaving callers
to choose :func:`coerce_utc_aware` or :func:`validate_utc_aware`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator

from ..errors.hierarchy import CoreValidationError


def parse_iso_datetime(raw: str) -> datetime:
    """Parse an ISO-8601 datetime string, normalising a trailing ``Z`` to ``+00:00``.

    :meth:`datetime.fromisoformat` historically rejects the ``Z`` UTC suffix; this
    normalises it first so UTC-suffixed timestamps parse. The result may be naive
    or aware depending on the input — pass it through :func:`validate_utc_aware` or
    :func:`coerce_utc_aware` when an aware value is required.
    """
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def coerce_utc_aware(value: datetime) -> datetime:
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


def validate_utc_aware(value: datetime) -> datetime:
    """Return *value* unchanged if it is a UTC-aware datetime.

    Raises :class:`cadrumo.core.errors.CoreValidationError` when *value*
    is naive (no ``tzinfo``) or when its UTC offset is not zero
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


UtcInstant = Annotated[datetime, AfterValidator(validate_utc_aware)]
"""A :class:`~datetime.datetime` field pinned to the canonical UTC contract.

The declarative form of :func:`validate_utc_aware`, for the many models
whose fields document an instant. Those models each carried their own
``field_validator`` calling the same helper, which made enrolment a thing an
author had to remember rather than a thing the type says: a field declared
as a bare ``datetime`` looks identical to an enrolled one at the point of
declaration, so the omissions are invisible in review and only surface when
a naive value has already been hashed or persisted.

It validates rather than coerces, deliberately. A naive instant arriving at
a model boundary is not a value with a missing offset, it is a value whose
offset is unknown -- attaching UTC would invent the one fact in doubt, and
would do it silently. Sources that genuinely produce naive local times (a
PKCS#12 certificate stamp) belong on :func:`coerce_utc_aware` at the point
they are read, where the assumption is stated once and visibly.

Refusal also protects derived identity. A content-addressed id that hashes
an instant's ``isoformat()`` gets a different digest for each spelling of
the same moment, so admitting several spellings turns one event into
several records; admitting only UTC leaves exactly one.
"""
