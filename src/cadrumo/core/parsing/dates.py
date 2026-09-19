"""Date string parsers for the two distinct input formats used across AEAT adapters.

Provides a unified :func:`_parse_date` helper that combines format selection with an error-policy axis.

The two variants are intentionally separate because they accept *different*
wire formats:

* :func:`parse_iso8601_date` — ``YYYY-MM-DD`` (ISO 8601).  Used wherever
  AEAT systems or profile storage serialises dates in the standard form
  (e.g. deadline-profile censo dates).

* :func:`parse_ddmmyyyy_date` — ``DD-MM-YYYY`` or ``DD/MM/YYYY`` (day-first,
  separator is ``-`` or ``/``).  Used wherever the AEAT G313 (Mis Datos
  Censales) HTML page publishes dates in the Spanish day-first convention.

Both functions live at the ``core`` layer: they carry no domain dependencies,
perform no I/O, and raise :exc:`ValueError` so callers can wrap the error in
the domain-appropriate exception type.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Final, Literal, overload

from pydantic import AfterValidator

from ..logging import get_logger

_log = get_logger(__name__)

# Matches the Spanish day-first wire format: dd-mm-yyyy or dd/mm/yyyy.
_DATE_DDMMYYYY_RE: Final = re.compile(r"^\s*(\d{2}[-/]\d{2}[-/]\d{4})\s*$")

# Extended-form ISO 8601 (``YYYY-MM-DD``); the compact form is deliberately refused.
_ISO_8601_EXTENDED_LENGTH: Final[int] = 10

#: The separators a date format is defined by. Each is recognised by comparison
#: and then re-emitted as its own literal below, so nothing from the input is
#: carried into the mask -- see :func:`_date_shape`.
_SHAPE_SEPARATORS: Final[tuple[str, ...]] = ("-", "/", ".", " ", ":", "T")


def _character_shape(char: str) -> str:
    """Return the class ``char`` belongs to, as a literal that never carries it.

    Every branch yields a constant. The input reaches the conditions only, so
    the mask this builds is a property of the value's shape and holds no part
    of the value itself.
    """
    if char.isdigit():
        return "9"
    for separator in _SHAPE_SEPARATORS:
        if char == separator:
            return separator
    return "A" if char.isalpha() else "?"


def _date_shape(value: str) -> str:
    """Return the character-class shape of ``value``, carrying none of it.

    The values these parsers refuse are personal data -- a descendant's date of
    birth, a censo registration date -- so a diagnostic must not echo them. What
    makes a malformed date actionable is its SHAPE: ``9999-99-99`` against
    ``99-99-9999`` says which format arrived, ``A`` says a letter reached a
    numeric position, and the mask's own length is the value's length. Two
    different dates of the same shape produce the same mask, and no mask
    reconstructs the value it came from.
    """
    return "".join(_character_shape(char) for char in value)


def parse_iso8601_date(raw: str | None) -> date | None:
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
        _log.debug(
            "parse_iso8601_date: refused a value of shape %s; expected 9999-99-99",
            _date_shape(cleaned),
        )
        # BROAD-EXCEPT-RATIONALE-PYDANTIC-PARSE-PROXY:
        # Called from @field_validator stacks; ValueError propagates into the
        # pydantic ValidationError chain.
        raise ValueError(
            f"date value {cleaned!r} is not a valid ISO-8601 date (expected YYYY-MM-DD)",
        ) from exc  # BROAD-EXCEPT-RATIONALE-PYDANTIC-PARSE-PROXY


def require_iso8601_date(raw: str) -> date:
    """Parse a required extended-form ISO-8601 date, refusing every other shape.

    The strict counterpart of :func:`parse_iso8601_date` for values that must
    be present and must be a real calendar date. Absence is a refusal rather
    than ``None``, and the compact ``YYYYMMDD`` form
    :meth:`~datetime.date.fromisoformat` also accepts is refused, so the one
    admitted shape is the extended ``YYYY-MM-DD`` the AEAT wire formats use.

    A model that declares a date as a length-bounded string admits an
    impossible calendar date -- ``2026-99-99`` and ``2026-02-30`` are both ten
    characters -- and every consumer downstream of it inherits that value as
    if a date authority had approved it.

    Args:
        raw: The declared date string.

    Returns:
        The parsed calendar date.

    Raises:
        ValueError: When ``raw`` is absent, is not extended-form ``YYYY-MM-DD``,
            or names a date that does not exist. Callers wrap this in the
            domain-appropriate exception; inside a pydantic validator it
            propagates into the ``ValidationError`` chain.
    """
    cleaned = raw.strip() if raw else ""
    if len(cleaned) != _ISO_8601_EXTENDED_LENGTH:
        raise ValueError(
            f"date value {raw!r} is not a valid ISO-8601 date (expected YYYY-MM-DD)",
        )
    parsed = parse_iso8601_date(cleaned)
    if parsed is None:  # pragma: no cover - a length-10 non-empty string always parses or raises.
        raise ValueError(
            f"date value {raw!r} is not a valid ISO-8601 date (expected YYYY-MM-DD)",
        )
    return parsed


def _iso_date_string(value: str) -> str:
    """Validate ``value`` as an extended-form ISO-8601 date and return it unchanged."""
    require_iso8601_date(value)
    return value


type IsoDateString = Annotated[str, AfterValidator(_iso_date_string)]
"""A wire date that stays a string but must name a real calendar date.

The field annotation behind every observation and payload whose declared date
crosses a boundary as ``YYYY-MM-DD``. It keeps the serialised shape a string
while making :func:`require_iso8601_date` the single admission authority, so a
length bound can no longer stand in for a date check.

Use a real :class:`~datetime.date` field where the value is only ever handled
as a date; use this where the string form itself is the persisted or
transported contract.
"""


def parse_ddmmyyyy_date(raw: str | None) -> date | None:
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
        _log.debug(
            "parse_ddmmyyyy_date: refused a value of shape %s; expected 99-99-9999 or 99/99/9999",
            _date_shape(cleaned),
        )
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
            "parse_ddmmyyyy_date: a value of shape %s named month %d day %d, which is not a calendar date",
            _date_shape(cleaned),
            month,
            day,
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
        fmt: ``"iso8601"`` delegates to :func:`parse_iso8601_date`;
             ``"ddmmyyyy"`` delegates to :func:`parse_ddmmyyyy_date`.
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
    delegate = parse_iso8601_date if fmt == "iso8601" else parse_ddmmyyyy_date
    try:
        return delegate(raw)
    except ValueError:
        if on_error == "none":
            return None
        raise


#: Public alias — cross-package callers must import ``parse_date`` rather than
#: the private ``_parse_date`` implementation name.
parse_date = _parse_date
