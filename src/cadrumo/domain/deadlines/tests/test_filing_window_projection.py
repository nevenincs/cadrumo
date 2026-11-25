"""Filing windows projected from the governed rule, and their precedence under authored windows.

The rule is RD 1624/1992 art. 71.4 with Orden EHA/3786/2008 art. 7 (Modelo 303)
and Orden EHA/3111/2009 art. 8 (Modelo 390): a quarterly window closes on the
20th of the following month, the fourth quarter and the annual summary on 30
January, a monthly SII window on the 30th of the following month and January's
on the last day of February. A close that falls on a Saturday, Sunday or
national holiday moves to the next day that is none of those, as AEAT publishes
it.

Expected values are worked independently of the projection: the agreement test
compares against every window AEAT published and the registry authors, and the
future-year test against a separate oracle written here from the articles'
text. Holiday calendars for years the authority does not publish are supplied by
the test; each lists the statutory national holidays the walks under test can
reach.
"""

from __future__ import annotations

import calendar as _calendar
from collections.abc import Iterator
from datetime import date, timedelta

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ...calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...calculations.registry.tests.authored_editions import filing_year_envelope, supported_authored_exercises
from ...contribuyente.entity_type import EntityType
from ...contribuyente.renta_codes import FiscalResidency
from ..effective_close import resolve_effective_filing_deadline
from ..engine import DeadlineEngine, indexed_deadline_window_year
from ..errors import DeadlineValidationError
from ..festivos import (
    CALENDAR_UNAVAILABLE_SHIFT_REASON,
    DeadlineHolidayCoverage,
    HolidayCalendar,
    holiday_calendar_from_authority,
)
from ..filing_window_projection import (
    AuthoredFilingWindow,
    FilingCloseInhabilBasis,
    FilingWindowClause,
    FilingWindowOpening,
    ProjectedFilingWindow,
    project_scheduled_window,
    scheduled_coordinate,
)
from ..models import (
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    ModeloEnrollment,
    ObligationStatus,
    TaxpayerProfile,
)
from ..plazo import resolve_filing_window
from .calendar_shapes import first_year_where, statutory_national_calendar
from .effective_close_scan import first_unpublished_calendar_year

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS = ("303", "390")


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def project_filing_window(
    operation: PinnedAuthorityOperation,
    *,
    modelo: str,
    period: Period,
    calendars: tuple[HolidayCalendar, ...],
) -> ProjectedFilingWindow | None:
    """Project one coordinate from the governed rule with holiday calendars supplied ahead of the authority."""
    if not period.has_date_span():
        return None
    scheduled = scheduled_coordinate(
        operation, modelo=modelo, filing_year=period.filing_year, token=period.registry_token
    )
    if scheduled is None:
        return None
    _metadata, schedule = scheduled
    return project_scheduled_window(operation, modelo=modelo, period=period, schedule=schedule, calendars=calendars)


with bundled_indexed_authority().operation() as _published:
    _FIRST_UNPUBLISHED_YEAR = first_unpublished_calendar_year(_published)


@pytest.fixture(scope="module")
def supplied_calendars(operation: PinnedAuthorityOperation) -> tuple[HolidayCalendar, ...]:
    """Fiestas laborales de ámbito nacional for each supported year the authority publishes no calendar for."""
    unpublished: list[int] = []
    for year in filing_year_envelope().years:
        try:
            holiday_calendar_from_authority(year, operation=operation)
        except DeadlineValidationError:
            unpublished.append(year)
    return tuple(statutory_national_calendar(year) for year in unpublished)


# ---------------------------------------------------------------------------
# Independent oracle, written from the articles' text.
# ---------------------------------------------------------------------------


def _oracle_nominal_close(modelo: str, period: Period) -> date:
    end = period.end_date
    month_year, month = (end.year + 1, 1) if end.month == 12 else (end.year, end.month + 1)
    code = period.registry_token
    if modelo == "390" or code in {"4T", "12"}:
        return date(month_year, 1, 30)
    if code.endswith("T"):
        return date(month_year, month, 20)
    if code == "01":
        return date(month_year, 2, _calendar.monthrange(month_year, 2)[1])
    return date(month_year, month, 30)


def _oracle_close(modelo: str, period: Period, holidays: frozenset[date]) -> date:
    close = _oracle_nominal_close(modelo, period)
    while close.weekday() >= 5 or close in holidays:
        close += timedelta(days=1)
    return close


# ---------------------------------------------------------------------------
# Clause arithmetic.
# ---------------------------------------------------------------------------


