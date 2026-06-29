"""Canonical period code enumeration for filing periods.

Period codes represent the filing frequency and scheme for tax returns:
- Quarterly: 1T, 2T, 3T, 4T (standard filing periods)
- Instalment: 1P, 2P, 3P, 4P (corporate-tax/IS instalment periods)
- Annual: 0A
- Monthly: 01-12 (calendar months)
- OSS/IOSS: EXT-1T, EXT-2T, EXT-3T, EXT-4T (extra-Union scheme)
- Ad-hoc/Event: AD-HOC, EVENT-N (event-driven filings)

:class:`StandardPeriodCode` is the canonical :class:`~enum.StrEnum` for
the basic period codes (1T-4T, 1P-4P, 0A, 01-12). Extended forms
(EXT-*, AD-HOC, EVENT-*) are validated via separate regex patterns for
modeller flexibility. :class:`Period` combines one accepted code with a
filing year, and :class:`PeriodKind` classifies the resulting cadence.
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from enum import StrEnum
from typing import Annotated, override

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from .errors import AeatError


class StandardPeriodCode(StrEnum):
    """Canonical enumeration of standard filing-period codes."""

    Q1 = "1T"
    Q2 = "2T"
    Q3 = "3T"
    Q4 = "4T"

    P1 = "1P"
    P2 = "2P"
    P3 = "3P"
    P4 = "4P"

    ANNUAL = "0A"

    JAN = "01"
    FEB = "02"
    MAR = "03"
    APR = "04"
    MAY = "05"
    JUN = "06"
    JUL = "07"
    AUG = "08"
    SEP = "09"
    OCT = "10"
    NOV = "11"
    DEC = "12"


_STANDARD_PERIOD_SET = frozenset(StandardPeriodCode)
_EXTENDED_PERIOD_SET = frozenset(("EXT-1T", "EXT-2T", "EXT-3T", "EXT-4T"))
_AD_HOC_PERIOD = "AD-HOC"
_EXT_PERIOD_RE = re.compile(r"^EXT-[1-4]T$")
_EVENT_PERIOD_RE = re.compile(r"^EVENT-\d+$")
_DISPLAY_PERIOD_RE = re.compile(r"^(?P<year>\d{4})\s+(?P<code>[A-Z0-9]+(?:-[A-Z0-9]+)*)$", re.I)

def _validate_period_against_registry(value: str) -> str:
    """Validate and normalize a period code against the union of accepted forms.

    Accepts StandardPeriodCode members, extended OSS/IOSS forms (EXT-1T..EXT-4T),
    ad-hoc literal (AD-HOC), and event-driven forms (EVENT-N where N is an integer).

    Raises ValueError with the full accepted-set list on rejection; pydantic
    wraps it into a ValidationError at the BeforeValidator boundary.
    """
    if not isinstance(value, str):
        raise ValueError(f"period code must be a string, got {type(value).__name__}")

    normalized = value.strip().upper()

    if normalized in _STANDARD_PERIOD_SET:
        return normalized
    if normalized in _EXTENDED_PERIOD_SET:
        return normalized
    if normalized == _AD_HOC_PERIOD:
        return normalized
    if _EVENT_PERIOD_RE.match(normalized):
        return normalized

    accepted = _format_accepted_period_set()
    raise ValueError(f"invalid period code '{value}'; accepted forms: {accepted}")


def accepted_period_codes() -> tuple[str, ...]:
    """Return the fully enumerable period codes (StandardPeriodCode + extended literals)."""
    return tuple(sorted(_STANDARD_PERIOD_SET | _EXTENDED_PERIOD_SET | {_AD_HOC_PERIOD}))


def accepted_period_patterns() -> tuple[str, ...]:
    """Return the period code patterns (including regex shapes for EVENT-N)."""
    return (
        "StandardPeriodCode (1T-4T, 1P-4P, 0A, 01-12)",
        "Extended OSS/IOSS (EXT-1T, EXT-2T, EXT-3T, EXT-4T)",
        "Ad-hoc (AD-HOC)",
        "Event-driven (EVENT-N where N is an integer)",
    )


def _format_accepted_period_set() -> str:
    """Format the accepted period set for error messages."""
    standard = sorted(_STANDARD_PERIOD_SET)
    extended = sorted(_EXTENDED_PERIOD_SET)
    lines = [
        f"StandardPeriodCode: {', '.join(standard)}",
        f"Extended: {', '.join(extended)}",
        f"Ad-hoc: {_AD_HOC_PERIOD}",
        "Event-driven: EVENT-N (where N is an integer)",
    ]
    return "; ".join(lines)


RegistryPeriodCode = Annotated[str, BeforeValidator(_validate_period_against_registry)]


class PeriodError(AeatError, ValueError):
    """Raised when a :class:`Period` is constructed from an invalid year/code.

    Subclasses :class:`ValueError` so pydantic validation and existing callers
    retain value-error compatibility while still routing through the registered
    :class:`AeatError` hierarchy required for production exceptions.
    """


class PeriodKind(StrEnum):
    """Cadence class of a filing period, derived from its registry code."""

    QUARTERLY = "quarterly"
    MONTHLY = "monthly"
    ANNUAL = "annual"
    INSTALMENT = "instalment"
    EXTENDED = "extended"


# Inclusive (start_month, end_month) for each quarterly token.
_QUARTER_SPAN_MONTHS: dict[str, tuple[int, int]] = {
    "1T": (1, 3),
    "2T": (4, 6),
    "3T": (7, 9),
    "4T": (10, 12),
}


class Period(BaseModel):
    """A filing period as one typed value: a year paired with a registry code.

    ``Period`` is the canonical, fundamental representation of "which filing
    period" across the whole application. It composes exactly two authoritative
    fields — the :attr:`filing_year` and the registry period :attr:`code`
    (a :class:`StandardPeriodCode` member such as ``1T`` / ``0A`` / ``03``, or an
    extended union member such as ``EXT-1T`` / ``AD-HOC`` / ``EVENT-3``) — and
    never a combined calendar string (``2026Q1`` / ``2026-03`` / ``2026``). The
    combined form exists only as the human-readable :meth:`__str__` projection;
    it is an output, never a parseable input. Inbound construction is always from
    a ``(year, code)`` pair via :meth:`from_year_and_code`.

    The model is frozen and hashes by ``(filing_year, code)``, so a ``Period`` is
    a drop-in dict key, set member, and equality target wherever a typed period
    is required.
    """

    model_config = ConfigDict(frozen=True)

    filing_year: int = Field(ge=1980, le=2200)
    code: RegistryPeriodCode

    @classmethod
    def from_year_and_code(cls, year: int, code: str) -> Period:
        """Build a :class:`Period` from a filing year and a bare registry code.

        Args:
            year: The filing year (e.g. ``2026``).
            code: A bare registry period code — a :class:`StandardPeriodCode`
                value (``1T``-``4T`` / ``1P``-``4P`` / ``0A`` / ``01``-``12``) or
                an extended union member (``EXT-1T``-``EXT-4T`` / ``AD-HOC`` /
                ``EVENT-N``). The code is validated against the registry union;
                a combined calendar string is refused.

        Raises:
            PeriodError: When ``code`` is not an accepted registry period code or
                ``year`` is outside the supported range.
        """
        try:
            return cls(filing_year=year, code=code)
        except ValueError as exc:
            raise PeriodError(f"cannot build a period from year={year!r} code={code!r}: {exc}") from exc

    @classmethod
    def from_string(cls, value: str) -> Period:
        """Parse the canonical display string emitted by :meth:`__str__` into a :class:`Period`.

        Only the separated ``"YYYY <registry-code>"`` display form is accepted.
        Combined calendar strings such as ``"2026Q1"`` or ``"2026-1T"`` are
        refused.
        """
        if not isinstance(value, str):
            raise PeriodError(f"period string must be str, got {type(value).__name__}")
        match = _DISPLAY_PERIOD_RE.fullmatch(value.strip())
        if match is None:
            raise PeriodError(f"invalid period display string {value!r}: expected 'YYYY <period-code>'")
        return cls.from_year_and_code(int(match.group("year")), match.group("code"))

    @property
    def year(self) -> int:
        """Return the filing year (alias of :attr:`filing_year`)."""
        return self.filing_year

    @property
    def registry_token(self) -> str:
        """Return the bare registry period code as a string (e.g. ``"1T"``)."""
        return str(self.code)

    @property
    def standard_code(self) -> StandardPeriodCode | None:
        """Return the :class:`StandardPeriodCode` member, or ``None`` for extended forms."""
        try:
            return StandardPeriodCode(str(self.code))
        except ValueError:
            return None

    @property
    def kind(self) -> PeriodKind:
        """Return the cadence class derived from the period code."""
        code = str(self.code)
        if code in _QUARTER_SPAN_MONTHS:
            return PeriodKind.QUARTERLY
        if code == "0A":
            return PeriodKind.ANNUAL
        if len(code) == 2 and code.isdigit():
            return PeriodKind.MONTHLY
        if len(code) == 2 and code.endswith("P") and code[0] in "1234":
            return PeriodKind.INSTALMENT
        return PeriodKind.EXTENDED

    def has_date_span(self) -> bool:
        """Return whether the period maps to an inclusive calendar date span.

        Quarterly, monthly, and annual periods cover a contiguous span of
        calendar dates. Instalment claves (``1P``-``4P``) and the extended union
        members are filing/payment events, not calendar spans, so they return
        ``False`` and :attr:`start_date` / :attr:`end_date` refuse for them.
        """
        return self.kind in (PeriodKind.QUARTERLY, PeriodKind.MONTHLY, PeriodKind.ANNUAL)

    @property
    def start_date(self) -> date:
        """Return the inclusive first calendar date of the period.

        Raises:
            PeriodError: When the period has no calendar span
                (:meth:`has_date_span` is ``False``).
        """
        code = str(self.code)
        if code in _QUARTER_SPAN_MONTHS:
            return date(self.filing_year, _QUARTER_SPAN_MONTHS[code][0], 1)
        if code == "0A":
            return date(self.filing_year, 1, 1)
        if self.kind is PeriodKind.MONTHLY:
            return date(self.filing_year, int(code), 1)
        raise PeriodError(f"period {self!s} has no calendar date span; guard with has_date_span()")

    @property
    def end_date(self) -> date:
        """Return the inclusive last calendar date of the period.

        Raises:
            PeriodError: When the period has no calendar span
                (:meth:`has_date_span` is ``False``).
        """
        code = str(self.code)
        if code in _QUARTER_SPAN_MONTHS:
            end_month = _QUARTER_SPAN_MONTHS[code][1]
            return date(self.filing_year, end_month, calendar.monthrange(self.filing_year, end_month)[1])
        if code == "0A":
            return date(self.filing_year, 12, 31)
        if self.kind is PeriodKind.MONTHLY:
            month = int(code)
            return date(self.filing_year, month, calendar.monthrange(self.filing_year, month)[1])
        raise PeriodError(f"period {self!s} has no calendar date span; guard with has_date_span()")

    def contains(self, value: date) -> bool:
        """Return whether ``value`` falls within this period's inclusive span.

        Raises:
            PeriodError: When the period has no calendar span.
        """
        return self.start_date <= value <= self.end_date

    @override
    def __str__(self) -> str:
        """Return the canonical display form: the year and code, space-separated.

        This is the operator ``--year YYYY --period <token>`` shape rendered as
        ``"2026 1T"`` — deliberately NOT the combined ``2026Q1`` form the
        standardisation removed, so the display can never be mistaken for, or
        round-tripped as, a parseable combined token.
        """
        return f"{self.filing_year} {self.code}"

    @override
    def __repr__(self) -> str:
        return f"Period(filing_year={self.filing_year}, code={str(self.code)!r})"

    @override
    def __hash__(self) -> int:
        return hash((self.filing_year, str(self.code)))


__all__ = [
    "Period",
    "PeriodError",
    "PeriodKind",
    "RegistryPeriodCode",
    "StandardPeriodCode",
    "accepted_period_codes",
    "accepted_period_patterns",
]
