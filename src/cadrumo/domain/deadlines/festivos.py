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

from collections.abc import Iterable
from datetime import date, timedelta
from enum import StrEnum
from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints

from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ..calculations.registry.facts.resolution import EventFactQuery, ResolvedEventFact
from ..calculations.registry.schema_base import DateAxis
from .errors import DeadlineValidationError

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


def load_holiday_calendar(year: int) -> HolidayCalendar:
    """Return the published calendar from the installed authority artifact.

    A calendar is usable only when the signed artifact carries its publication
    event.  Runtime never parses an authoring TOML tree or treats an absent file
    as a holiday-free year.
    """
    from ..calculations.registry.authority import bundled_authority

    return holiday_calendar_from_authority(year, authority=bundled_authority())


@lru_cache(maxsize=64)
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
    "HOLIDAY_CALENDAR_PUBLICATION_EVENT_FACT_ID",
    "HOLIDAY_EVENT_FACT_ID",
    "MODELOS_WITHOUT_SHIFT",
    "CalendarCCAA",
    "DeadlineShift",
    "Holiday",
    "HolidayCalendar",
    "HolidayJurisdiction",
    "holiday_calendar_from_authority",
    "is_business_day",
    "load_holiday_calendar",
    "next_business_day",
    "shift_deadline",
)
