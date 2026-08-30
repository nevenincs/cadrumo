"""Canonical period code enumeration for filing periods.

Period codes represent the filing frequency and scheme for tax returns:
- Quarterly: 1T, 2T, 3T, 4T (standard filing periods)
- Instalment: 1P, 2P, 3P, 4P (corporate-tax/IS instalment periods)
- Annual: 0A
- Monthly: 01-12 (calendar months)
- OSS/IOSS: EXT-1T, EXT-2T, EXT-3T, EXT-4T (extra-Union scheme)
- Ad-hoc/Event: AD-HOC, EVENT-N (event-driven filings)

:class:`StandardPeriodCode` is the canonical :class:`~enum.StrEnum` for
the closed standard vocabulary (1T-4T, 1P-4P, 0A, 01-12). It includes both
calendar spans and instalment claves, so callers that need date boundaries
must still check :meth:`Period.has_date_span`. :data:`RegistryPeriodCode`
is the pydantic field annotation for the full registry union: standard
members plus extended OSS/IOSS literals, ``AD-HOC``, the open-ended event
shape, the administrative censo tokens, and the symbolic ``EVENT-N`` selector.
:data:`FilingPeriodCode` is the narrower annotation for a period a taxpayer
files in — the same union minus the administrative tokens and the symbolic
selector, neither of which names one concrete filing period. Two boundaries
with different value spaces need two annotations:
widening one to admit a registry coordinate must not widen the other.
:class:`Period` combines one accepted FILING code with a filing year, and
:class:`PeriodKind` classifies the resulting cadence.

This module is the runtime counterpart to the registry
:data:`domain.calculations.registry._schema_scalars.PeriodCode` alias and
:class:`domain.calculations.registry.PeriodSelector` schema. Registry
objects carry bare period tokens; application services that need a concrete
filing window compose those tokens with a year into :class:`Period`.
Operator commands follow the same separated shape (``--year YYYY --period
<AEAT-token>``); any year-qualified filter mini-grammar is converted at the
CLI boundary before it reaches this model.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from typing import Annotated, override

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter, ValidationError

from .errors.hierarchy import CadrumoError


class StandardPeriodCode(StrEnum):
    """Canonical enumeration of closed standard filing-period codes.

    Quarterly, monthly, and annual members have calendar spans. Instalment
    members (``1P``-``4P``) identify filing/payment events and intentionally do
    not imply a contiguous ledger date span.
    """

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


_STANDARD_PERIOD_SET: frozenset[str] = frozenset(member.value for member in StandardPeriodCode)
_EXTENDED_PERIOD_SET: frozenset[str] = frozenset(("EXT-1T", "EXT-2T", "EXT-3T", "EXT-4T"))
_AD_HOC_PERIOD = "AD-HOC"
_ADMINISTRATIVE_PERIOD_SET: frozenset[str] = frozenset(
    ("ALTA", "MODIFICACION", "BAJA", "COMUNICACION", "VARIACION"),
)
#: The symbolic token a registry ``period_selector`` declares to COVER the
#: concrete event periods (``EVENT-1``, ``EVENT-2``, ...) an operator scope may
#: carry — see the shared-matcher rationale in the registry's ``select_revision``.
#: It stands for a SET of periods, so it is not itself one.
_SYMBOLIC_EVENT_SELECTOR = "EVENT-N"
_EVENT_NUMBER_PERIOD_RE = re.compile(r"^EVENT-\d+$")
_DISPLAY_PERIOD_RE = re.compile(r"^(?P<year>\d{4})\s+(?P<code>[A-Z0-9]+(?:-[A-Z0-9]+)*)$", re.I)


def _normalised_period_token(value: str) -> str:
    """Return the trimmed, upper-cased token, refusing a non-string input."""
    if not isinstance(value, str):
        raise ValueError(f"period code must be a string, got {type(value).__name__}")
    return value.strip().upper()


def _validate_filing_period(value: str) -> str:
    """Validate and normalize a period code that a taxpayer can actually file.

    Accepts StandardPeriodCode members, extended OSS/IOSS forms (EXT-1T..EXT-4T),
    the ad-hoc literal (AD-HOC), and event-driven forms carrying a concrete event
    NUMBER (EVENT-3). It admits neither the administrative censo/comunicación
    tokens nor the symbolic ``EVENT-N`` selector: an administrative token names a
    registration event rather than a period, and ``EVENT-N`` is declared to COVER
    the concrete ``EVENT-1``/``EVENT-2`` scopes rather than to be one of them. A
    symbolic stand-in for a set is a type error at a boundary whose whole contract
    is "exactly one filing period", not merely an odd value.

    Raises ValueError with the filing-scoped accepted set on rejection; pydantic
    wraps it into a ValidationError at the BeforeValidator boundary.
    """
    normalized = _normalised_period_token(value)

    if normalized in _STANDARD_PERIOD_SET:
        return normalized
    if normalized in _EXTENDED_PERIOD_SET:
        return normalized
    if normalized == _AD_HOC_PERIOD:
        return normalized
    if _EVENT_NUMBER_PERIOD_RE.match(normalized):
        return normalized

    accepted = _format_accepted_filing_period_set()
    raise ValueError(f"invalid period code '{value}'; accepted forms: {accepted}")


def _validate_period_against_registry(value: str) -> str:
    """Validate and normalize a period code against the union of accepted forms.

    This is the REGISTRY coordinate's vocabulary: every filing period plus the
    two sub-vocabularies that address a revision without naming a filing period —
    the administrative censo/comunicación tokens (Modelo 036, Modelo 145) and the
    symbolic ``EVENT-N`` selector (Modelo 210). Use :func:`_validate_filing_period`
    for anything that represents a period a taxpayer files in.

    Raises ValueError with the full accepted-set list on rejection; pydantic
    wraps it into a ValidationError at the BeforeValidator boundary.
    """
    normalized = _normalised_period_token(value)

    if normalized in _ADMINISTRATIVE_PERIOD_SET:
        return normalized
    if normalized == _SYMBOLIC_EVENT_SELECTOR:
        return normalized
    try:
        return _validate_filing_period(normalized)
    except ValueError:
        accepted = _format_accepted_period_set()
        raise ValueError(f"invalid period code '{value}'; accepted forms: {accepted}") from None


def is_administrative_period_token(token: str) -> bool:
    """Return whether ``token`` is one of the administrative censo period codes.

    The administrative sub-vocabulary (Modelo 036's ``ALTA`` / ``MODIFICACION`` /
    ``BAJA``, Modelo 145's ``COMUNICACION`` / ``VARIACION``) addresses a registry
    revision rather than naming a period, so a caller holding a raw registry token
    generally needs to route it somewhere other than :class:`Period`. This is the
    one public way to ask, so the membership test cannot be hand-copied into a
    second, drifting set.

    Matching is on the registry's own unaccented spelling. A caller reading a
    token off an AEAT-rendered surface — where Spanish prints ``MODIFICACIÓN``,
    ``COMUNICACIÓN``, ``VARIACIÓN`` — folds it with
    :func:`~cadrumo.core.fold_diacritics` first; admitting accented spellings here
    would put this predicate and :data:`RegistryPeriodCode` into disagreement
    about the same token.

    Raises:
        ValueError: When ``token`` is not a string.
    """
    return _normalised_period_token(token) in _ADMINISTRATIVE_PERIOD_SET


def accepted_period_codes() -> tuple[str, ...]:
    """Return the fully enumerable REGISTRY period codes.

    The tuple includes :class:`StandardPeriodCode`, extended OSS/IOSS literals,
    ``AD-HOC``, and the administrative tokens. It deliberately excludes the
    infinite ``EVENT-N`` family; pair it with :func:`accepted_period_patterns`
    when building help text or parse-error guidance.

    This is the registry-facing set. Operator surfaces describing what may be
    FILED consume :func:`accepted_filing_period_codes` instead.
    """
    return tuple(sorted(_STANDARD_PERIOD_SET | _EXTENDED_PERIOD_SET | {_AD_HOC_PERIOD} | _ADMINISTRATIVE_PERIOD_SET))


def accepted_filing_period_codes() -> tuple[str, ...]:
    """Return the fully enumerable codes a :class:`Period` accepts.

    The administrative tokens are excluded — they address a registry revision,
    not a filing period — as is the infinite ``EVENT-<number>`` family.
    """
    return tuple(sorted(_STANDARD_PERIOD_SET | _EXTENDED_PERIOD_SET | {_AD_HOC_PERIOD}))


def accepted_period_patterns() -> tuple[str, ...]:
    """Return human-readable REGISTRY period-code patterns, including open regex shapes."""
    return (
        *accepted_filing_period_patterns(),
        f"Administrative ({', '.join(sorted(_ADMINISTRATIVE_PERIOD_SET))})",
        f"Symbolic registry selector (the literal {_SYMBOLIC_EVENT_SELECTOR}, which covers the EVENT-<n> scopes)",
    )


def accepted_filing_period_patterns() -> tuple[str, ...]:
    """Return human-readable patterns for the periods a :class:`Period` accepts."""
    return (
        "StandardPeriodCode (1T-4T, 1P-4P, 0A, 01-12)",
        "Extended OSS/IOSS (EXT-1T, EXT-2T, EXT-3T, EXT-4T)",
        "Ad-hoc (AD-HOC)",
        "Event-driven (EVENT-N where N is an event-number integer, e.g. EVENT-3)",
    )


def _format_accepted_filing_period_set() -> str:
    """Format the filing-scoped accepted period set for error messages."""
    standard = sorted(_STANDARD_PERIOD_SET)
    extended = sorted(_EXTENDED_PERIOD_SET)
    lines = [
        f"StandardPeriodCode: {', '.join(standard)}",
        f"Extended: {', '.join(extended)}",
        f"Ad-hoc: {_AD_HOC_PERIOD}",
        "Event-driven: EVENT-N (where N is an event-number integer, e.g. EVENT-3)",
    ]
    return "; ".join(lines)


def _format_accepted_period_set() -> str:
    """Format the registry-scoped accepted period set for error messages."""
    lines = [
        _format_accepted_filing_period_set(),
        f"Administrative: {', '.join(sorted(_ADMINISTRATIVE_PERIOD_SET))}",
        f"Symbolic registry selector: the literal {_SYMBOLIC_EVENT_SELECTOR}",
    ]
    return "; ".join(lines)


#: Pydantic field annotation for bare registry period tokens. Use
#: :data:`FilingPeriodCode` (or :class:`Period`) instead when the value names a
#: period a taxpayer files in rather than a registry coordinate.
RegistryPeriodCode = Annotated[str, BeforeValidator(_validate_period_against_registry)]

#: Pydantic field annotation for a bare period token a taxpayer can file in.
#: Narrower than :data:`RegistryPeriodCode`: the administrative censo tokens and
#: the symbolic ``EVENT-N`` selector are refused.
FilingPeriodCode = Annotated[str, BeforeValidator(_validate_filing_period)]


def _validate_registry_selector_period(value: str) -> str:
    """Validate a registry token while preserving declaration casing for event selectors."""
    normalized = _validate_period_against_registry(value)
    if normalized in _ADMINISTRATIVE_PERIOD_SET:
        return normalized.lower()
    return normalized


RegistrySelectorPeriodCode = Annotated[str, BeforeValidator(_validate_registry_selector_period)]


class PeriodError(CadrumoError, ValueError):
    """Raised when a :class:`Period` is constructed from an invalid year/code.

    Subclasses :class:`ValueError` so pydantic validation and existing callers
    retain value-error compatibility while still routing through the registered
    :class:`CadrumoError` hierarchy required for production exceptions.
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

_QUARTER_ORDINALS: dict[StandardPeriodCode, int] = {
    StandardPeriodCode.Q1: 1,
    StandardPeriodCode.Q2: 2,
    StandardPeriodCode.Q3: 3,
    StandardPeriodCode.Q4: 4,
}


def _period_kind_for_code(code: str) -> PeriodKind:
    """Classify a normalised period code's cadence.

    The cadence is a property of the token alone — no filing year participates —
    so this is shared by :attr:`Period.kind` and :func:`registry_period_kind`
    rather than requiring a registry-facing caller to mint a throwaway
    :class:`Period` (which the administrative tokens can no longer become).
    """
    if code in _QUARTER_SPAN_MONTHS:
        return PeriodKind.QUARTERLY
    if code == "0A":
        return PeriodKind.ANNUAL
    if len(code) == 2 and code.isdigit():
        return PeriodKind.MONTHLY
    if len(code) == 2 and code.endswith("P") and code[0] in "1234":
        return PeriodKind.INSTALMENT
    return PeriodKind.EXTENDED


def registry_period_kind(token: str) -> PeriodKind:
    """Return the cadence class of any REGISTRY period token.

    Accepts the full :data:`RegistryPeriodCode` vocabulary, so a registry-facing
    consistency check (a ``filing_schedules`` declaration reconciling its
    ``period_kind`` against its ``periods``) can classify an administrative censo
    token or the symbolic ``EVENT-N`` selector. Both classify as
    :attr:`PeriodKind.EXTENDED`, matching what a :class:`Period` reported for them
    while one validator still served both boundaries.

    This lives here, rather than in the one registry validator that calls it,
    because :func:`_period_kind_for_code` is the single cadence authority
    :attr:`Period.kind` also reads. Registry ownership would force either a
    cross-package import of that private helper or a second token-to-cadence map —
    a duplicate authority for "what cadence is this token". One narrow public
    function for one narrow caller is the cheaper of the two, and it names the
    vocabulary it speaks now that two vocabularies exist.

    Raises:
        ValueError: When ``token`` is not an accepted registry period code.
    """
    normalized = _validate_period_against_registry(token)
    if normalized in _ADMINISTRATIVE_PERIOD_SET or normalized == _SYMBOLIC_EVENT_SELECTOR:
        return PeriodKind.EXTENDED
    return _period_kind_for_code(normalized)


class Period(BaseModel):
    """A filing period as one typed value: a year paired with a registry code.

    ``Period`` is the canonical, fundamental representation of "which filing
    period" across the whole application. It composes exactly two authoritative
    fields — the :attr:`filing_year` and the registry period :attr:`code`
    (a :class:`StandardPeriodCode` member such as ``1T`` / ``0A`` / ``03``, or an
    extended union member such as ``EXT-1T`` / ``AD-HOC`` / ``EVENT-3``) — and
    never a combined calendar string (``2026Q1`` / ``2026-03`` / ``2026``).
    Those calendar shapes are neither accepted inputs nor canonical outputs.
    The only display projection is the space-separated :meth:`__str__` form
    (``"2026 1T"``), and normal inbound construction is from a ``(year, code)``
    pair via :meth:`from_year_and_code`.

    The model is frozen and hashes by ``(filing_year, code)``, so a ``Period`` is
    a drop-in dict key, set member, and equality target wherever a typed period
    is required. The ledger and aggregation boundary routes through
    :func:`application.aggregation.aggregation_period_for_modelo`, then uses
    :meth:`contains` as the single date-boundary authority.

    Attributes:
        filing_year: Filing year carried separately from the registry token.
        code: Bare :data:`FilingPeriodCode` token — the registry union minus the
            coordinates that address a revision rather than a filing period.
    """

    model_config = ConfigDict(frozen=True)

    filing_year: int = Field(ge=1980, le=2200)
    """Deliberately wider than the registry's authored filing-year window.

    A period is a calendar span, not a claim that a revision exists for it. It
    must be able to EXPRESS a year the registry cannot serve -- a pre-1995
    IVA regime under Ley 41/1994, or a 1999 coordinate whose refusal is the
    behaviour under test -- so narrowing it to the filing-year axis would make
    those cases unrepresentable rather than refusable.
    """
    code: FilingPeriodCode

    @classmethod
    def from_year_and_code(cls, year: int, code: str) -> Period:
        """Build a :class:`Period` from a filing year and a bare registry code.

        Args:
            year: The filing year (e.g. ``2026``).
            code: A bare filing period code — a :class:`StandardPeriodCode`
                value (``1T``-``4T`` / ``1P``-``4P`` / ``0A`` / ``01``-``12``) or
                an extended union member (``EXT-1T``-``EXT-4T`` / ``AD-HOC`` /
                ``EVENT-3``). The code is validated against
                :data:`FilingPeriodCode`; a combined calendar string, an
                administrative censo token, and the symbolic ``EVENT-N``
                selector are all refused.

        Raises:
            PeriodError: When ``code`` is not an accepted filing period code or
                ``year`` is outside the supported range.
        """
        try:
            return cls(filing_year=year, code=code)
        except ValueError as exc:
            raise PeriodError(f"cannot build a period from year={year!r} code={code!r}: {exc}") from exc

    @classmethod
    def from_string(cls, value: str) -> Period:
        """Parse the canonical display string emitted by :meth:`__str__`.

        Only the separated ``"YYYY <registry-code>"`` display form is accepted.
        Combined calendar strings such as ``"2026Q1"`` or ``"2026-1T"`` are
        refused; this method is for display round-trips, not an alternate CLI or
        registry grammar.

        Args:
            value: Space-separated display string containing a four-digit filing
                year and a bare registry period code.

        Returns:
            A :class:`Period` parsed from the canonical display string.

        Raises:
            PeriodError: When ``value`` is not the display form or contains an
                invalid registry period code.
        """
        if not isinstance(value, str):
            raise PeriodError(f"period string must be str, got {type(value).__name__}")
        match = _DISPLAY_PERIOD_RE.fullmatch(value.strip())
        if match is None:
            raise PeriodError(f"invalid period display string {value!r}: expected 'YYYY <period-code>'")
        return cls.from_year_and_code(int(match.group("year")), match.group("code"))

    @property
    def registry_token(self) -> str:
        """Return the bare registry period code as a string (e.g. ``"1T"``).

        Use this when calling registry APIs that expect the bare
        :data:`domain.calculations.registry._schema_scalars.PeriodCode` token
        rather than a
        structured :class:`Period`.
        """
        return str(self.code)

    @property
    def standard_code(self) -> StandardPeriodCode | None:
        """Return the :class:`StandardPeriodCode` member, or ``None`` for extended forms."""
        try:
            return StandardPeriodCode(str(self.code))
        except ValueError:
            return None

    @property
    def quarter_ordinal(self) -> int | None:
        """Return the standard-quarter ordinal, or ``None`` for every non-quarter period.

        Only the ordinary ``1T`` through ``4T`` registry tokens are quarterly.
        Extended OSS/IOSS tokens such as ``EXT-1T`` retain their extended
        cadence and therefore do not acquire a quarter ordinal.
        """
        standard_code = self.standard_code
        if standard_code is None:
            return None
        return _QUARTER_ORDINALS.get(standard_code)

    @property
    def is_quarterly(self) -> bool:
        """Return whether this is one of the four ordinary quarterly periods."""
        return self.quarter_ordinal is not None

    @property
    def kind(self) -> PeriodKind:
        """Return the cadence class derived from the period code."""
        return _period_kind_for_code(str(self.code))

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


_SCENARIO_MAPPING_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(
    dict[str, object], config=ConfigDict(strict=True)
)


def _scenario_mapping(value: object) -> dict[str, object] | None:
    """Return a strictly typed scenario mapping when ``value`` is one."""
    if not isinstance(value, Mapping):
        return None
    try:
        return _SCENARIO_MAPPING_ADAPTER.validate_python(value)
    except ValidationError:
        return None


def hydrate_scenario_filing_period(data: object) -> object:
    """Derive ``filing_period`` from ``filing_year`` + ``period`` for a scenario payload.

    The pydantic ``mode="before"`` validator body shared by the registry
    scenario and parity-tape harnesses. Returns ``data`` unchanged when it is
    not a mapping, already carries ``filing_period``, lacks a well-typed
    ``filing_year``/``period`` pair, or the pair does not form a valid
    :class:`Period`.
    """
    payload = _scenario_mapping(data)
    if payload is None or "filing_period" in payload:
        return data
    filing_year = payload.get("filing_year")
    period = payload.get("period")
    if not isinstance(filing_year, int) or not isinstance(period, str):
        return data
    try:
        filing_period = Period.from_year_and_code(filing_year, period)
    except ValueError:
        return data
    return {**payload, "filing_period": filing_period}


__all__ = [
    "FilingPeriodCode",
    "Period",
    "PeriodError",
    "PeriodKind",
    "RegistryPeriodCode",
    "StandardPeriodCode",
    "accepted_filing_period_codes",
    "accepted_filing_period_patterns",
    "accepted_period_codes",
    "accepted_period_patterns",
    "hydrate_scenario_filing_period",
    "is_administrative_period_token",
    "registry_period_kind",
]
