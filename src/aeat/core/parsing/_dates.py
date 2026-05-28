"""Date string parsers for the two distinct input formats used across AEAT adapters.

The two variants are intentionally separate because they accept *different*
wire formats:

* :func:`_parse_iso8601_date` — ``YYYY-MM-DD`` (ISO 8601).  Used wherever
  AEAT systems or profile storage serialises dates in the standard form
  (e.g. deadline-profile census dates).

* :func:`_parse_ddmmyyyy_date` — ``DD-MM-YYYY`` or ``DD/MM/YYYY`` (day-first,
  separator is ``-`` or ``/``).  Used wherever the AEAT G313 (Mis Datos
  Censales) HTML page publishes dates in the Spanish day-first convention.

Both functions live at the ``core`` layer: they carry no domain dependencies,
perform no I/O, and raise :exc:`ValueError` so callers can wrap the error in
the domain-appropriate exception type.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Final

from ..logging import get_logger

_log = get_logger(__name__)

# Matches the Spanish day-first wire format: dd-mm-yyyy or dd/mm/yyyy.
_DATE_DDMMYYYY_RE: Final = re.compile(r"^\s*(\d{2}[-/]\d{2}[-/]\d{4})\s*$")


def _parse_iso8601_date(raw: str | None) -> date | None:
    """Parse an ISO-8601 date string (``YYYY-MM-DD``) into a :class:`date`.

    Args:
        raw: Raw string from a profile or registry field.  ``None`` and empty
             strings are treated as absent and return ``None``.

    Returns:
        Parsed :class:`datetime.date`, or ``None`` when *raw* is absent.

    Raises:
        ValueError: When *raw* is non-empty but does not conform to ISO-8601.
                    Callers are expected to wrap this in the appropriate
                    domain exception.
    """
    if not raw:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        _log.debug("_parse_iso8601_date: %r is not a valid ISO-8601 date", cleaned)
        raise ValueError(
            f"date value {cleaned!r} is not a valid ISO-8601 date (expected YYYY-MM-DD)"
        )


def _parse_ddmmyyyy_date(raw: str | None) -> date | None:
    """Parse a Spanish day-first date string (``DD-MM-YYYY`` / ``DD/MM/YYYY``).

    Both separator characters (``-`` and ``/``) are accepted because the AEAT
    G313 page uses them interchangeably across form revisions.

    Args:
        raw: Raw string scraped from a G313 HTML field.  ``None`` and empty
             strings are treated as absent and return ``None``.

    Returns:
        Parsed :class:`datetime.date`, or ``None`` when *raw* is absent.

    Raises:
        ValueError: When *raw* is non-empty but does not match the expected
                    format or represents an invalid calendar date.  Callers are
                    expected to wrap this in the appropriate domain exception.
    """
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    match = _DATE_DDMMYYYY_RE.match(cleaned)
    if match is None:
        _log.debug("_parse_ddmmyyyy_date: %r does not match dd-mm-yyyy / dd/mm/yyyy", cleaned)
        raise ValueError(
            f"date value {cleaned!r} is not a dd-mm-yyyy or dd/mm/yyyy date"
        )
    parts = re.split(r"[-/]", match.group(1))
    day, month, year = (int(p) for p in parts)
    try:
        return date(year, month, day)
    except ValueError:
        _log.debug(
            "_parse_ddmmyyyy_date: %r parsed to (%d, %d, %d) which is not a valid calendar date",
            cleaned,
            day,
            month,
            year,
        )
        raise ValueError(
            f"date value {cleaned!r} is not a valid calendar date"
        )
