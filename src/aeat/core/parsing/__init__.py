"""Shared parsing primitives for the AEAT application layer.

Public surface
--------------

* :func:`parse_bool` — parse a raw string token into ``True``, ``False``,
  or ``None`` (absent / unrecognised).
* :func:`parse_date` — unified date parser with format and error-policy axes.
* :func:`parse_iso8601_date` — parse an ISO-8601 date string (``YYYY-MM-DD``).
* :func:`parse_ddmmyyyy_date` — parse a Spanish day-first date string
  (``DD-MM-YYYY`` or ``DD/MM/YYYY``).

The implementation modules still own underscore-prefixed helpers for
package-local tests and tightly scoped internal consumers. This package
initializer exposes only public parser names so cross-package callers cannot
accidentally depend on private compatibility aliases.
"""

from __future__ import annotations

from datetime import date

from ._dates import (
    _parse_ddmmyyyy_date as _parse_ddmmyyyy_date_impl,
)
from ._dates import (
    _parse_iso8601_date as _parse_iso8601_date_impl,
)
from ._dates import parse_date
from ._utils import parse_bool


def parse_iso8601_date(raw: str | None) -> date | None:
    """Parse an ISO-8601 date string (``YYYY-MM-DD``) into a :class:`~datetime.date`."""
    return _parse_iso8601_date_impl(raw)


def parse_ddmmyyyy_date(raw: str | None) -> date | None:
    """Parse a Spanish day-first date string (``DD-MM-YYYY`` / ``DD/MM/YYYY``)."""
    return _parse_ddmmyyyy_date_impl(raw)


__all__ = [
    "parse_bool",
    "parse_date",
    "parse_ddmmyyyy_date",
    "parse_iso8601_date",
]
