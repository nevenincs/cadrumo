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
from ...contribuyente.entity_type import EntityType
from ...contribuyente.renta_codes import FiscalResidency
from ..engine import DeadlineEngine, indexed_deadline_window_year
from ..festivos import DeadlineHolidayCoverage, Holiday, HolidayCalendar, HolidayJurisdiction
from ..filing_window_projection import (
    AuthoredFilingWindow,
    FilingCloseInhabilBasis,
    FilingWindowClause,
    FilingWindowCloseUnavailableReason,
    FilingWindowOpening,
    ProjectedFilingWindow,
    ProjectedFilingWindowCloseUnavailable,
    ProjectedFilingWindowResolution,
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
) -> ProjectedFilingWindowResolution | None:
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


def _national(year: int, *days: tuple[int, int]) -> HolidayCalendar:
    return HolidayCalendar(
        year=year,
        boe_ref=f"test-national-{year}",
        national=tuple(
            Holiday(holiday_date=date(year, month, day), jurisdiction=HolidayJurisdiction.NATIONAL, name="fiesta")
            for month, day in days
        ),
    )


# Fiestas laborales de ámbito nacional for the years the authority does not
# publish. 2022: BOE-A-2021-17113; 2023: BOE-A-2022-17112.
_SUPPLIED_CALENDARS = (
    _national(2022, (1, 1), (1, 6), (4, 15), (8, 15), (10, 12), (11, 1), (12, 6), (12, 8)),
    _national(2023, (1, 6), (4, 7), (5, 1), (8, 15), (10, 12), (11, 1), (12, 6), (12, 8), (12, 25)),
)

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

    assert month_end.nominal_close(date(2028, 1, 31)) == date(2028, 2, 29)
    assert month_end.nominal_close(date(2027, 1, 31)) == date(2027, 2, 28)
    assert thirtieth.nominal_close(date(2027, 12, 31)) == date(2028, 1, 30)
    assert thirtieth.opens_on(date(2027, 12, 31)) == date(2028, 1, 1)


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


def test_every_authored_303_and_390_window_agrees_with_the_rule(operation: PinnedAuthorityOperation) -> None:
    rows = _authored_rows(operation)
    support = operation.supported_filing_years()
    # Sixteen Modelo 303 periods and one Modelo 390 summary per authored year.
    assert len(rows) == (support.horizon - support.floor + 1) * 17, len(rows)

    disagreements: set[tuple[str, int, str]] = set()
    for modelo, period, opens_on, closes_on in rows:
        projected = project_filing_window(operation, modelo=modelo, period=period, calendars=_SUPPLIED_CALENDARS)
        assert isinstance(projected, ProjectedFilingWindow), (modelo, period, projected)
        assert projected.opens_on == opens_on, (modelo, period)
        if projected.closes_on != closes_on:
            disagreements.add((modelo, period.filing_year, period.registry_token))

    assert disagreements == set()


# RD 439/2007 art. 108.1 (withholding: the 20th of the month after the quarter or
# month) and art. 111.1 (pagos fraccionados: the 20th, and 30 January for the
# fourth quarter). Only modelos with a filing schedule are projected.
_RIRPF_SCHEDULED_MODELOS = ("111", "115", "123", "130", "131")


def test_every_authored_rirpf_window_agrees_with_the_rule(operation: PinnedAuthorityOperation) -> None:
    support = operation.supported_filing_years()
    checked: set[str] = set()
    disagreements: set[tuple[str, int, str]] = set()
    for year in range(support.floor, support.horizon + 1):
        index = indexed_deadline_window_year(operation, year)
        for modelo, _revision, window in index.dated:
            if modelo not in _RIRPF_SCHEDULED_MODELOS or window.id in index.projected:
                continue
            projected = project_filing_window(
                operation, modelo=modelo, period=window.period, calendars=_SUPPLIED_CALENDARS
            )
            assert isinstance(projected, ProjectedFilingWindow), (modelo, window.period, projected)
            assert projected.opens_on == window.opens_on, (modelo, window.period)
            checked.add(modelo)
            if projected.closes_on != window.closes_on:
                disagreements.add((modelo, window.period.filing_year, window.period.registry_token))

    assert checked == set(_RIRPF_SCHEDULED_MODELOS)
    assert disagreements == set(), sorted(disagreements)


def test_the_390_2026_authored_close_is_the_weekend_shifted_monday(operation: PinnedAuthorityOperation) -> None:
    period = Period.from_year_and_code(2026, "0A")
    authored = resolve_filing_window("390", 2026, period, authority=operation)
    projected = project_filing_window(operation, modelo="390", period=period, calendars=_SUPPLIED_CALENDARS)

    assert isinstance(authored, AuthoredFilingWindow)
    assert authored.closes_on == date(2027, 2, 1)  # nominal Saturday 30 January moved by art. 30.5
    assert isinstance(projected, ProjectedFilingWindow)
    assert projected.nominal_closes_on == date(2027, 1, 30)
    assert projected.closes_on == date(2027, 2, 1)


# ---------------------------------------------------------------------------
# Precedence: an authored window always wins.
# ---------------------------------------------------------------------------


def test_an_authored_window_wins_over_a_differing_projection(operation: PinnedAuthorityOperation) -> None:
    # 1T 2024: 20 April is a Saturday, so AEAT published Monday 22 April. A
    # calendar that also marks the 22nd inhábil moves the projection to the
    # 23rd, while the resolver keeps the authored date.
    period = Period.from_year_and_code(2024, "1T")
    marked_2024 = _national(2024, (1, 1), (1, 6), (3, 29), (4, 22), (5, 1), (8, 15), (10, 12), (11, 1))

    projected = project_filing_window(operation, modelo="303", period=period, calendars=(marked_2024,))
    resolved = resolve_filing_window("303", 2024, period, authority=operation)

    assert isinstance(projected, ProjectedFilingWindow)
    assert projected.closes_on == date(2024, 4, 23)
    assert isinstance(resolved, AuthoredFilingWindow)
    assert resolved.closes_on == date(2024, 4, 22)


