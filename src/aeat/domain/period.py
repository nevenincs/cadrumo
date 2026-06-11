"""Filing-period parsing primitives shared across the application layer.

The application stores filing periods in a single canonical token shape:

- ``YYYYQ[1-4]`` or ``YYYY-[1-4]T`` — quarterly (e.g. ``2026Q1`` or ``2026-1T``)
- ``YYYY-MM``      — monthly  (e.g. ``2026-03``)
- ``YYYYA``        — annual   (e.g. ``2026A``)
- bare ``YYYY``    — annual shorthand

Pieces of the verification surface receive raw AEAT-scraped tokens that
carry only ``nT`` for quarterly and rely on a separately-supplied
``ejercicio`` (filing year). Both callers ultimately resolve to the same
``(year, registry_period)`` shape, where ``registry_period`` is the
registry-native period identifier (``"1T"`` … ``"4T"``, ``"01"`` … ``"12"``,
``"0A"``, ``"1P"`` … ``"3P"``).

The ``nP`` tokens are the Impuesto sobre Sociedades pago-fraccionado
instalment claves (Modelo 202). Per the AEAT Modelo 202 instructions,
``1P`` is the payment made in the first twenty days of April, ``2P``
the equivalent October payment, and ``3P`` the December payment; the
period-boundary helpers map each instalment to its payment month.

This module centralises that parsing and the canonical period-end-date
mapping each surface needs. Callers wrap :class:`ValueError` into their
own domain error type (e.g. ``ModeloBuilderError``,
``RegistrySnapshotError``) at the boundary they own.

Registry-introspection surfaces use bare registry tokens directly, or
an explicit ``(filing_year, registry_period)`` scope when the filing
year must participate in revision selection.
"""

from __future__ import annotations

import re
from datetime import date

from ..core.errors import AeatError


class PeriodError(AeatError):
    """Base class for period-related errors."""


class PeriodValidationError(PeriodError, ValueError):
    """Raised when a period token is malformed. Inherits from ValueError for Pydantic."""


_QUARTER_PERIOD_RE = re.compile(r"^(?P<year>\d{4})Q(?P<quarter>[1-4])$")
_DASHED_QUARTER_PERIOD_RE = re.compile(r"^(?P<year>\d{4})-(?P<quarter>[1-4])T$")
_MONTH_PERIOD_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>0[1-9]|1[0-2])$")
_ANNUAL_PERIOD_RE = re.compile(r"^(?P<year>\d{4})A$")
_BARE_YEAR_RE = re.compile(r"^\d{4}$")
_RAW_QUARTER_RE = re.compile(r"^(?P<quarter>[1-4])T$")
_PAGO_FRACCIONADO_PERIOD_RE = re.compile(r"^(?P<year>\d{4})P(?P<instalment>[1-3])$")


def parse_canonical_period(period: str, *, ejercicio: str | None = None) -> tuple[int, str]:
    """Return ``(filing_year, registry_period)`` for a canonical period token.

    Args:
        period: A canonical filing-period token (``YYYYQ[1-4]``,
            ``YYYY-[1-4]T``, ``YYYY-MM``, ``YYYYA``, bare ``YYYY``,
            or ``YYYYPn`` for pago-fraccionado instalments). When ``ejercicio`` is
            supplied, the raw AEAT quarterly form (``nT``) is also
            accepted; the year then comes from ``ejercicio``.
        ejercicio: Optional filing year string consumed only when
            ``period`` is a raw ``nT`` quarterly token. Pass ``None``
            for callers that only see canonical inputs.

    Returns:
        ``(filing_year, registry_period)`` where the second element is
        the registry-native period (``"1T"`` … ``"4T"``, ``"01"`` …
        ``"12"``, ``"0A"``, or ``"1P"`` … ``"3P"``).

    Raises:
        PeriodValidationError: When ``period`` is none of the accepted shapes.
    """
    if match := _QUARTER_PERIOD_RE.fullmatch(period):
        return int(match.group("year")), f"{match.group('quarter')}T"
    if match := _DASHED_QUARTER_PERIOD_RE.fullmatch(period):
        return int(match.group("year")), f"{match.group('quarter')}T"
    if match := _MONTH_PERIOD_RE.fullmatch(period):
        return int(match.group("year")), match.group("month")
    if match := _ANNUAL_PERIOD_RE.fullmatch(period):
        return int(match.group("year")), "0A"
    if _BARE_YEAR_RE.fullmatch(period):
        return int(period), "0A"
    if match := _PAGO_FRACCIONADO_PERIOD_RE.fullmatch(period):
        return int(match.group("year")), f"{match.group('instalment')}P"
    if ejercicio is not None and (match := _RAW_QUARTER_RE.fullmatch(period)):
        return int(ejercicio), f"{match.group('quarter')}T"
    raise PeriodValidationError(f"cannot map filing period {period!r} to a registry period")


