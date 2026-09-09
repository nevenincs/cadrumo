"""Spanish business-day calendar and AEAT deadline shift.

This module is the holiday-adjustment service. It loads BOE-
published national plus autonomous-community ("CCAA") holiday
calendars from the project's
``registry/aeat/calendars/`` directory and exposes pure functions that
answer two questions:

* Is a given date a *día hábil* (business day) for AEAT filings in the
  taxpayer's CCAA of tax residence?
* Given an AEAT-registered close date, what is the legally-due filing
  deadline once weekends, national holidays, and CCAA holidays are
  considered, and what was the reason for the shift?

AEAT's published deadline-shift rule (Calendario del Contribuyente,
*"Vencimientos en días inhábiles, sábados o festivos"*) is:

    "Si el último día del plazo coincide con un sábado, domingo o
    festivo, el plazo se entiende ampliado hasta el primer día hábil
    siguiente."

The rule covers national holidays plus the autonomous-community holiday
of the taxpayer's domicilio fiscal. Local (municipal) holidays do NOT
affect AEAT filing deadlines and are not part of this calendar.

One well-known exception: **Modelo 369** (OSS / IOSS one-stop-shop)
deadlines do NOT shift, even when the close date falls on a non-
business day, because the OSS / IOSS regime is governed by the EU
Council Directive's harmonised cutoffs and the AEAT cannot lengthen
the EU-wide window unilaterally. The exception list is encoded in
:data:`MODELOS_WITHOUT_SHIFT` so future modelo additions land as data,
not as a fork in :func:`shift_deadline`.

The substrate is pure domain logic: it never touches the CLI, never
mutates input, and never reaches outside the project for live calendar
data (calendars are git-tracked, BOE-cited TOML).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, StringConstraints, ValidationError

from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.resources.bundled_data import bundled_path
from ...core.revision_review import RevisionReviewStatus
from ...core.toml import read_toml
from ..calculations.registry.facts.schema import (
    EventFactPayload,
    FactOwnership,
    FactSelector,
    GovernedFact,
    GovernedFactFamily,
    GovernedFactVariant,
    NamedFactValue,
)
from ..calculations.registry.facts.resolution import EventFactQuery, ResolvedEventFact
from ..calculations.registry.loader_cache import toml_file_fingerprint
from ..calculations.registry.loader_fingerprints import RegistryPathFingerprints
from ..calculations.registry.schema_base import DateAxis, SourceCitation
from .errors import DeadlineValidationError

HOLIDAY_CALENDAR_PROVIDER_ID = "legal-holiday-calendars"
HOLIDAY_CALENDAR_PROVIDER_DIRECTORY = "calendars"
HOLIDAY_EVENT_FACT_ID = "deadlines.public-holiday"
HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID = "deadlines.holiday-calendar-publication"
_HOLIDAY_SHIFT_LEGAL_REF = "ley-39-2015:art-30.5"

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority

# ---------------------------------------------------------------------------
# CCAA enumeration (ISO 3166-2:ES codes).
# ---------------------------------------------------------------------------


class CalendarCCAA(StrEnum):
    """Spanish autonomous communities and the two autonomous cities, keyed by ISO 3166-2:ES code.

    AEAT filing deadlines may shift when the close date coincides with
    a holiday in the taxpayer's CCAA of tax residence (domicilio
    fiscal). The two autonomous cities of Ceuta and Melilla each
    publish their own holiday calendar and behave like a CCAA for this
    purpose.

    The codes match the ISO 3166-2:ES standard and the BOE-published
    holiday resolutions.
    """

    ANDALUCIA = "ES-AN"
    ARAGON = "ES-AR"
    ASTURIAS = "ES-AS"
    ILLES_BALEARS = "ES-IB"
    CANARIAS = "ES-CN"
    CANTABRIA = "ES-CB"
    CASTILLA_LA_MANCHA = "ES-CM"
    CASTILLA_Y_LEON = "ES-CL"
    CATALUNA = "ES-CT"
    EXTREMADURA = "ES-EX"
    GALICIA = "ES-GA"
    LA_RIOJA = "ES-RI"
    MADRID = "ES-MD"
    MURCIA = "ES-MC"
    NAVARRA = "ES-NC"
    PAIS_VASCO = "ES-PV"
    VALENCIA = "ES-VC"
    CEUTA = "ES-CE"
    MELILLA = "ES-ML"


class HolidayJurisdiction(StrEnum):
    """Layer of government that declared the holiday.

    * ``NATIONAL`` — declared by the State; observed everywhere.
    * ``CCAA`` — declared by an autonomous community; observed only in
      that CCAA's territory.

    AEAT does not consider municipal-level holidays for filing-deadline
    shifts, so a corresponding ``LOCAL`` value would be out of scope.
    """

    NATIONAL = "national"
    CCAA = "ccaa"


# ---------------------------------------------------------------------------
# Holiday + Calendar value types.
# ---------------------------------------------------------------------------


_NonEmptyShortString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class Holiday(BaseModel):
    """A single declared holiday."""

    model_config = STRICT_FROZEN_CONFIG

    holiday_date: date
    jurisdiction: HolidayJurisdiction
    ccaa_code: CalendarCCAA | None = None
    name: _NonEmptyShortString


class HolidayCalendar(BaseModel):
    """A year's BOE-published holiday calendar.

    ``boe_ref`` is the citation stem of the BOE Resolución that
    published the annual relación de fiestas laborales. ``boe_url`` is
    an optional convenience anchor for the same resolution.
    """

    model_config = STRICT_FROZEN_CONFIG

    year: Annotated[int, Field(ge=2000, le=2100)]
    boe_ref: _NonEmptyShortString
    boe_url: str | None = None
    national: tuple[Holiday, ...] = Field(default_factory=tuple)
    ccaa: tuple[Holiday, ...] = Field(default_factory=tuple)


#: The authoring-boundary config for the festivos TOML rows below.
#:
#: Frozen and closed like every other model here, but NOT strict, because these
#: three rows are the hydration boundary: registry TOML is authored free-form
#: and this is where its scalars become typed. A ``ccaa_code`` arrives from the
#: parser as the string ``"ES-MD"``, and strict mode refuses to make it a
#: :class:`CalendarCCAA` -- so the model that exists to coerce was refusing to.
#:
#: It failed closed and then failed quiet. Every bundled calendar raised on load,
#: :func:`shift_deadline` raised for every input, and its one caller catches that
#: error and falls back to the unshifted date with a DEBUG log. The AEAT
#: business-day rule was inert for every year shipped, and nothing said so.
#:
#: :class:`Holiday` and :class:`HolidayCalendar` -- the records these rows are
#: projected onto -- stay strict, which is where strictness belongs.
_TOML_ROW_CONFIG: ConfigDict = ConfigDict(frozen=True, extra="forbid", validate_default=True)


class _NationalHolidayRow(BaseModel):
    """One ``[[national]]`` row as authored in a festivos TOML file."""

    model_config = _TOML_ROW_CONFIG

    date: date
    name: _NonEmptyShortString


class _CcaaHolidayRow(BaseModel):
    """One ``[[ccaa]]`` row as authored in a festivos TOML file."""

    model_config = _TOML_ROW_CONFIG

    date: date
    ccaa_code: CalendarCCAA
    name: _NonEmptyShortString


class _HolidayCalendarToml(BaseModel):
    """Typed shape of a parsed ``festivos-{year}.toml`` document.

    Validating the loosely-typed :func:`read_toml` result through this
    boundary model lifts the TOML rows into typed records (coercing the
    native TOML scalars into the ``date`` and :class:`CalendarCCAA` field
    types) before they are projected onto the immutable :class:`Holiday`
    / :class:`HolidayCalendar` domain records, which stay strict.
    """

    model_config = _TOML_ROW_CONFIG

    year: Annotated[int, Field(ge=2000, le=2100)]
    boe_ref: _NonEmptyShortString
    boe_url: str | None = None
    national: list[_NationalHolidayRow] = Field(default_factory=list)
    ccaa: list[_CcaaHolidayRow] = Field(default_factory=list)


class DeadlineShift(BaseModel):
    """Outcome of applying the AEAT deadline-shift rule to one close date.

    Carries the original AEAT-registered close date, the legally-adjusted
    close date after weekend / holiday shifts, a structured reason, and
    references to the holiday source(s) that drove the shift.

    ``shifted`` is the boolean predicate "did the close date move?";
    ``shift_days`` is the (always non-negative) day count between
    original and adjusted; ``shift_reason`` is a stable identifier
    consumers may use for output-formatting and rule-explanation; the
    optional ``holiday_refs`` and ``jurisdictions`` tuples carry the
    specific holidays whose presence on the calendar caused the shift.
    """

    model_config = STRICT_FROZEN_CONFIG

    original_close_date: date
    adjusted_close_date: date
    shifted: bool
    shift_days: NonNegativeInt
    shift_reason: _NonEmptyShortString
    jurisdictions: tuple[HolidayJurisdiction, ...] = Field(default_factory=tuple)
    holiday_refs: tuple[str, ...] = Field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Modelo-specific exception list.
# ---------------------------------------------------------------------------


#: Modelos whose deadlines are NOT shifted by the AEAT día-inhábil rule.
#:
#: Per the AEAT Calendario del Contribuyente, the OSS / IOSS one-stop-shop
#: regime (Modelo 369) is governed by the EU-harmonised cutoff date and
#: AEAT cannot extend the window unilaterally even when the close date
#: falls on a Spanish holiday or weekend. Adding new modelos to this
#: tuple keeps the exception list data-driven; :func:`shift_deadline`
#: never grows a switch statement.
MODELOS_WITHOUT_SHIFT: tuple[str, ...] = (Modelo.M369,)


# ---------------------------------------------------------------------------
# Calendar loader.
# ---------------------------------------------------------------------------


_CALENDARS_DIR = bundled_path("registry", "aeat", "calendars")


def _calendar_path(year: int) -> Path:
    return _CALENDARS_DIR / f"festivos-{year}.toml"


@lru_cache(maxsize=64)
def load_holiday_calendar(year: int) -> HolidayCalendar:
    """Load the BOE-published holiday calendar for ``year``.

    Reads ``registry/aeat/calendars/festivos-{year}.toml``, parses it
    into immutable :class:`Holiday` records under the
    :class:`HolidayCalendar` aggregate, and caches the result. The
    cache is unbounded by use but bounded by call site (lru_cache with
    ``maxsize=64``).

    Raises :class:`DeadlineValidationError` when the TOML file is
    missing or malformed (caller-recoverable; the surrounding deadline
    engine can degrade to weekend-only shifts).
    """
    return _load_holiday_calendar_path(year, _calendar_path(year).resolve())


@lru_cache(maxsize=64)
def _load_holiday_calendar_path(year: int, path: Path) -> HolidayCalendar:
    """Load one exact calendar path for legacy and provider callers."""
    if not path.exists():
        raise DeadlineValidationError(f"holiday calendar for year {year} not registered (expected file: {path.name})")
    raw = read_toml(path, error_factory=DeadlineValidationError)

    declared_year = raw.get("year")
    if declared_year != year:
        raise DeadlineValidationError(
            f"holiday calendar year mismatch: filename declares {year} but TOML declares {declared_year!r}",
        )

    try:
        parsed = _HolidayCalendarToml.model_validate(raw)
        national_entries = tuple(
            Holiday(
                holiday_date=entry.date,
                jurisdiction=HolidayJurisdiction.NATIONAL,
                ccaa_code=None,
                name=entry.name,
            )
            for entry in parsed.national
        )
        ccaa_entries = tuple(
            Holiday(
                holiday_date=entry.date,
                jurisdiction=HolidayJurisdiction.CCAA,
                ccaa_code=entry.ccaa_code,
                name=entry.name,
            )
            for entry in parsed.ccaa
        )
        return HolidayCalendar(
            year=year,
            boe_ref=parsed.boe_ref,
            boe_url=parsed.boe_url,
            national=national_entries,
            ccaa=ccaa_entries,
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise DeadlineValidationError(f"{path}: invalid holiday calendar row: {exc}") from exc


def compile_holiday_calendar_facts(registry_root: Path) -> tuple[GovernedFact, ...]:
    """Project BOE-identified calendars while excluding ungrounded bootstrap years."""
    calendar_root = registry_root.resolve() / HOLIDAY_CALENDAR_PROVIDER_DIRECTORY
    holiday_variants: list[GovernedFactVariant] = []
    publication_variants: list[GovernedFactVariant] = []
    for path in sorted(calendar_root.glob("festivos-*.toml"), key=lambda candidate: candidate.name):
        year_token = path.stem.removeprefix("festivos-")
        if not year_token.isdigit():
            continue
        calendar = _load_holiday_calendar_path(int(year_token), path.resolve())
        if calendar.boe_url is None:
            continue
        publication_variants.append(_holiday_calendar_publication_variant(calendar))
        holiday_variants.extend(_holiday_fact_variant(calendar, holiday) for holiday in (*calendar.national, *calendar.ccaa))
    if not publication_variants:
        return ()
    facts = [
        GovernedFact(
            fact_id=HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
            family=GovernedFactFamily.EVENT,
            variants=tuple(publication_variants),
        ),
    ]
    if holiday_variants:
        facts.append(
            GovernedFact(
                fact_id=HOLIDAY_EVENT_FACT_ID,
                family=GovernedFactFamily.EVENT,
                variants=tuple(holiday_variants),
            )
        )
    return tuple(facts)


def _holiday_calendar_publication_variant(calendar: HolidayCalendar) -> GovernedFactVariant:
    """State that an entire calendar year, including clear dates, is published."""
    source_ref = f"aeat-calendario-contribuyente-{calendar.year}"
    return GovernedFactVariant(
        variant_id=f"holiday-calendar-publication:{calendar.year}",
        date_axis=DateAxis.SUBMISSION_DATE,
        valid_from=date(calendar.year, 1, 1),
        valid_to=date(calendar.year, 12, 31),
        payload=EventFactPayload(
            event_date=date(calendar.year, 1, 1),
            event_code="holiday_calendar_published",
            outputs=(
                NamedFactValue(name="boe_ref", value=calendar.boe_ref),
                NamedFactValue(name="boe_url", value=calendar.boe_url or ""),
            ),
        ),
        legal_refs=(_HOLIDAY_SHIFT_LEGAL_REF,),
        source_refs=(source_ref,),
        source_citations=(SourceCitation(source_ref=source_ref, required_text=("Calendario del contribuyente",)),),
        review_status=RevisionReviewStatus.PENDING_REVIEW,
        ownership=FactOwnership.GENERATED,
    )


def holiday_calendar_from_authority(
    year: int,
    *,
    authority: ValidatedRegistryAuthority,
) -> HolidayCalendar:
    """Resolve one complete published calendar from the governed-fact authority.

    The publication event is resolved first.  It is the positive proof that an
    absent per-date holiday event means an ordinary business day rather than an
    unpublished calendar year.  All individual holiday values are then read
    through exact event queries, retaining the authority's provenance.
    """
    coordinate = date(year, 7, 1)
    publication = authority.resolve_governed_fact(
        EventFactQuery(
            fact_id=HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
            date_axis=DateAxis.SUBMISSION_DATE,
            effective_date=coordinate,
        )
    )
    if not isinstance(publication, ResolvedEventFact):
        raise DeadlineValidationError("holiday calendar publication must resolve to an event fact")
    publication_outputs = {output.name: output.value for output in publication.payload.outputs}
    boe_ref = publication_outputs.get("boe_ref")
    boe_url = publication_outputs.get("boe_url")
    if not isinstance(boe_ref, str) or not boe_ref:
        raise DeadlineValidationError(f"holiday calendar publication for {year} has no BOE reference")
    if not isinstance(boe_url, str) or not boe_url:
        raise DeadlineValidationError(f"holiday calendar publication for {year} has no BOE URL")

    fact = authority.catalogues.facts.facts.get(HOLIDAY_EVENT_FACT_ID)
    if fact is None:
        raise DeadlineValidationError(f"published holiday calendar for {year} has no holiday event fact")
    national: list[Holiday] = []
    ccaa: list[Holiday] = []
    for variant in fact.variants:
        if variant.valid_from.year != year:
            continue
        resolved = authority.resolve_governed_fact(
            EventFactQuery(
                fact_id=HOLIDAY_EVENT_FACT_ID,
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=variant.valid_from,
                selectors=variant.selectors,
            )
        )
        if not isinstance(resolved, ResolvedEventFact):
            raise DeadlineValidationError("holiday event must resolve to an event fact")
        outputs = {output.name: output.value for output in resolved.payload.outputs}
        name = outputs.get("name")
        selectors = {selector.name: selector.value for selector in resolved.matched_selectors}
        jurisdiction_value = selectors.get("jurisdiction")
        if not isinstance(name, str) or not isinstance(jurisdiction_value, str):
            raise DeadlineValidationError(f"holiday event for {year} is incomplete")
        jurisdiction = HolidayJurisdiction(jurisdiction_value)
        ccaa_value = selectors.get("ccaa_code")
        holiday = Holiday(
            holiday_date=resolved.payload.event_date,
            jurisdiction=jurisdiction,
            ccaa_code=CalendarCCAA(ccaa_value) if isinstance(ccaa_value, str) else None,
            name=name,
        )
        if jurisdiction is HolidayJurisdiction.NATIONAL:
            national.append(holiday)
        else:
            ccaa.append(holiday)
    return HolidayCalendar(year=year, boe_ref=boe_ref, boe_url=boe_url, national=tuple(national), ccaa=tuple(ccaa))
def collect_holiday_calendar_fact_fingerprints(registry_root: Path) -> RegistryPathFingerprints:
    """Fingerprint every calendar, including excluded bootstrap declarations."""
    calendar_root = registry_root.resolve() / HOLIDAY_CALENDAR_PROVIDER_DIRECTORY
    return tuple(toml_file_fingerprint(path.resolve()) for path in sorted(calendar_root.glob("*.toml")))


def reset_holiday_calendar_fact_provider() -> None:
    """Clear both public and provider calendar caches on authority reset."""
    load_holiday_calendar.cache_clear()
    _load_holiday_calendar_path.cache_clear()


def _holiday_fact_variant(calendar: HolidayCalendar, holiday: Holiday) -> GovernedFactVariant:
    selectors = [FactSelector(name="jurisdiction", value=holiday.jurisdiction.value)]
    if holiday.ccaa_code is not None:
        selectors.append(FactSelector(name="ccaa_code", value=holiday.ccaa_code.value))
    source_ref = f"aeat-calendario-contribuyente-{calendar.year}"
    return GovernedFactVariant(
        variant_id=(
            f"{holiday.holiday_date.isoformat()}:{holiday.jurisdiction.value}:"
            f"{holiday.ccaa_code.value.lower() if holiday.ccaa_code is not None else 'es'}"
        ),
        selectors=tuple(selectors),
        date_axis=DateAxis.SUBMISSION_DATE,
        valid_from=holiday.holiday_date,
        valid_to=holiday.holiday_date,
        payload=EventFactPayload(
            event_date=holiday.holiday_date,
            event_code="public_holiday",
            outputs=(
                NamedFactValue(name="name", value=holiday.name),
                NamedFactValue(name="boe_ref", value=calendar.boe_ref),
                NamedFactValue(name="boe_url", value=calendar.boe_url or ""),
            ),
        ),
        legal_refs=(_HOLIDAY_SHIFT_LEGAL_REF,),
        source_refs=(source_ref,),
        source_citations=(SourceCitation(source_ref=source_ref, required_text=("Calendario del contribuyente",)),),
        review_status=RevisionReviewStatus.PENDING_REVIEW,
        ownership=FactOwnership.GENERATED,
    )


# ---------------------------------------------------------------------------
# Pure business-day arithmetic.
# ---------------------------------------------------------------------------


_WEEKEND = {5, 6}  # Saturday, Sunday — Python's date.weekday()


def _holidays_on(
    candidate: date,
    *,
    calendar: HolidayCalendar,
    ccaa_code: CalendarCCAA | None,
) -> tuple[Holiday, ...]:
    """Return every holiday that matches ``candidate`` for the supplied CCAA.

    National holidays are always included regardless of CCAA.
    """
    matches: list[Holiday] = []
    for holiday in calendar.national:
        if holiday.holiday_date == candidate:
            matches.append(holiday)
    if ccaa_code is not None:
        for holiday in calendar.ccaa:
            if holiday.holiday_date == candidate and holiday.ccaa_code is ccaa_code:
                matches.append(holiday)
    return tuple(matches)


def is_business_day(
    candidate: date,
    *,
    calendar: HolidayCalendar,
    ccaa_code: CalendarCCAA | None,
) -> bool:
    """Return True when ``candidate`` is a business day for AEAT filings.

    A date is a business day when it is not a Saturday, not a Sunday,
    not a national holiday for that year, and (when ``ccaa_code`` is
    supplied) not a CCAA holiday for that ccaa-year pair. When
    ``ccaa_code`` is ``None`` the predicate degrades to national-only:
    callers with no tax-residence information get weekend + national
    detection but miss CCAA shifts.
    """
    if candidate.weekday() in _WEEKEND:
        return False
    return not _holidays_on(candidate, calendar=calendar, ccaa_code=ccaa_code)


def next_business_day(
    start: date,
    *,
    calendar: HolidayCalendar,
    ccaa_code: CalendarCCAA | None,
) -> date:
    """Return the first date on or after ``start`` that is a business day.

    The walk is bounded by 14 days (a fortnight) to keep the function
    safe against pathological inputs; in practice the AEAT calendar
    never strings more than four non-business days together (e.g.
    Semana Santa weekend + Jueves Santo + Viernes Santo + Lunes de
    Pascua = 4 days).
    """
    candidate = start
    for _ in range(14):
        if is_business_day(candidate, calendar=calendar, ccaa_code=ccaa_code):
            return candidate
        candidate = candidate + timedelta(days=1)
    raise DeadlineValidationError(
        f"could not find a business day within 14 days of {start.isoformat()} "
        f"(ccaa={ccaa_code.value if ccaa_code else 'none'}); the calendar may "
        f"have invalid contiguous holidays",
    )


# ---------------------------------------------------------------------------
# Shift computation.
# ---------------------------------------------------------------------------


def _reason_for(
    candidate: date,
    *,
    holidays: Iterable[Holiday],
) -> tuple[str, tuple[HolidayJurisdiction, ...], tuple[str, ...]]:
    """Build the structured shift reason for one non-business day."""
    if candidate.weekday() == 5:
        weekend_token = "sabado"
    elif candidate.weekday() == 6:
        weekend_token = "domingo"
    else:
        weekend_token = ""

    holiday_tuple = tuple(holidays)
    holiday_names = tuple(h.name for h in holiday_tuple)
    jurisdictions = tuple(h.jurisdiction for h in holiday_tuple)

    if weekend_token and holiday_tuple:
        # e.g., a Saturday that is also a national holiday.
        reason = f"{weekend_token} + " + " + ".join(holiday_names)
    elif weekend_token:
        reason = weekend_token
    elif holiday_tuple:
        reason = " + ".join(holiday_names)
    else:
        reason = "business_day"

    return reason, jurisdictions, holiday_names


def shift_deadline(
    original_close_date: date,
    *,
    modelo: str,
    ccaa_code: CalendarCCAA | None,
    calendar: HolidayCalendar | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> DeadlineShift:
    """Apply the AEAT deadline-shift rule and return a :class:`DeadlineShift` result.

    The rule moves the deadline to the next business day when the
    original close date is a Saturday, Sunday, national holiday, or
    CCAA holiday of the taxpayer's tax residence.

    Modelo-specific exceptions (e.g., Modelo 369 OSS / IOSS) bypass
    the shift and return an unshifted :class:`DeadlineShift` with reason
    ``modelo_exception``.

    When ``calendar`` is omitted, ``authority`` is required and resolves a
    BOE-published calendar through the governed publication and holiday event
    facts.  A missing publication fact fails closed; it is never treated as a
    holiday-free calendar.  Callers that already hold a calendar may pass it
    directly.
    """
    if not modelo:
        raise DeadlineValidationError("modelo must be a non-empty string")

    if modelo in MODELOS_WITHOUT_SHIFT:
        return DeadlineShift(
            original_close_date=original_close_date,
            adjusted_close_date=original_close_date,
            shifted=False,
            shift_days=0,
            shift_reason="modelo_exception",
            jurisdictions=(),
            holiday_refs=(),
        )

    if calendar is not None:
        target_calendar = calendar
    elif authority is not None:
        target_calendar = holiday_calendar_from_authority(original_close_date.year, authority=authority)
    else:
        raise DeadlineValidationError("holiday authority is required when no calendar is supplied")

    # Determine whether the original date is a business day.
    holidays_on_close = _holidays_on(
        original_close_date,
        calendar=target_calendar,
        ccaa_code=ccaa_code,
    )
    is_weekend = original_close_date.weekday() in _WEEKEND

    if not is_weekend and not holidays_on_close:
        return DeadlineShift(
            original_close_date=original_close_date,
            adjusted_close_date=original_close_date,
            shifted=False,
            shift_days=0,
            shift_reason="business_day",
            jurisdictions=(),
            holiday_refs=(),
        )

    # Build the structured reason for the original date being inhábil.
    reason, jurisdictions, holiday_names = _reason_for(
        original_close_date,
        holidays=holidays_on_close,
    )

    # Walk forward to the next business day.
    adjusted = next_business_day(
        original_close_date + timedelta(days=1),
        calendar=target_calendar,
        ccaa_code=ccaa_code,
    )

    return DeadlineShift(
        original_close_date=original_close_date,
        adjusted_close_date=adjusted,
        shifted=True,
        shift_days=(adjusted - original_close_date).days,
        shift_reason=reason,
        jurisdictions=jurisdictions,
        holiday_refs=holiday_names,
    )


__all__ = (
    "HOLIDAY_CALENDAR_PROVIDER_DIRECTORY",
    "HOLIDAY_CALENDAR_PROVIDER_ID",
    "HOLIDAY_EVENT_FACT_ID",
    "HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID",
    "MODELOS_WITHOUT_SHIFT",
    "CalendarCCAA",
    "DeadlineShift",
    "Holiday",
    "HolidayCalendar",
    "HolidayJurisdiction",
    "collect_holiday_calendar_fact_fingerprints",
    "compile_holiday_calendar_facts",
    "holiday_calendar_from_authority",
    "is_business_day",
    "load_holiday_calendar",
    "next_business_day",
    "reset_holiday_calendar_fact_provider",
    "shift_deadline",
)