def test_a_clause_crosses_the_year_and_resolves_the_month_end_of_a_leap_february() -> None:
    month_end = FilingWindowClause(
        opening=FilingWindowOpening.DAY_AFTER_PERIOD_END, deadline_month_offset=1, filing_last_day=None
    )
    thirtieth = FilingWindowClause(
        opening=FilingWindowOpening.DAY_AFTER_PERIOD_END, deadline_month_offset=1, filing_last_day=30
    )

    leap_year = first_year_where(_calendar.isleap)
    common_year = leap_year + 1

    assert month_end.nominal_close(date(leap_year, 1, 31)) == date(leap_year, 2, 29)
    assert month_end.nominal_close(date(common_year, 1, 31)) == date(common_year, 2, 28)
    assert thirtieth.nominal_close(date(common_year, 12, 31)) == date(common_year + 1, 1, 30)
    assert thirtieth.opens_on(date(common_year, 12, 31)) == date(common_year + 1, 1, 1)


# ---------------------------------------------------------------------------
# Agreement with every authored window.
# ---------------------------------------------------------------------------


def _authored_rows(operation: PinnedAuthorityOperation) -> list[tuple[str, Period, date, date]]:
    """Every authored Modelo 303 and 390 window from the support floor to the authored horizon."""
    support = operation.supported_filing_years()
    rows: list[tuple[str, Period, date, date]] = []
    for year in range(support.floor, support.horizon + 1):
        index = indexed_deadline_window_year(operation, year)
        for modelo, _revision, window in index.dated:
            if modelo in _MODELOS and window.id not in index.projected:
                rows.append((modelo, window.period, window.opens_on, window.closes_on))
    return rows


def test_every_authored_303_and_390_window_agrees_with_the_rule(
    operation: PinnedAuthorityOperation, supplied_calendars: tuple[HolidayCalendar, ...]
) -> None:
    rows = _authored_rows(operation)
    support = operation.supported_filing_years()
    # Sixteen Modelo 303 periods and one Modelo 390 summary per authored year.
    assert len(rows) == (support.horizon - support.floor + 1) * 17, len(rows)

    disagreements: set[tuple[str, int, str]] = set()
    for modelo, period, opens_on, closes_on in rows:
        projected = project_filing_window(operation, modelo=modelo, period=period, calendars=supplied_calendars)
        assert isinstance(projected, ProjectedFilingWindow), (modelo, period, projected)
        assert projected.opens_on == opens_on, (modelo, period)
        if projected.closes_on != closes_on:
            disagreements.add((modelo, period.filing_year, period.registry_token))

    assert disagreements == set()


# RD 439/2007 art. 108.1 (withholding: the 20th of the month after the quarter or
# month) and art. 111.1 (pagos fraccionados: the 20th, and 30 January for the
# fourth quarter). Only modelos with a filing schedule are projected.
_RIRPF_SCHEDULED_MODELOS = ("111", "115", "123", "130", "131")


def test_every_authored_rirpf_window_agrees_with_the_rule(
    operation: PinnedAuthorityOperation, supplied_calendars: tuple[HolidayCalendar, ...]
) -> None:
    support = operation.supported_filing_years()
    checked: set[str] = set()
    disagreements: set[tuple[str, int, str]] = set()
    for year in range(support.floor, support.horizon + 1):
        index = indexed_deadline_window_year(operation, year)
        for modelo, _revision, window in index.dated:
            if modelo not in _RIRPF_SCHEDULED_MODELOS or window.id in index.projected:
                continue
            projected = project_filing_window(
                operation, modelo=modelo, period=window.period, calendars=supplied_calendars
            )
            assert isinstance(projected, ProjectedFilingWindow), (modelo, window.period, projected)
            assert projected.opens_on == window.opens_on, (modelo, window.period)
            checked.add(modelo)
            if projected.closes_on != window.closes_on:
                disagreements.add((modelo, window.period.filing_year, window.period.registry_token))

    assert checked == set(_RIRPF_SCHEDULED_MODELOS)
    assert disagreements == set(), sorted(disagreements)


@pytest.mark.parametrize("year", supported_authored_exercises("390"))
def test_the_390_authored_close_is_the_30_january_moved_past_a_weekend(
    year: int, operation: PinnedAuthorityOperation, supplied_calendars: tuple[HolidayCalendar, ...]
) -> None:
    period = Period.from_year_and_code(year, "0A")
    authored = resolve_filing_window("390", year, period, authority=operation)
    projected = project_filing_window(operation, modelo="390", period=period, calendars=supplied_calendars)
    nominal = date(year + 1, 1, 30)
    # A Saturday or Sunday nominal close moves to the Monday by art. 30.5.
    expected = nominal + timedelta(days=7 - nominal.weekday() if nominal.weekday() >= 5 else 0)

    assert isinstance(authored, AuthoredFilingWindow)
    assert authored.closes_on == expected
    assert isinstance(projected, ProjectedFilingWindow)
    assert projected.nominal_closes_on == nominal
    assert projected.closes_on == expected


