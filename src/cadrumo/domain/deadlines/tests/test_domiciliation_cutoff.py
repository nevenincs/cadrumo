"""Domiciliación payment cutoffs derived from Orden EHA/1658/2009 art. 3.2 and Anexo II.

Expected values are worked by hand from the Orden and the published calendars,
never copied from a run:

* Anexo II, Modelo 303: "Desde el día 1 hasta el 15 de los meses de abril, julio
  y octubre, y desde el día 1 hasta el 25 del mes de enero" (quarterly); day 25 of
  the filing month (monthly), and for January's autoliquidación day 23 of
  February, 24 in a leap year.
* Art. 3.2.b: the domiciliación period is extended by the days the filing period
  is extended when its last day is inhábil.
* Orden HAC/241/2025, from 15 March 2025: at least "tres días hábiles o cinco
  naturales" must remain before the end of the voluntary period, counted on the
  calendar of the municipality of AEAT's Departamento de Informática (Madrid).
* 2026 calendar (BOE-A-2025-23702): 15 April, 15 July and 15 October 2026 fall on
  a Wednesday, a Wednesday and a Thursday and are not inhábil in Madrid; the
  windows close on Monday 20 April, Monday 20 July and Tuesday 20 October.

The AEAT 2026 domiciliación calendar bundled with the registry is an independent
oracle for every Modelo 303 row it prints.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from html import unescape

import pytest

from ....core.period import Period
from ....core.resources.bundled_data import resolve_corpus_binary
from ...calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...calculations.registry.calendar_ccaa_catalogue import resolve_calendar_ccaa_catalogue
from ...calculations.registry.schema_deadlines import DeadlineWindowDefinition
from ...calculations.registry.schema_references import TemporalProjectionDirection
from ...calculations.registry.tests.authored_editions import filing_year_envelope, source_exercise
from ...calculations.registry.tests.published_authority import published_source_reference
from ..domiciliation_cutoff import (
    AuthoredPaymentCutoff,
    DerivedPaymentCutoff,
    DomiciliationClause,
    DomiciliationHolidayCoverage,
    DomiciliationMargin,
    DomiciliationProcedure,
    InhabilBaseAuthority,
    InhabilBasePolicy,
    PaymentCutoffUnavailableReason,
    UnavailablePaymentCutoff,
    derive_domiciliation_cutoff,
    derive_payment_cutoff,
    resolve_payment_cutoff,
)
from ..errors import DeadlineValidationError
from ..festivos import Holiday, HolidayCalendar, HolidayJurisdiction
from ..plazo import resolve_filing_window
from .calendar_shapes import first_year_where
from .effective_close_scan import first_unpublished_calendar_year

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DOMICILIATION_CALENDAR_SOURCE = "aeat-calendario-contribuyente-2026-domiciliacion"
_CALENDAR_YEAR = source_exercise(published_source_reference(_DOMICILIATION_CALENDAR_SOURCE))
"""The exercise of the AEAT domiciliación calendar the hand-worked Anexo II days below are read from."""
_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_QUARTERLY = DomiciliationClause(deadline_month_offset=1, filing_last_day=20, domiciliation_last_day=15)
_MONTHLY = DomiciliationClause(deadline_month_offset=1, filing_last_day=30, domiciliation_last_day=25)
_JANUARY = DomiciliationClause(
    deadline_month_offset=1,
    filing_last_day=None,
    domiciliation_last_day=23,
    leap_year_domiciliation_last_day=24,
)
_MARGIN = DomiciliationMargin(min_business_days=3, min_calendar_days=5, territory="ES-MD")
_PRE_MARGIN = DomiciliationProcedure(
    margin=None,
    inhabil_base=InhabilBasePolicy.KEEP,
    inhabil_base_authority=InhabilBaseAuthority.ORDEN_TEXT,
)
_ORDEN_MARGIN = DomiciliationProcedure(
    margin=_MARGIN,
    inhabil_base=InhabilBasePolicy.KEEP,
    inhabil_base_authority=InhabilBaseAuthority.ORDEN_TEXT,
)
_PRACTICE = DomiciliationProcedure(
    margin=_MARGIN,
    inhabil_base=InhabilBasePolicy.LATEST_MARGIN_COMPLIANT_BUSINESS_DAY,
    inhabil_base_authority=InhabilBaseAuthority.AEAT_ADMINISTRATIVE_PRACTICE,
)


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _weekdays_except(*holidays: date) -> Callable[[date], bool]:
    def business_day(candidate: date) -> bool:
        return candidate.weekday() < 5 and candidate not in holidays

    return business_day


def _never_consulted(candidate: date) -> bool:
    raise AssertionError(f"a procedure without a margin read the calendar for {candidate}")


def _window(modelo: str, year: int, code: str, operation: PinnedAuthorityOperation) -> DeadlineWindowDefinition:
    resolution = resolve_filing_window(modelo, year, Period.from_year_and_code(year, code), authority=operation)
    assert resolution is not None, f"no {modelo} window for {year} {code}"
    window = resolution.dated_window
    assert window is not None, f"the {modelo} {year} {code} window has no known close"
    return window


# ---------------------------------------------------------------------------
# Pure arithmetic against the Orden's text.
# ---------------------------------------------------------------------------


def _april(year: int, day: int) -> date:
    return date(year, 4, day)


_THURSDAY_30_APRIL = first_year_where(lambda candidate: _april(candidate, 30).weekday() == 3)


def test_natural_days_are_counted_strictly_between_the_domiciliation_end_and_the_close() -> None:
    # A first quarter whose 20 April is a Sunday, so filing closes Monday 21 April and the
    # Anexo II day 15 moves one day to Wednesday 16. Jueves Santo (17, Madrid)
    # and Viernes Santo (18, national) leave one business day after the 16th and
    # four natural days strictly before the close, so the 16th fails both counts.
    # Tuesday 15 leaves five natural days, the "o" of the Orden, as AEAT's calendar
    # publishes for such a year ("1 al 15 de abril").
    year = first_year_where(lambda candidate: _april(candidate, 20).weekday() == 6)
    arithmetic = derive_domiciliation_cutoff(
        clause=_QUARTERLY,
        procedure=_ORDEN_MARGIN,
        period_end=date(year, 3, 31),
        closes_on=_april(year, 21),
        business_day=_weekdays_except(_april(year, 17), _april(year, 18)),
    )

    assert arithmetic.extension_days == 1
    assert arithmetic.base_on == _april(year, 16)
    assert arithmetic.margin_cap_on == _april(year, 15)
    assert arithmetic.cutoff_on == _april(year, 15)


def test_the_margin_is_met_by_three_business_days_with_fewer_than_five_natural_days() -> None:
    # Filing closes on a Thursday 30 April. Monday 27 leaves 28, 29 and 30: three
    # business days in three natural days, so 27 is the latest compliant day.
    year = _THURSDAY_30_APRIL
    arithmetic = derive_domiciliation_cutoff(
        clause=_MONTHLY,
        procedure=_ORDEN_MARGIN,
        period_end=date(year, 3, 31),
        closes_on=_april(year, 30),
        business_day=_weekdays_except(),
    )

    assert arithmetic.margin_cap_on == _april(year, 27)


def test_the_orden_keeps_an_inhabil_anexo_day_and_the_aeat_practice_moves_it() -> None:
    # 3M: Anexo II day 25 April is a Saturday when 30 April is a Thursday. The Orden
    # moves nothing, so the day stays; AEAT's calendar publishes Monday 27, the
    # latest business day that leaves three business days before Thursday 30.
    year = _THURSDAY_30_APRIL
    common = {
        "clause": _MONTHLY,
        "period_end": date(year, 3, 31),
        "closes_on": _april(year, 30),
        "business_day": _weekdays_except(),
    }

    assert derive_domiciliation_cutoff(procedure=_ORDEN_MARGIN, **common).cutoff_on == _april(year, 25)
    assert derive_domiciliation_cutoff(procedure=_PRACTICE, **common).cutoff_on == _april(year, 27)


def test_a_holiday_anexo_day_moves_back_to_the_latest_business_day_with_the_margin() -> None:
    # 11M: 25 December is a national holiday (a Friday) and filing closes Wednesday
    # 30 December. Monday 28 and Tuesday 29 leave too little; Thursday 24 leaves
    # six natural days.
    year = first_year_where(lambda candidate: date(candidate, 12, 30).weekday() == 2)
    arithmetic = derive_domiciliation_cutoff(
        clause=_MONTHLY,
        procedure=_PRACTICE,
        period_end=date(year, 11, 30),
        closes_on=date(year, 12, 30),
        business_day=_weekdays_except(date(year, 12, 25)),
    )

    assert arithmetic.cutoff_on == date(year, 12, 24)


# A leap year whose 29 February is a weekday, and a common year whose 28 February is a Sunday.
_LEAP_WEEKDAY_FEBRUARY = first_year_where(
    lambda candidate: calendar.isleap(candidate) and date(candidate, 2, 29).weekday() < 5
)
_COMMON_SUNDAY_FEBRUARY = first_year_where(
    lambda candidate: not calendar.isleap(candidate) and date(candidate, 2, 28).weekday() == 6
)


@pytest.mark.parametrize(
    ("period_end", "closes_on", "expected"),
    (
        # A leap year: February has 29 days, a weekday, so nothing extends.
        (
            date(_LEAP_WEEKDAY_FEBRUARY, 1, 31),
            date(_LEAP_WEEKDAY_FEBRUARY, 2, 29),
            date(_LEAP_WEEKDAY_FEBRUARY, 2, 24),
        ),
        # A common year whose 28 February is a Sunday: filing closes Monday 1 March, one day later.
        (
            date(_COMMON_SUNDAY_FEBRUARY, 1, 31),
            date(_COMMON_SUNDAY_FEBRUARY, 3, 1),
            date(_COMMON_SUNDAY_FEBRUARY, 2, 24),
        ),
    ),
    ids=("leap-year-day-24", "common-year-day-23-plus-one"),
)
def test_january_autoliquidacion_uses_the_leap_year_day(period_end: date, closes_on: date, expected: date) -> None:
    arithmetic = derive_domiciliation_cutoff(
        clause=_JANUARY,
        procedure=_PRE_MARGIN,
        period_end=period_end,
        closes_on=closes_on,
        business_day=_never_consulted,
    )

    assert arithmetic.cutoff_on == expected


_WEEKEND_PRACTICE = DomiciliationProcedure(
    margin=_MARGIN,
    inhabil_base=InhabilBasePolicy.WEEKEND_TO_LATEST_MARGIN_COMPLIANT_BUSINESS_DAY,
    inhabil_base_authority=InhabilBaseAuthority.AEAT_ADMINISTRATIVE_PRACTICE,
)
_BUSINESS_ONLY_PRACTICE = DomiciliationProcedure(
    margin=DomiciliationMargin(min_business_days=3, min_calendar_days=None, territory="ES-MD"),
    inhabil_base=InhabilBasePolicy.WEEKEND_TO_LATEST_MARGIN_COMPLIANT_BUSINESS_DAY,
    inhabil_base_authority=InhabilBaseAuthority.AEAT_ADMINISTRATIVE_PRACTICE,
)


def _quarter_with_fifteenth_on(weekday: int) -> tuple[date, date]:
    """The end of a quarter whose following Anexo II day 15 falls on ``weekday``, and that day.

    The month is found from the support horizon forward, so no year is written here.
    """
    year = filing_year_envelope().horizon
    for month_index in range(year * 12, year * 12 + 120):
        month = month_index % 12 + 1
        if month not in {1, 4, 7, 10}:
            continue
        anexo_on = date(month_index // 12, month, 15)
        if anexo_on.weekday() == weekday:
            return anexo_on.replace(day=1) - timedelta(days=1), anexo_on
    raise AssertionError(f"no quarter in ten years has its fifteenth on weekday {weekday}")


def test_the_weekend_practice_moves_a_saturday_anexo_day_forward_to_the_latest_compliant_business_day() -> None:
    # Saturday 15 before a Thursday 20 close: Monday 17 leaves 18, 19 and 20,
    # as the 2024 and 2025 calendars publish ("mayo: 1 al 17 de junio").
    period_end, anexo_on = _quarter_with_fifteenth_on(5)
    arithmetic = derive_domiciliation_cutoff(
        clause=_QUARTERLY,
        procedure=_WEEKEND_PRACTICE,
        period_end=period_end,
        closes_on=anexo_on + timedelta(days=5),
        business_day=_weekdays_except(),
    )

    assert arithmetic.cutoff_on == anexo_on + timedelta(days=2)


def test_the_weekend_practice_keeps_a_holiday_anexo_day_that_meets_the_margin() -> None:
    # A holiday Friday 15 before a Wednesday 20 close leaves 18, 19 and 20, so it
    # stands, as the 2025 calendar keeps 15 August; the 2026 practice, which
    # replaces any inhábil day, takes Thursday 14 instead.
    period_end, anexo_on = _quarter_with_fifteenth_on(4)
    common = {
        "clause": _QUARTERLY,
        "period_end": period_end,
        "closes_on": anexo_on + timedelta(days=5),
        "business_day": _weekdays_except(anexo_on),
    }

    assert derive_domiciliation_cutoff(procedure=_WEEKEND_PRACTICE, **common).cutoff_on == anexo_on
    assert derive_domiciliation_cutoff(procedure=_PRACTICE, **common).cutoff_on == anexo_on - timedelta(days=1)


def test_a_business_day_only_margin_ignores_natural_days() -> None:
    # Anexo II day Tuesday 15: the close on Sunday 20 moves to Monday 21 and the
    # Anexo day by one day to Wednesday 16. With Thursday 17 and Friday 18
    # inhábil, the business-only margin needs Monday 14 (15, 16 and 21), while the
    # Orden's natural-day alternative accepts Tuesday 15, as Modelo 303 febrero
    # 2024 (published 25 March) and 1T 25 (published 15 April) show.
    period_end, anexo_on = _quarter_with_fifteenth_on(1)
    common = {
        "clause": _QUARTERLY,
        "period_end": period_end,
        "closes_on": anexo_on + timedelta(days=6),
        "business_day": _weekdays_except(anexo_on + timedelta(days=2), anexo_on + timedelta(days=3)),
    }

    business_only = derive_domiciliation_cutoff(procedure=_BUSINESS_ONLY_PRACTICE, **common)
    with_natural_days = derive_domiciliation_cutoff(procedure=_WEEKEND_PRACTICE, **common)

    assert business_only.base_on == anexo_on + timedelta(days=1)
    assert business_only.cutoff_on == anexo_on - timedelta(days=1)
    assert with_natural_days.cutoff_on == anexo_on


def test_the_margin_walk_crosses_into_the_previous_year() -> None:
    # A clause closing on a Wednesday 3 January with an Anexo day of Monday
    # 1 January (a holiday): Tuesday 2 January leaves too little, 30 and 31
    # December are a weekend, Friday 29 December of the year before leaves two
    # business days and four natural days strictly before the close, and
    # Thursday 28 December leaves three business days, so it is the cap.
    year = first_year_where(lambda candidate: date(candidate + 1, 1, 3).weekday() == 2)
    clause = DomiciliationClause(deadline_month_offset=1, filing_last_day=3, domiciliation_last_day=1)
    arithmetic = derive_domiciliation_cutoff(
        clause=clause,
        procedure=_ORDEN_MARGIN,
        period_end=date(year, 12, 31),
        closes_on=date(year + 1, 1, 3),
        business_day=_weekdays_except(date(year + 1, 1, 1)),
    )

    assert arithmetic.margin_cap_on == date(year, 12, 28)
    assert arithmetic.cutoff_on == date(year, 12, 28)


def test_a_window_closing_before_its_nominal_close_is_a_registry_inconsistency() -> None:
    with pytest.raises(DeadlineValidationError, match="before the nominal filing close"):
        derive_domiciliation_cutoff(
            clause=_QUARTERLY,
            procedure=_PRE_MARGIN,
            period_end=date(_CALENDAR_YEAR, 3, 31),
            closes_on=date(_CALENDAR_YEAR, 4, 19),
            business_day=_never_consulted,
        )


# ---------------------------------------------------------------------------
# Through the published authority.
# ---------------------------------------------------------------------------


def _published_303_domiciliation_rows() -> tuple[tuple[int, str, date], ...]:
    source = published_source_reference(_DOMICILIATION_CALENDAR_SOURCE)
    path = resolve_corpus_binary(*source.corpus_path.split("/"))
    assert path is not None
    text = path.read_text(encoding="utf-8")
    rows: list[tuple[int, str, date]] = []
    for row in re.findall(r"<tr>(.*?)</tr>", text, flags=re.DOTALL):
        cells = re.findall(r"<td>(.*?)</td>", row, flags=re.DOTALL)
        if len(cells) < 2 or "303" not in unescape(cells[0]):
            continue
        # The second cell is the domiciliación column; the third is filing.
        for count, kind, year, day, month in re.findall(
            r"<li>(\d+)([MT]) (\d{2}): 1(?: de \w+)? al (\d+) de (\w+)</li>", cells[1]
        ):
            filing_year = _CALENDAR_YEAR - _CALENDAR_YEAR % 100 + int(year)
            code = f"{int(count):02d}" if kind == "M" else f"{count}T"
            period_end = Period.from_year_and_code(filing_year, code).end_date
            month_number = _MONTHS[month]
            cutoff_year = filing_year if month_number > period_end.month else filing_year + 1
            rows.append((filing_year, code, date(cutoff_year, month_number, int(day))))
    return tuple(rows)


def test_every_modelo_303_row_of_the_published_domiciliation_calendar_is_derived(
    operation: PinnedAuthorityOperation,
) -> None:
    rows = _published_303_domiciliation_rows()
    # Twelve monthly rows and four quarterly rows: 12M and 4T of the previous
    # exercise, 1M to 11M and 1T to 3T of the calendar's own.
    assert len(rows) == 16

    for filing_year, code, published in rows:
        derived = derive_payment_cutoff("303", _window("303", filing_year, code, operation), operation=operation)
        assert isinstance(derived, DerivedPaymentCutoff), (filing_year, code, derived)
        assert derived.cutoff_on == published, (filing_year, code)


@pytest.mark.parametrize(
    ("code", "expected"),
    (("1T", date(_CALENDAR_YEAR, 4, 15)), ("2T", date(_CALENDAR_YEAR, 7, 15)), ("3T", date(_CALENDAR_YEAR, 10, 15))),
)
def test_calendar_year_quarters_without_an_authored_cutoff_resolve_a_derived_one(
    code: str,
    expected: date,
    operation: PinnedAuthorityOperation,
) -> None:
    window = _window("303", _CALENDAR_YEAR, code, operation)
    assert window.payment_cutoff_on is None

    resolved = resolve_payment_cutoff("303", window, operation=operation)

    assert isinstance(resolved, DerivedPaymentCutoff)
    assert resolved.cutoff_on == expected
    assert resolved.extension_days == 0
    assert resolved.base_on == expected
    assert resolved.clause.variant_id == "domiciliation-cutoff-clause:303:quarterly:1t-3t"
    assert resolved.procedure.variant_id == "domiciliation-procedure:aeat-practice-2026"
    assert resolved.inhabil_base_authority is InhabilBaseAuthority.AEAT_ADMINISTRATIVE_PRACTICE
    assert resolved.holiday_coverage is DomiciliationHolidayCoverage.NATIONAL_AND_TERRITORY_MUNICIPAL_UNVERIFIED
    assert "orden-eha-1658-2009:anexo-ii" in resolved.legal_refs
    assert "orden-hac-241-2025:art-2" in resolved.legal_refs
    assert _DOMICILIATION_CALENDAR_SOURCE in resolved.source_refs


def test_an_authored_cutoff_wins_over_a_different_derived_one(operation: PinnedAuthorityOperation) -> None:
    # Modelo 111 2M of the calendar year: AEAT publishes 16 March; the rule gives Tuesday 17, which
    # leaves 18, 19 and 20 before the Friday close with no Madrid holiday between
    # (the expected discrepancy of the calendar-backed retention census). The
    # authored date is an explicit override.
    window = _window("111", _CALENDAR_YEAR, "02", operation)

    resolved = resolve_payment_cutoff("111", window, operation=operation)
    derived = derive_payment_cutoff("111", window, operation=operation)

    assert isinstance(resolved, AuthoredPaymentCutoff)
    assert resolved.cutoff_on == date(_CALENDAR_YEAR, 3, 16)
    assert resolved.legal_refs == tuple(window.legal_refs)
    assert derived.cutoff_on == date(_CALENDAR_YEAR, 3, 17)


def test_a_past_period_under_the_orden_margin_derives_against_its_published_calendar(
    operation: PinnedAuthorityOperation,
) -> None:
    # 3T of the year before the calendar year: Anexo day Wednesday 15 October, filing closes Monday 20 October;
    # 16, 17 and 20 are business days in Madrid, so the 15th stands. The margin is
    # the Orden's; the weekend replacement the variant carries is AEAT's practice.
    derived = derive_payment_cutoff("303", _window("303", _CALENDAR_YEAR - 1, "3T", operation), operation=operation)

    assert isinstance(derived, DerivedPaymentCutoff)
    assert derived.cutoff_on == date(_CALENDAR_YEAR - 1, 10, 15)
    assert derived.procedure.variant_id == "domiciliation-procedure:hac-241-2025"
    assert derived.inhabil_base_authority is InhabilBaseAuthority.AEAT_ADMINISTRATIVE_PRACTICE
    assert derived.procedure.projection_direction is TemporalProjectionDirection.AUTHORED


def test_the_floor_period_derives_from_the_floor_reaching_variants_without_a_calendar(
    operation: PinnedAuthorityOperation,
) -> None:
    # 1T of the floor year: before the margin existed the Anexo day stands even on
    # Viernes Santo, and no holiday calendar is read.
    floor = filing_year_envelope().floor
    window = _window("303", floor, "1T", operation)

    derived = derive_payment_cutoff("303", window, operation=operation)

    assert isinstance(derived, DerivedPaymentCutoff)
    assert derived.cutoff_on == date(floor, 4, 15)
    assert derived.cutoff_on == window.payment_cutoff_on
    assert derived.procedure.variant_id == "domiciliation-procedure:orden-text-pre-margin"
    assert derived.holiday_coverage is DomiciliationHolidayCoverage.NOT_CONSULTED
    assert derived.margin_cap_on is None


@pytest.mark.parametrize("code", ("4T", "12"))
def test_the_calendar_year_end_cutoffs_derive_from_the_next_years_published_calendar(
    code: str,
    operation: PinnedAuthorityOperation,
) -> None:
    # The Anexo II day is 25 January. The filing period ends Saturday 30 January of
    # the next year, so it runs to Monday 1 February (two days) and art. 3.2.b extends
    # the Anexo II day by the same two days to Wednesday 27 January. That day leaves
    # five natural days and three business days (28, 29 January and 1 February) before
    # the close. The calendar prints no row for 12M of its year, so none is authored.
    window = _window("303", _CALENDAR_YEAR, code, operation)
    assert window.closes_on == date(_CALENDAR_YEAR + 1, 2, 1)
    assert window.payment_cutoff_on is None

    resolved = resolve_payment_cutoff("303", window, operation=operation)

    assert isinstance(resolved, DerivedPaymentCutoff)
    assert resolved.extension_days == 2
    assert resolved.cutoff_on == date(_CALENDAR_YEAR + 1, 1, 27)
    assert resolved.base_on == date(_CALENDAR_YEAR + 1, 1, 27)


# A filing year the authority publishes no holiday calendar for, chosen so that
# 15 July is a Saturday and 20 July a Thursday.
with bundled_indexed_authority().operation() as _published:
    _FIRST_UNPUBLISHED_YEAR = first_unpublished_calendar_year(_published)
_PROJECTED_YEAR = first_year_where(
    lambda candidate: date(candidate, 7, 15).weekday() == 5, start=_FIRST_UNPUBLISHED_YEAR
)


def _projected_window() -> DeadlineWindowDefinition:
    period = Period.from_year_and_code(_PROJECTED_YEAR, "2T")
    return DeadlineWindowDefinition.model_validate(
        {
            "id": f"synthetic-303-{_PROJECTED_YEAR}-2t",
            "filing_year": _PROJECTED_YEAR,
            "period": period,
            "period_kind": "quarterly",
            "opens_on": date(_PROJECTED_YEAR, 7, 1),
            "closes_on": date(_PROJECTED_YEAR, 7, 20),
            "legal_refs": ("rd-1624-1992:art-71",),
            "source_refs": ("aeat-modelo-303-procedure",),
        },
    )


def _synthetic_calendar(operation: PinnedAuthorityOperation, *holidays: date) -> HolidayCalendar:
    madrid = resolve_calendar_ccaa_catalogue(
        effective_date=date(_PROJECTED_YEAR, 7, 15),
        authority=operation,
    ).require("ES-MD")
    return HolidayCalendar(
        year=_PROJECTED_YEAR,
        boe_ref="synthetic-test-calendar",
        national=tuple(
            Holiday(holiday_date=day, jurisdiction=HolidayJurisdiction.NATIONAL, name="Synthetic holiday")
            for day in holidays
        ),
        verified_territories=(madrid,),
    )


@pytest.mark.parametrize(
    ("holidays", "expected"),
    (
        # Saturday 15 July moves to Monday 17, which leaves 18, 19 and 20.
        ((), date(_PROJECTED_YEAR, 7, 17)),
        # With Monday 17 a holiday, Friday 14 is the latest day with five natural days.
        ((date(_PROJECTED_YEAR, 7, 17),), date(_PROJECTED_YEAR, 7, 14)),
    ),
    ids=("weekend-anexo-day", "holiday-after-weekend"),
)
def test_a_future_year_projects_the_rule_forward_when_its_calendar_is_known(
    holidays: tuple[date, ...],
    expected: date,
    operation: PinnedAuthorityOperation,
) -> None:
    derived = derive_payment_cutoff(
        "303",
        _projected_window(),
        operation=operation,
        calendars=(_synthetic_calendar(operation, *holidays),),
    )

    assert isinstance(derived, DerivedPaymentCutoff)
    assert derived.cutoff_on == expected
    assert derived.base_on == date(_PROJECTED_YEAR, 7, 15)
    assert derived.clause.projection_direction is TemporalProjectionDirection.FORWARD
    assert derived.procedure.projection_direction is TemporalProjectionDirection.FORWARD
    assert derived.procedure.variant_id == "domiciliation-procedure:aeat-practice-2026"


def test_a_future_year_without_a_published_calendar_is_unavailable(operation: PinnedAuthorityOperation) -> None:
    resolved = resolve_payment_cutoff("303", _projected_window(), operation=operation)

    assert isinstance(resolved, UnavailablePaymentCutoff)
    assert resolved.reason is PaymentCutoffUnavailableReason.HOLIDAY_CALENDAR_UNAVAILABLE
    assert resolved.clause is not None
    assert resolved.clause.projection_direction is TemporalProjectionDirection.FORWARD


def test_an_unverified_territory_is_unavailable_rather_than_national_only(operation: PinnedAuthorityOperation) -> None:
    unverified = _synthetic_calendar(operation).model_copy(update={"verified_territories": ()})

    resolved = derive_payment_cutoff("303", _projected_window(), operation=operation, calendars=(unverified,))

    assert isinstance(resolved, UnavailablePaymentCutoff)
    assert resolved.reason is PaymentCutoffUnavailableReason.TERRITORY_UNVERIFIED


# ---------------------------------------------------------------------------
# Other Anexo II modelos.
#
# Modelos 111, 115, 117, 123, 126 and 128: "Obligación trimestral de
# presentación: Desde el día 1 hasta el 15 de los meses de abril, julio, octubre
# y enero", and monthly from the 1st to the 15th of every filing month; filing
# closes on the 20th (RD 439/2007 art. 108.1). Modelos 130 and 131: day 15 of
# April, July and October and day 25 of January; filing closes on the 20th and,
# for the fourth quarter, on 30 January (RD 439/2007 art. 111.1).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("modelo", ("111", "115", "117", "123", "126", "128"))
@pytest.mark.parametrize(
    ("year", "code", "expected"),
    (
        # Wednesday 15 April of the calendar year; filing closes Monday 20 April, so nothing
        # extends and 16, 17 and 20 April leave the margin.
        (_CALENDAR_YEAR, "1T", date(_CALENDAR_YEAR, 4, 15)),
        # Thursday 15 January of the calendar year; filing closes Tuesday 20 January.
        (_CALENDAR_YEAR - 1, "4T", date(_CALENDAR_YEAR, 1, 15)),
    ),
    ids=("1t-calendar-year", "4t-previous-year"),
)
def test_a_quarterly_withholding_modelo_derives_day_15_of_the_filing_month(
    modelo: str,
    year: int,
    code: str,
    expected: date,
    operation: PinnedAuthorityOperation,
) -> None:
    derived = derive_payment_cutoff(modelo, _window(modelo, year, code, operation), operation=operation)

    assert isinstance(derived, DerivedPaymentCutoff), (modelo, derived)
    assert derived.cutoff_on == expected
    assert derived.extension_days == 0
    assert derived.clause.variant_id == f"domiciliation-cutoff-clause:{modelo}:quarterly"
    assert "orden-eha-1658-2009:anexo-ii" in derived.legal_refs
    assert "rd-439-2007:art-108" in derived.legal_refs


@pytest.mark.parametrize(
    ("code", "expected"),
    (
        # Anexo day Sunday 15 February of the calendar year; filing closes Friday 20 February.
        # AEAT's practice takes the latest business day leaving three business
        # days: Tuesday 17 (18, 19 and 20). The 2026 calendar prints 17.
        ("01", date(_CALENDAR_YEAR, 2, 17)),
        # Nominal close Saturday 20 June 2026 moves to Monday 22, two days, so
        # the Anexo day moves from 15 to Wednesday 17 June, which leaves 18, 19
        # and 22. The 2026 calendar prints 17.
        ("05", date(_CALENDAR_YEAR, 6, 17)),
    ),
    ids=("01-weekend-anexo-day", "05-extended-close"),
)
def test_a_monthly_modelo_111_derives_from_day_15_of_the_following_month(
    code: str,
    expected: date,
    operation: PinnedAuthorityOperation,
) -> None:
    derived = derive_payment_cutoff("111", _window("111", _CALENDAR_YEAR, code, operation), operation=operation)

    assert isinstance(derived, DerivedPaymentCutoff), derived
    assert derived.cutoff_on == expected
    assert derived.clause.variant_id == "domiciliation-cutoff-clause:111:monthly"


def test_a_monthly_modelo_111_period_12_cuts_off_on_15_january(operation: PinnedAuthorityOperation) -> None:
    # Period 12 of the year before the calendar year is filed in January of the
    # calendar year, whose Anexo day is Thursday 15 January; filing closes Tuesday 20 January.
    derived = derive_payment_cutoff("111", _window("111", _CALENDAR_YEAR - 1, "12", operation), operation=operation)

    assert isinstance(derived, DerivedPaymentCutoff), derived
    assert derived.anexo_on == date(_CALENDAR_YEAR, 1, 15)
    assert derived.cutoff_on == date(_CALENDAR_YEAR, 1, 15)


@pytest.mark.parametrize("modelo", ("130", "131"))
@pytest.mark.parametrize(
    ("year", "code", "expected_anexo", "expected"),
    (
        # Wednesday 15 July of the calendar year; filing closes Monday 20 July.
        (_CALENDAR_YEAR, "2T", date(_CALENDAR_YEAR, 7, 15), date(_CALENDAR_YEAR, 7, 15)),
        # Anexo day Sunday 25 January of the calendar year; filing closes Friday 30 January.
        # AEAT's practice takes Tuesday 27, which leaves 28, 29 and 30; the calendar
        # prints "1 al 27 de enero" for the fourth quarter of both modelos.
        (_CALENDAR_YEAR - 1, "4T", date(_CALENDAR_YEAR, 1, 25), date(_CALENDAR_YEAR, 1, 27)),
    ),
    ids=("2t-calendar-year", "4t-previous-year"),
)
def test_a_pago_fraccionado_modelo_derives_the_303_quarterly_days(
    modelo: str,
    year: int,
    code: str,
    expected_anexo: date,
    expected: date,
    operation: PinnedAuthorityOperation,
) -> None:
    derived = derive_payment_cutoff(modelo, _window(modelo, year, code, operation), operation=operation)

    assert isinstance(derived, DerivedPaymentCutoff), (modelo, derived)
    assert derived.anexo_on == expected_anexo
    assert derived.cutoff_on == expected
    assert "rd-439-2007:art-111" in derived.legal_refs
    assert _DOMICILIATION_CALENDAR_SOURCE in derived.source_refs


def test_a_modelo_without_a_declared_clause_has_no_cutoff(operation: PinnedAuthorityOperation) -> None:
    # Anexo II lists Modelo 216, but the registry declares no clause for it.
    window = _window("216", _CALENDAR_YEAR, "1T", operation).model_copy(update={"payment_cutoff_on": None})

    resolved = resolve_payment_cutoff("216", window, operation=operation)

    assert isinstance(resolved, UnavailablePaymentCutoff)
    assert resolved.reason is PaymentCutoffUnavailableReason.NO_CLAUSE
    assert resolved.clause is None


def test_a_coordinate_below_the_support_floor_has_no_cutoff_rule(operation: PinnedAuthorityOperation) -> None:
    floor = operation.supported_filing_years().floor
    period = Period.from_year_and_code(floor - 1, "1T")
    window = DeadlineWindowDefinition.model_validate(
        {
            "id": "below-floor-303-1t",
            "filing_year": floor - 1,
            "period": period,
            "period_kind": "quarterly",
            "opens_on": period.end_date + timedelta(days=1),
            "closes_on": period.end_date + timedelta(days=20),
            "legal_refs": ("rd-1624-1992:art-71",),
            "source_refs": ("aeat-modelo-303-procedure",),
        },
    )

    answer = derive_payment_cutoff("303", window, operation=operation)
    assert isinstance(answer, UnavailablePaymentCutoff)
    assert answer.reason is PaymentCutoffUnavailableReason.NO_CLAUSE