def period_start_date(filing_year: int, registry_period: str) -> date:
    """Return the inclusive start-of-period date for a registry token.

    Args:
        filing_year: The filing year resolved from
            :func:`parse_canonical_period`.
        registry_period: One of ``"1T"`` … ``"4T"``, ``"01"`` … ``"12"``,
            ``"0A"``.

    Returns:
        The first day of the period the token covers (e.g. ``"1T"`` →
        ``YYYY-01-01``, ``"4T"`` → ``YYYY-10-01``, ``"0A"`` →
        ``YYYY-01-01``, ``"03"`` → ``YYYY-03-01``, ``"1P"`` →
        ``YYYY-04-01``, ``"2P"`` → ``YYYY-10-01``, ``"3P"`` →
        ``YYYY-12-01``).

    Raises:
        PeriodValidationError: When ``registry_period`` is not a recognised shape.
    """
    if registry_period == "1T":
        return date(filing_year, 1, 1)
    if registry_period == "2T":
        return date(filing_year, 4, 1)
    if registry_period == "3T":
        return date(filing_year, 7, 1)
    if registry_period == "4T":
        return date(filing_year, 10, 1)
    if registry_period == "0A":
        return date(filing_year, 1, 1)
    if registry_period == "1P":
        return date(filing_year, 4, 1)
    if registry_period == "2P":
        return date(filing_year, 10, 1)
    if registry_period == "3P":
        return date(filing_year, 12, 1)
    try:
        return date(filing_year, int(registry_period), 1)
    except ValueError as exc:
        raise PeriodValidationError(f"invalid registry period {registry_period!r}") from exc


def period_end_date(filing_year: int, registry_period: str) -> date:
    """Return the inclusive end-of-period date for a registry token.

    Args:
        filing_year: The filing year resolved from
            :func:`parse_canonical_period`.
        registry_period: One of ``"1T"`` … ``"4T"``, ``"01"`` … ``"12"``,
            ``"0A"``.

    Returns:
        The last day of the period the token covers (e.g. ``"1T"`` →
        ``YYYY-03-31``, ``"0A"`` and ``"4T"`` → ``YYYY-12-31``, ``"03"``
        → ``YYYY-03-01`` for the monthly-as-first-of-month convention
        the application layer already uses, ``"1P"`` → ``YYYY-04-30``,
        ``"2P"`` → ``YYYY-10-31``, ``"3P"`` → ``YYYY-12-31``).

    Raises:
        PeriodValidationError: When ``registry_period`` is not a recognised shape.
    """
    if registry_period == "1T":
        return date(filing_year, 3, 31)
    if registry_period == "2T":
        return date(filing_year, 6, 30)
    if registry_period == "3T":
        return date(filing_year, 9, 30)
    if registry_period in {"4T", "0A"}:
        return date(filing_year, 12, 31)
    if registry_period == "1P":
        return date(filing_year, 4, 30)
    if registry_period == "2P":
        return date(filing_year, 10, 31)
    if registry_period == "3P":
        return date(filing_year, 12, 31)
    try:
        return date(filing_year, int(registry_period), 1)
    except ValueError as exc:
        raise PeriodValidationError(f"invalid registry period {registry_period!r}") from exc


__all__ = [
    "PeriodError",
    "PeriodValidationError",
    "parse_canonical_period",
    "period_end_date",
    "period_start_date",
]