# ---------------------------------------------------------------------------
# Precedence: an authored window always wins.
# ---------------------------------------------------------------------------


def test_an_authored_window_wins_over_a_differing_projection(operation: PinnedAuthorityOperation) -> None:
    # An authored first quarter whose 20 April is a weekend day: AEAT published the
    # Monday after. A calendar that also marks that Monday inhábil moves the
    # projection to the Tuesday, while the resolver keeps the authored date.
    year = next(candidate for candidate in supported_authored_exercises("303") if date(candidate, 4, 20).weekday() >= 5)
    nominal = date(year, 4, 20)
    monday = nominal + timedelta(days=7 - nominal.weekday())
    period = Period.from_year_and_code(year, "1T")
    marked = statutory_national_calendar(year, (monday.month, monday.day))

    projected = project_filing_window(operation, modelo="303", period=period, calendars=(marked,))
    resolved = resolve_filing_window("303", year, period, authority=operation)

    assert isinstance(projected, ProjectedFilingWindow)
    assert projected.closes_on == monday + timedelta(days=1)
    assert isinstance(resolved, AuthoredFilingWindow)
    assert resolved.closes_on == monday


# ---------------------------------------------------------------------------
# Future years.
# ---------------------------------------------------------------------------

# The first year the authority publishes no holiday calendar for in which 20 April is
# a Thursday of a leap year. That fixes the whole year's weekdays: 20 July a Thursday,
# 29 February a Tuesday, 30 September and 30 December Saturdays, and 30 January of the
# next year a Tuesday.
_FUTURE_YEAR = first_year_where(
    lambda candidate: _calendar.isleap(candidate) and date(candidate, 4, 20).weekday() == 3,
    start=_FIRST_UNPUBLISHED_YEAR,
)
# Synthetic calendars for that year and the next. The statutory fixed national holidays
# are joined by a holiday placed on its Thursday 20 April, so a weekday close is moved
# by a holiday and not only by a weekend.
_FUTURE_CALENDARS = (
    statutory_national_calendar(_FUTURE_YEAR, (4, 20)),
    statutory_national_calendar(_FUTURE_YEAR + 1),
)
_FUTURE_HOLIDAYS = frozenset(holiday.holiday_date for cal in _FUTURE_CALENDARS for holiday in cal.national)
_303_PERIODS = ("1T", "2T", "3T", "4T", *(f"{month:02d}" for month in range(1, 13)))


@pytest.mark.parametrize(("modelo", "code"), [*(("303", code) for code in _303_PERIODS), ("390", "0A")])
def test_a_future_year_projects_the_rule_with_the_national_shift(
    modelo: str,
    code: str,
    operation: PinnedAuthorityOperation,
) -> None:
    period = Period.from_year_and_code(_FUTURE_YEAR, code)

    projected = project_filing_window(operation, modelo=modelo, period=period, calendars=_FUTURE_CALENDARS)

    assert isinstance(projected, ProjectedFilingWindow), projected
    assert projected.nominal_closes_on == _oracle_nominal_close(modelo, period)
    assert projected.closes_on == _oracle_close(modelo, period, _FUTURE_HOLIDAYS)
    assert projected.opens_on == period.end_date + timedelta(days=1)
    assert projected.holiday_coverage is DeadlineHolidayCoverage.NATIONAL_ONLY
    assert projected.inhabil_basis is FilingCloseInhabilBasis.AEAT_PUBLISHED_PRACTICE
    clause_ref = "orden-eha-3111-2009:art-8" if modelo == "390" else "rd-1624-1992:art-71.4"
    assert clause_ref in projected.window.legal_refs
    assert "ley-39-2015:art-30.5" in projected.window.legal_refs


def test_the_oracle_matches_hand_worked_future_closes() -> None:
    # Worked by hand from the year's shape: 20 April is a Thursday (the synthetic
    # holiday moves it to Friday 21); 20 July a Thursday; 29 February a Tuesday;
    # 30 September a Saturday (Monday 2 October); 30 January of the next year a Tuesday.
    year = _FUTURE_YEAR

    def close(modelo: str, code: str) -> date:
        return _oracle_close(modelo, Period.from_year_and_code(year, code), _FUTURE_HOLIDAYS)

    assert close("303", "1T") == date(year, 4, 21)
    assert close("303", "2T") == date(year, 7, 20)
    assert close("303", "01") == date(year, 2, 29)
    assert close("303", "08") == date(year, 10, 2)
    assert close("303", "4T") == date(year + 1, 1, 30)
    assert close("390", "0A") == date(year + 1, 1, 30)


# ---------------------------------------------------------------------------
# Unknown close.
# ---------------------------------------------------------------------------


