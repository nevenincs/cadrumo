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
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from ...core import STRICT_FROZEN_CONFIG, Modelo, read_toml
from ...core.resources import bundled_path
from .errors import DeadlineValidationError

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


class _NationalHolidayRow(BaseModel):
    """One ``[[national]]`` row as authored in a festivos TOML file."""

    model_config = ConfigDict(extra="forbid")

    date: date
    name: _NonEmptyShortString


class _CcaaHolidayRow(BaseModel):
    """One ``[[ccaa]]`` row as authored in a festivos TOML file."""

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

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
    shift_days: Annotated[int, Field(ge=0)]
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
    path = _calendar_path(year)
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
) -> DeadlineShift:
    """Apply the AEAT deadline-shift rule and return a :class:`DeadlineShift` result.

    The rule moves the deadline to the next business day when the
    original close date is a Saturday, Sunday, national holiday, or
    CCAA holiday of the taxpayer's tax residence.

    Modelo-specific exceptions (e.g., Modelo 369 OSS / IOSS) bypass
    the shift and return an unshifted :class:`DeadlineShift` with reason
    ``modelo_exception``.

    When ``calendar`` is omitted the function loads it via
    :func:`load_holiday_calendar` keyed by the original close date's
    year. Callers that already hold the calendar may pass it directly
    to avoid a second lookup.
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

    target_calendar = calendar if calendar is not None else load_holiday_calendar(original_close_date.year)

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
    "MODELOS_WITHOUT_SHIFT",
    "CalendarCCAA",
    "DeadlineShift",
    "Holiday",
    "HolidayCalendar",
    "HolidayJurisdiction",
    "is_business_day",
    "load_holiday_calendar",
    "next_business_day",
    "shift_deadline",
)
