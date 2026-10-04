"""Spanish business-day calendar and AEAT deadline shift.

This module is the holiday-adjustment service. It loads BOE-
published national plus autonomous-community ("CCAA") holiday
calendars from governed event facts in the validated authority and exposes
pure functions that answer two questions:

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
mutates input, and resolves only governed, BOE-cited event facts from the
validated registry authority.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from enum import StrEnum
from threading import RLock
from typing import TYPE_CHECKING, Annotated, Self

from pydantic import BaseModel, Field, GetCoreSchemaHandler, NonNegativeInt, StringConstraints
from pydantic_core import CoreSchema, core_schema

from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.registry_token import RegistryToken
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import EventFactQuery, ResolvedEventFact
from ..calculations.registry.schema_base import DateAxis
from ..calculations.registry.schema_references import TemporalProjectionDirection
from .errors import DeadlineValidationError

HOLIDAY_EVENT_FACT_ID = "deadlines.public-holiday"
HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID = "deadlines.holiday-calendar-publication"

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation
    from ..calculations.registry.calendar_ccaa_catalogue import CalendarCcaaCatalogue
    from ..calculations.registry.facts.variants import GovernedFactVariant

# ---------------------------------------------------------------------------
# CCAA enumeration (ISO 3166-2:ES codes).
# ---------------------------------------------------------------------------


class CalendarCCAA(RegistryToken):
    """Registry-projected ISO 3166-2:ES deadline-calendar territory token.

    Fact 0143 owns the nineteen territory codes used by the deadline calendar,
    including the foral communities and autonomous cities that are intentionally
    outside fact 0129's fifteen-member tax-residence vocabulary. Direct token
    construction is reserved for the typed catalogue projection; callers
    resolve membership through the same operation before constructing one.
    """

    __slots__ = ()

    _projection_source = "registry"
    _empty_value_message = "calendar CCAA code must be a non-empty string"

    @classmethod
    def _require_registry_token(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        raise ValueError("CalendarCCAA must be a registry-projected token")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Accept only a projected calendar token and serialize it as text."""
        del source_type, handler
        return core_schema.no_info_plain_validator_function(
            cls._require_registry_token,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @property
    def name(self) -> str:
        """Return the canonical ISO code for diagnostics."""
        return str(self)


class HolidayJurisdiction(StrEnum):
    """Layer of government that declared the holiday.

    * ``NATIONAL`` — declared by the State; observed everywhere.
    * ``CCAA`` — declared by an autonomous community; observed only in
      that CCAA's territory.

    Municipal holidays also extend an AEAT filing deadline (Ley 39/2015
    art. 30.6 and 30.7), but the registry carries no municipal holiday
    source, so no shift can be attributed to one; see
    :class:`DeadlineHolidayCoverage`.
    """

    NATIONAL = "national"
    CCAA = "ccaa"


class DeadlineHolidayCoverage(StrEnum):
    """Which holiday layers were checked when a close date was adjusted.

    A deadline also moves for a holiday of the taxpayer's autonomous community
    or municipality (Ley 39/2015 art. 30.6). Municipal holidays are never
    checked because the registry has no source for them, so no state claims
    complete coverage.

    * ``NATIONAL_AND_TERRITORY`` — weekends, national holidays and the
      taxpayer's autonomous-community holidays were checked.
    * ``TERRITORY_UNVERIFIED`` — the taxpayer's territory is known but its
      regional holidays for the year are not verified in the registry, so
      only weekends and national holidays were applied.
    * ``NATIONAL_ONLY`` — the taxpayer's territory is not established, so
      only weekends and national holidays were checked.
    * ``NOT_SHIFTED`` — the modelo's deadline does not move for non-working
      days, so no calendar applies.
    * ``CALENDAR_UNAVAILABLE`` — the holiday calendar could not be resolved
      and the original close date was kept unverified.
    """

    NATIONAL_AND_TERRITORY = "national_and_territory"
    TERRITORY_UNVERIFIED = "territory_unverified"
    NATIONAL_ONLY = "national_only"
    NOT_SHIFTED = "not_shifted"
    CALENDAR_UNAVAILABLE = "calendar_unavailable"


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

    ``verified_territories`` names the autonomous communities whose complete
    list of regional non-working days for the year has been checked against
    that resolution.  Regional holidays of any other territory may be partial
    or unverified, so they never extend a deadline.
    """

    model_config = STRICT_FROZEN_CONFIG

    year: Annotated[int, Field(ge=2000, le=2100)]
    boe_ref: _NonEmptyShortString
    boe_url: str | None = None
    national: tuple[Holiday, ...] = Field(default_factory=tuple)
    ccaa: tuple[Holiday, ...] = Field(default_factory=tuple)
    verified_territories: tuple[CalendarCCAA, ...] = Field(default_factory=tuple)


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
    coverage: DeadlineHolidayCoverage


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
MODELOS_WITHOUT_SHIFT: tuple[str, ...] = (Modelo("369"),)


# ---------------------------------------------------------------------------
# Calendar loader.
# ---------------------------------------------------------------------------


_HOLIDAY_CALENDAR_CACHE_SIZE = 16
_holiday_calendar_cache: OrderedDict[tuple[object, int], HolidayCalendar] = OrderedDict()
_holiday_calendar_cache_lock = RLock()


def load_holiday_calendar(
    year: int,
    *,
    operation: PinnedAuthorityOperation,
) -> HolidayCalendar:
    """Load a calendar through the caller's pinned operation.

    A calendar view shifts every deadline of a year against the same
    publication, so successful loads are reused per generation pin and year.
    A refused year is not cached and is resolved again on its next request.
    """
    key = (operation.pin(), year)
    with _holiday_calendar_cache_lock:
        cached = _holiday_calendar_cache.get(key)
        if cached is not None:
            _holiday_calendar_cache.move_to_end(key)
            return cached
    calendar = holiday_calendar_from_authority(year, operation=operation)
    with _holiday_calendar_cache_lock:
        _holiday_calendar_cache[key] = calendar
        _holiday_calendar_cache.move_to_end(key)
        while len(_holiday_calendar_cache) > _HOLIDAY_CALENDAR_CACHE_SIZE:
            _holiday_calendar_cache.popitem(last=False)
    return calendar


def holiday_calendar_from_authority(
    year: int,
    *,
    operation: PinnedAuthorityOperation,
) -> HolidayCalendar:
    """Resolve one complete published calendar from the governed-fact authority.

    The publication event is resolved first.  It is the positive proof that an
    absent per-date holiday event means an ordinary business day rather than an
    unpublished calendar year.  All individual holiday values are then read
    through exact event queries, retaining the authority's provenance.
    """
    coordinate = date(year, 7, 1)
    publication = _resolve_holiday_publication(year, coordinate, operation=operation)
    boe_ref_value, boe_url_value, verified_value = _publication_fields(publication, year=year)
    territory = _calendar_territory_resolver(operation=operation)
    verified_territories = _verified_calendar_territories(
        verified_value,
        coordinate=coordinate,
        year=year,
        territory=territory,
    )
    boe_ref = _required_publication_string(boe_ref_value, year=year, label="reference")
    boe_url = _required_publication_string(boe_url_value, year=year, label="URL")
    national, ccaa = _calendar_holidays_from_authority(year, operation=operation, territory=territory)
    return HolidayCalendar(
        year=year,
        boe_ref=boe_ref,
        boe_url=boe_url,
        national=national,
        ccaa=ccaa,
        verified_territories=verified_territories,
    )


def _resolve_holiday_publication(
    year: int,
    coordinate: date,
    *,
    operation: PinnedAuthorityOperation,
) -> ResolvedEventFact:
    selected = operation
    try:
        publication = selected.resolve_governed_fact(
            EventFactQuery(
                fact_id=HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID,
                date_axis=DateAxis.SUBMISSION_DATE,
                effective_date=coordinate,
            )
        )
    except RegistryValidationError as exc:
        raise DeadlineValidationError(f"holiday calendar publication for {year} could not be resolved") from exc
    if not isinstance(publication, ResolvedEventFact):
        raise DeadlineValidationError("holiday calendar publication must resolve to an event fact")
    # A publication carried over from another year proves nothing about this
    # one: only an authored publication makes absent holiday events business days.
    if publication.projection_direction is not TemporalProjectionDirection.AUTHORED:
        raise DeadlineValidationError(f"holiday calendar for {year} has no governed publication")
    return publication


def _publication_fields(
    publication: ResolvedEventFact,
    *,
    year: int,
) -> tuple[object, object, str]:
    publication_outputs = {output.name: output.value for output in publication.payload.outputs}
    boe_ref = publication_outputs.get("boe_ref")
    boe_url = publication_outputs.get("boe_url")
    verified_value = publication_outputs.get("verified_territories", "")
    if not isinstance(verified_value, str):
        raise DeadlineValidationError(f"holiday calendar publication for {year} has malformed verified territories")
    return boe_ref, boe_url, verified_value


def _calendar_territory_resolver(
    *,
    operation: PinnedAuthorityOperation,
) -> Callable[[str, date], CalendarCCAA]:
    from ..calculations.registry.calendar_ccaa_catalogue import resolve_calendar_ccaa_catalogue

    catalogues: dict[date, CalendarCcaaCatalogue] = {}
    selected = operation

    def territory(value: str, effective_date: date) -> CalendarCCAA:
        catalogue = catalogues.get(effective_date)
        if catalogue is None:
            catalogue = resolve_calendar_ccaa_catalogue(effective_date=effective_date, authority=selected)
            catalogues[effective_date] = catalogue
        return catalogue.require(value)

    return territory


def _verified_calendar_territories(
    verified_value: str,
    *,
    coordinate: date,
    year: int,
    territory: Callable[[str, date], CalendarCCAA],
) -> tuple[CalendarCCAA, ...]:
    verified_territories = tuple(
        territory(token.strip(), coordinate) for token in verified_value.split(",") if token.strip()
    )
    if len(set(verified_territories)) != len(verified_territories):
        raise DeadlineValidationError(f"holiday calendar publication for {year} repeats a verified territory")
    return verified_territories


def _required_publication_string(value: object, *, year: int, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DeadlineValidationError(f"holiday calendar publication for {year} has no BOE {label}")
    return value


def _calendar_holidays_from_authority(
    year: int,
    *,
    operation: PinnedAuthorityOperation,
    territory: Callable[[str, date], CalendarCCAA],
) -> tuple[tuple[Holiday, ...], tuple[Holiday, ...]]:
    fact = operation.governed_fact(HOLIDAY_EVENT_FACT_ID)
    national: list[Holiday] = []
    ccaa: list[Holiday] = []
    for variant in fact.variants:
        holiday = _holiday_from_authority_variant(variant, year=year, operation=operation, territory=territory)
        if holiday is None:
            continue
        if holiday.jurisdiction is HolidayJurisdiction.NATIONAL:
            national.append(holiday)
        else:
            ccaa.append(holiday)
    return tuple(national), tuple(ccaa)


def _holiday_from_authority_variant(
    variant: GovernedFactVariant,
    *,
    year: int,
    operation: PinnedAuthorityOperation,
    territory: Callable[[str, date], CalendarCCAA],
) -> Holiday | None:
    if variant.valid_from is None:
        raise DeadlineValidationError(f"holiday event variant {variant.variant_id!r} has no validity start")
    if variant.valid_from.year != year:
        return None
    resolved = operation.resolve_governed_fact(
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
    return Holiday(
        holiday_date=resolved.payload.event_date,
        jurisdiction=jurisdiction,
        ccaa_code=territory(ccaa_value, variant.valid_from) if isinstance(ccaa_value, str) else None,
        name=name,
    )


# ---------------------------------------------------------------------------
# Pure business-day arithmetic.
# ---------------------------------------------------------------------------


_WEEKEND = {5, 6}  # Saturday, Sunday — Python's date.weekday()


def _require_calendar_year(candidate: date, *, calendar: HolidayCalendar) -> None:
    # A calendar says nothing about another year's holidays: answering from it
    # would report 1 January of the following year as a business day.
    if candidate.year != calendar.year:
        raise DeadlineValidationError(
            f"the {calendar.year} holiday calendar cannot classify {candidate.isoformat()}",
        )


def _holidays_on(
    candidate: date,
    *,
    calendar: HolidayCalendar,
    ccaa_code: CalendarCCAA | None,
) -> tuple[Holiday, ...]:
    """Return every holiday that matches ``candidate`` for the supplied CCAA.

    National holidays are always included regardless of CCAA.
    """
    _require_calendar_year(candidate, calendar=calendar)
    matches: list[Holiday] = []
    for holiday in calendar.national:
        if holiday.holiday_date == candidate:
            matches.append(holiday)
    if ccaa_code is not None:
        for holiday in calendar.ccaa:
            if holiday.holiday_date == candidate and holiday.ccaa_code == ccaa_code:
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
    detection but miss CCAA shifts. A date outside ``calendar.year`` is
    refused rather than classified.
    """
    _require_calendar_year(candidate, calendar=calendar)
    if candidate.weekday() in _WEEKEND:
        return False
    return not _holidays_on(candidate, calendar=calendar, ccaa_code=ccaa_code)


def _first_business_day(
    start: date,
    *,
    ccaa_code: CalendarCCAA | None,
    business_day: Callable[[date], bool],
) -> date:
    candidate = start
    for _ in range(14):
        if business_day(candidate):
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


def _calendar_source(
    calendars: tuple[HolidayCalendar, ...],
    *,
    operation: PinnedAuthorityOperation,
) -> Callable[[int], HolidayCalendar]:
    """Return a per-year calendar lookup: supplied calendars first, then the authority."""
    supplied: dict[int, HolidayCalendar] = {}
    for calendar in calendars:
        if calendar.year in supplied:
            raise DeadlineValidationError(f"more than one holiday calendar was supplied for {calendar.year}")
        supplied[calendar.year] = calendar

    def calendar_for(year: int) -> HolidayCalendar:
        calendar = supplied.get(year)
        return calendar if calendar is not None else load_holiday_calendar(year, operation=operation)

    return calendar_for


def _territory_coverage(
    ccaa_code: CalendarCCAA | None,
    *,
    calendar: HolidayCalendar,
) -> tuple[DeadlineHolidayCoverage, CalendarCCAA | None]:
    """Return the coverage one year's calendar gives and the territory it may apply."""
    # A later deadline is the harmful error, so a territory's regional
    # holidays only move a date once its list for the year is verified.
    if ccaa_code is None:
        return DeadlineHolidayCoverage.NATIONAL_ONLY, None
    if ccaa_code in calendar.verified_territories:
        return DeadlineHolidayCoverage.NATIONAL_AND_TERRITORY, ccaa_code
    return DeadlineHolidayCoverage.TERRITORY_UNVERIFIED, None


def _walk_to_business_day(
    start: date,
    *,
    ccaa_code: CalendarCCAA | None,
    coverage: DeadlineHolidayCoverage,
    calendar_for: Callable[[int], HolidayCalendar],
) -> tuple[date, DeadlineHolidayCoverage]:
    """Walk forward from ``start`` judging each day against its own year's calendar.

    The returned coverage is degraded when a year the walk enters does not
    verify the territory.
    """
    walked_coverage = coverage

    def business_day(candidate: date) -> bool:
        nonlocal walked_coverage
        calendar = calendar_for(candidate.year)
        year_coverage, applied_territory = _territory_coverage(ccaa_code, calendar=calendar)
        if year_coverage is DeadlineHolidayCoverage.TERRITORY_UNVERIFIED:
            walked_coverage = year_coverage
        return is_business_day(candidate, calendar=calendar, ccaa_code=applied_territory)

    adjusted = _first_business_day(start, ccaa_code=ccaa_code, business_day=business_day)
    return adjusted, walked_coverage


def shift_deadline(
    original_close_date: date,
    *,
    modelo: str,
    ccaa_code: CalendarCCAA | None,
    calendars: tuple[HolidayCalendar, ...] = (),
    operation: PinnedAuthorityOperation,
) -> DeadlineShift:
    """Apply the AEAT deadline-shift rule and return a :class:`DeadlineShift` result.

    The rule moves the deadline to the next business day when the
    original close date is a Saturday, Sunday, national holiday, or
    holiday of ``ccaa_code``, the taxpayer's autonomous community
    (Ley 39/2015 art. 30.6). ``None`` means the territory is not
    established: only national holidays are checked and the result's
    coverage says so rather than implying the date is final.

    Modelo-specific exceptions (e.g., Modelo 369 OSS / IOSS) bypass
    the shift and return an unshifted :class:`DeadlineShift` with reason
    ``modelo_exception``.

    Each day is judged against its own year's calendar, so a walk past 31
    December sees the following year's holidays. A year absent from
    ``calendars`` is resolved through the caller's pinned ``operation`` from
    the governed publication and holiday event facts. A missing publication
    fact for any year the walk enters fails closed with
    :class:`DeadlineValidationError`; it is never treated as a holiday-free
    calendar. Coverage reports the weakest territory verification among the
    years consulted.
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
            coverage=DeadlineHolidayCoverage.NOT_SHIFTED,
        )

    calendar_for = _calendar_source(calendars, operation=operation)
    close_calendar = calendar_for(original_close_date.year)
    coverage, applied_territory = _territory_coverage(ccaa_code, calendar=close_calendar)

    # Determine whether the original date is a business day.
    holidays_on_close = _holidays_on(
        original_close_date,
        calendar=close_calendar,
        ccaa_code=applied_territory,
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
            coverage=coverage,
        )

    # Build the structured reason for the original date being inhábil.
    reason, jurisdictions, holiday_names = _reason_for(
        original_close_date,
        holidays=holidays_on_close,
    )

    adjusted, coverage = _walk_to_business_day(
        original_close_date + timedelta(days=1),
        ccaa_code=ccaa_code,
        coverage=coverage,
        calendar_for=calendar_for,
    )

    return DeadlineShift(
        original_close_date=original_close_date,
        adjusted_close_date=adjusted,
        shifted=True,
        shift_days=(adjusted - original_close_date).days,
        shift_reason=reason,
        jurisdictions=jurisdictions,
        holiday_refs=holiday_names,
        coverage=coverage,
    )


__all__ = (
    "HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID",
    "HOLIDAY_EVENT_FACT_ID",
    "MODELOS_WITHOUT_SHIFT",
    "CalendarCCAA",
    "DeadlineHolidayCoverage",
    "DeadlineShift",
    "Holiday",
    "HolidayCalendar",
    "HolidayJurisdiction",
    "holiday_calendar_from_authority",
    "is_business_day",
    "load_holiday_calendar",
    "shift_deadline",
)