def test_a_year_without_a_published_calendar_has_an_unknown_close(operation: PinnedAuthorityOperation) -> None:
    period = Period.from_year_and_code(_FUTURE_YEAR, "1T")

    resolved = resolve_filing_window("303", _FUTURE_YEAR, period, authority=operation)

    assert isinstance(resolved, ProjectedFilingWindow)
    assert resolved.holiday_coverage is DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE
    assert resolved.shift_reason == CALENDAR_UNAVAILABLE_SHIFT_REASON
    assert resolved.opens_on == date(_FUTURE_YEAR, 4, 1)
    assert resolved.nominal_closes_on == date(_FUTURE_YEAR, 4, 20)
    assert resolved.closes_on == resolved.nominal_closes_on, "an unknown close keeps only its nominal date"
    effective = resolve_effective_filing_deadline("303", _FUTURE_YEAR, period, operation=operation)
    assert effective is not None
    assert effective.close_known is False


@pytest.mark.parametrize("code", ("1T", "10"))
def test_a_window_past_the_authored_horizon_resolves_against_the_published_calendar(
    code: str, operation: PinnedAuthorityOperation
) -> None:
    # The last year before the first unpublished calendar is published yet past the
    # authored horizon, so its windows are projected and shifted by that calendar's
    # national holidays.
    year = _FIRST_UNPUBLISHED_YEAR - 1
    assert year > filing_year_envelope().horizon, "no published calendar lies past the authored horizon"
    period = Period.from_year_and_code(year, code)
    published = holiday_calendar_from_authority(year, operation=operation)
    holidays = frozenset(holiday.holiday_date for holiday in published.national)

    window = resolve_filing_window("303", year, period, authority=operation)

    assert isinstance(window, ProjectedFilingWindow)
    assert window.nominal_closes_on == _oracle_nominal_close("303", period)
    assert window.closes_on == _oracle_close("303", period, holidays)


def test_a_walk_into_an_unpublished_year_has_an_unknown_close(operation: PinnedAuthorityOperation) -> None:
    # Monthly 11 of the future year closes Saturday 30 December; the walk enters the
    # next year, which this case leaves unpublished, so the close cannot be classified.
    period = Period.from_year_and_code(_FUTURE_YEAR, "11")

    projected = project_filing_window(operation, modelo="303", period=period, calendars=_FUTURE_CALENDARS[:1])

    assert isinstance(projected, ProjectedFilingWindow)
    assert projected.holiday_coverage is DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE
    assert projected.nominal_closes_on == date(_FUTURE_YEAR, 12, 30)
    assert projected.closes_on == projected.nominal_closes_on


def test_a_year_below_the_floor_projects_nothing(
    operation: PinnedAuthorityOperation, supplied_calendars: tuple[HolidayCalendar, ...]
) -> None:
    below = operation.supported_filing_years().floor - 1
    period = Period.from_year_and_code(below, "1T")

    assert project_filing_window(operation, modelo="303", period=period, calendars=supplied_calendars) is None


def _iva_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X0001500M",
        entity_type=EntityType.from_registry("natural_person"),
        irpf_income_categories=frozenset({IrpfIncomeCategory.from_registry("actividad_economica")}),
        irpf_estimation_regime=IrpfEstimationRegime.from_registry("directa_normal"),
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_professionals_with_retencion=False,
        art109_activity_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        fiscal_residency=FiscalResidency.from_registry("resident_irpf"),
        enrollment=ModeloEnrollment(large_company=False),
    )


def test_the_engine_reports_an_unknown_close_as_unknown_and_never_overdue(
    operation: PinnedAuthorityOperation,
) -> None:
    # A reference date past every nominal close of the future year.
    schedule = DeadlineEngine().compute(_iva_profile(), _FUTURE_YEAR, today=date(_FUTURE_YEAR + 1, 12, 31))

    rows = {(item.modelo, item.period.registry_token): item for item in schedule.obligations}
    first_quarter = rows[(Modelo("303"), "1T")]
    assert first_quarter.status is ObligationStatus.UNKNOWN
    assert first_quarter.holiday_coverage is DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE
    assert first_quarter.opens_on == date(_FUTURE_YEAR, 4, 1)
    assert first_quarter.closes_on == date(_FUTURE_YEAR, 4, 20)
    assert first_quarter.adjusted_closes_on == first_quarter.closes_on
    assert first_quarter.payment_cutoff_on is None
    assert first_quarter.recovery is None
    unshifted = [item for item in schedule.obligations if item.modelo in _MODELOS]
    assert unshifted, "the future year's Modelo 303 and 390 windows are dated obligations"
    assert all(item.status is ObligationStatus.UNKNOWN for item in unshifted), (
        "a future-year Modelo 303 or 390 window has no known close, so none is due or overdue"
    )