# ---------------------------------------------------------------------------
# Future years.
# ---------------------------------------------------------------------------

# Synthetic calendars for 2028 and 2029. The statutory fixed national holidays
# are joined by a holiday placed on Thursday 20 April 2028, so a weekday close
# is moved by a holiday and not only by a weekend.
_FUTURE_CALENDARS = (
    _national(2028, (1, 1), (1, 6), (4, 14), (4, 20), (5, 1), (8, 15), (10, 12), (11, 1), (12, 6), (12, 8), (12, 25)),
    _national(2029, (1, 1), (1, 6)),
)
_FUTURE_HOLIDAYS = frozenset(holiday.holiday_date for cal in _FUTURE_CALENDARS for holiday in cal.national)
_303_PERIODS = ("1T", "2T", "3T", "4T", *(f"{month:02d}" for month in range(1, 13)))


@pytest.mark.parametrize(("modelo", "code"), [*(("303", code) for code in _303_PERIODS), ("390", "0A")])
def test_a_future_year_projects_the_rule_with_the_national_shift(
    modelo: str,
    code: str,
    operation: PinnedAuthorityOperation,
) -> None:
    period = Period.from_year_and_code(2028, code)

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


def test_the_oracle_matches_hand_worked_2028_closes() -> None:
    # From a perpetual calendar: 20 April 2028 is a Thursday (the synthetic
    # holiday moves it to Friday 21); 20 July a Thursday; 29 February 2028 a
    # Tuesday; 30 September 2028 a Saturday (Monday 2 October); 30 January 2029
    # a Tuesday.
    def close(modelo: str, code: str) -> date:
        return _oracle_close(modelo, Period.from_year_and_code(2028, code), _FUTURE_HOLIDAYS)

    assert close("303", "1T") == date(2028, 4, 21)
    assert close("303", "2T") == date(2028, 7, 20)
    assert close("303", "01") == date(2028, 2, 29)
    assert close("303", "08") == date(2028, 10, 2)
    assert close("303", "4T") == date(2029, 1, 30)
    assert close("390", "0A") == date(2029, 1, 30)


# ---------------------------------------------------------------------------
# Unknown close.
# ---------------------------------------------------------------------------


def test_a_year_without_a_published_calendar_has_an_unknown_close(operation: PinnedAuthorityOperation) -> None:
    period = Period.from_year_and_code(2028, "1T")

    resolved = resolve_filing_window("303", 2028, period, authority=operation)

    assert isinstance(resolved, ProjectedFilingWindowCloseUnavailable)
    assert resolved.reason is FilingWindowCloseUnavailableReason.HOLIDAY_CALENDAR_UNAVAILABLE
    assert resolved.opens_on == date(2028, 4, 1)
    assert resolved.nominal_closes_on == date(2028, 4, 20)
    assert resolved.closes_on is None
    assert resolved.dated_window is None


def test_a_2027_window_resolves_against_the_published_2027_calendar(operation: PinnedAuthorityOperation) -> None:
    # 20 April 2027 is a Tuesday and 30 December 2027 a Thursday, and neither is
    # a national inhábil day, so each nominal close stands.
    quarter = resolve_filing_window("303", 2027, Period.from_year_and_code(2027, "1T"), authority=operation)
    month = resolve_filing_window("303", 2027, Period.from_year_and_code(2027, "11"), authority=operation)

    assert isinstance(quarter, ProjectedFilingWindow)
    assert quarter.nominal_closes_on == date(2027, 4, 20)
    assert quarter.closes_on == date(2027, 4, 20)
    assert isinstance(month, ProjectedFilingWindow)
    assert month.closes_on == date(2027, 12, 30)


def test_a_walk_into_an_unpublished_year_has_an_unknown_close(operation: PinnedAuthorityOperation) -> None:
    # Monthly 11 of 2028 closes Saturday 30 December 2028; the walk enters 2029,
    # which this case leaves unpublished, so the close cannot be classified.
    period = Period.from_year_and_code(2028, "11")

    projected = project_filing_window(operation, modelo="303", period=period, calendars=_FUTURE_CALENDARS[:1])

    assert isinstance(projected, ProjectedFilingWindowCloseUnavailable)
    assert projected.nominal_closes_on == date(2028, 12, 30)


def test_a_year_below_the_floor_projects_nothing(operation: PinnedAuthorityOperation) -> None:
    below = operation.supported_filing_years().floor - 1
    period = Period.from_year_and_code(below, "1T")

    assert project_filing_window(operation, modelo="303", period=period, calendars=_SUPPLIED_CALENDARS) is None


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
    # A reference date past every nominal close of 2028.
    schedule = DeadlineEngine().compute(_iva_profile(), 2028, today=date(2029, 12, 31))

    unknown = {(item.modelo, item.period.registry_token): item for item in schedule.close_unknown_obligations}
    first_quarter = unknown[(Modelo("303"), "1T")]
    assert first_quarter.status is ObligationStatus.UNKNOWN
    assert first_quarter.opens_on == date(2028, 4, 1)
    assert first_quarter.nominal_closes_on == date(2028, 4, 20)
    assert first_quarter.close_unavailable_reason == FilingWindowCloseUnavailableReason.HOLIDAY_CALENDAR_UNAVAILABLE
    dated_303 = [item for item in schedule.obligations if item.modelo in _MODELOS]
    assert dated_303 == [], "a 2028 Modelo 303 or 390 window has no known close, so none is dated or overdue"
