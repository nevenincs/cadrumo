"""Shared parsing primitives for the AEAT application layer.

Public surface
--------------

* :func:`parse_bool` — parse a raw string token into ``True``, ``False``,
  or ``None`` (absent / unrecognised).
* :func:`parse_date` — unified date parser with format and error-policy axes.
* :func:`parse_iso8601_date` — parse an ISO-8601 date string (``YYYY-MM-DD``).
* :func:`require_iso8601_date` and :data:`IsoDateString` — the strict admission
  authority for a required wire date that must name a real calendar date.
* :func:`parse_ddmmyyyy_date` — parse a Spanish day-first date string
  (``DD-MM-YYYY`` or ``DD/MM/YYYY``).
* :func:`normalise_iso_4217_currency` — normalise a raw currency token to its
  uppercase ISO 4217 code.
* :func:`normalise_iso_3166_alpha2_jurisdiction` — validate a source
  jurisdiction as an ISO 3166-1 alpha-2 code.
* :func:`enum_value` — coerce an enum member (or any value) to its wire
  string, mapping ``None`` to ``""``.

The implementation modules still own underscore-prefixed helpers for
package-local tests and tightly scoped internal consumers. This package
initializer exposes only public parser names so cross-package callers cannot
accidentally depend on private compatibility aliases.
"""

from __future__ import annotations

from datetime import date

from .codes import IsoCurrencyCode, normalise_iso_3166_alpha2_jurisdiction, normalise_iso_4217_currency
from .dates import IsoDateString, parse_date, require_iso8601_date
from .dates import _parse_ddmmyyyy_date as _parse_ddmmyyyy_date_impl
from .dates import _parse_iso8601_date as _parse_iso8601_date_impl
from .utils import enum_value, parse_bool


def parse_iso8601_date(raw: str | None) -> date | None:
    """Parse an ISO-8601 date string (``YYYY-MM-DD``) into a :class:`~datetime.date`."""
    return _parse_iso8601_date_impl(raw)


def parse_ddmmyyyy_date(raw: str | None) -> date | None:
    """Parse a Spanish day-first date string (``DD-MM-YYYY`` / ``DD/MM/YYYY``)."""
    return _parse_ddmmyyyy_date_impl(raw)


__all__ = [
    "IsoCurrencyCode",
    "IsoDateString",
    "enum_value",
    "normalise_iso_3166_alpha2_jurisdiction",
    "normalise_iso_4217_currency",
    "parse_bool",
    "parse_date",
    "parse_ddmmyyyy_date",
    "parse_iso8601_date",
    "require_iso8601_date",
]
