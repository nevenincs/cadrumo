"""Date string parsers for the two distinct input formats used across AEAT adapters.

Provides a unified :func:`_parse_date` helper that combines format selection with an error-policy axis.

The two variants are intentionally separate because they accept *different*
wire formats:

* :func:`_parse_iso8601_date` — ``YYYY-MM-DD`` (ISO 8601).  Used wherever
  AEAT systems or profile storage serialises dates in the standard form
  (e.g. deadline-profile censo dates).

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
from typing import Final, Literal, overload

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
    except ValueError as exc:
        _log.debug("_parse_iso8601_date: %r is not a valid ISO-8601 date", cleaned)
        # BROAD-EXCEPT-RATIONALE-PYDANTIC-PARSE-PROXY:
        # Called from @field_validator stacks; ValueError propagates into the
        # pydantic ValidationError chain.
        raise ValueError(
            f"date value {cleaned!r} is not a valid ISO-8601 date (expected YYYY-MM-DD)",
        ) from exc  # BROAD-EXCEPT-RATIONALE-PYDANTIC-PARSE-PROXY


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
        # BROAD-EXCEPT-RATIONALE-PYDANTIC-PARSE-PROXY:
        # Called from @field_validator stacks; ValueError propagates into the
        # pydantic ValidationError chain.
        raise ValueError(
            f"date value {cleaned!r} is not a dd-mm-yyyy or dd/mm/yyyy date",
        )  # BROAD-EXCEPT-RATIONALE-PYDANTIC-PARSE-PROXY
    parts = re.split(r"[-/]", match.group(1))
    day, month, year = (int(p) for p in parts)
    try:
        return date(year, month, day)
    except ValueError as exc:
        _log.debug(
            "_parse_ddmmyyyy_date: %r parsed to (%d, %d, %d) which is not a valid calendar date",
            cleaned,
            day,
            month,
            year,
        )
        # BROAD-EXCEPT-RATIONALE-PYDANTIC-PARSE-PROXY:
        # Called from @field_validator stacks; ValueError propagates into the
        # pydantic ValidationError chain.
        raise ValueError(
            f"date value {cleaned!r} is not a valid calendar date",
        ) from exc  # BROAD-EXCEPT-RATIONALE-PYDANTIC-PARSE-PROXY


# ── Unified parse-date surface ────────────────────────────────────────────────

_DateFmt = Literal["iso8601", "ddmmyyyy"]
_OnError = Literal["raise", "none"]


@overload
def _parse_date(
    raw: str | None,
    *,
    fmt: _DateFmt,
    on_error: Literal["none"],
) -> date | None: ...


@overload
def _parse_date(
    raw: str | None,
    *,
    fmt: _DateFmt,
    on_error: Literal["raise"] = ...,
) -> date | None: ...


def _parse_date(
    raw: str | None,
    *,
    fmt: _DateFmt = "iso8601",
    on_error: _OnError = "raise",
) -> date | None:
    """Parse *raw* using the nominated format, applying the requested error policy.

    Args:
        raw: Input string; ``None`` and blank strings return ``None`` regardless
             of *on_error*.
        fmt: ``"iso8601"`` delegates to :func:`_parse_iso8601_date`;
             ``"ddmmyyyy"`` delegates to :func:`_parse_ddmmyyyy_date`.
        on_error: ``"raise"`` re-raises the :exc:`ValueError` from the delegate
                  (callers wrap it in their domain exception); ``"none"``
                  silently returns ``None`` on any parse failure.

    Returns:
        Parsed :class:`datetime.date`, or ``None`` when *raw* is absent or
        (when *on_error* is ``"none"``) when parsing fails.

    Raises:
        ValueError: When *on_error* is ``"raise"`` and *raw* is non-empty but
                    cannot be parsed by the selected format delegate.
    """
    delegate = _parse_iso8601_date if fmt == "iso8601" else _parse_ddmmyyyy_date
    try:
        return delegate(raw)
    except ValueError:
        if on_error == "none":
            return None
        raise


#: Public alias — cross-package callers must import ``parse_date`` rather than
#: the private ``_parse_date`` implementation name.
parse_date = _parse_date
