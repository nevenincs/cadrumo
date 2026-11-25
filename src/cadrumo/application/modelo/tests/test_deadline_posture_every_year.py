"""Every surface takes the same deadline posture, whichever supported year is filed.

The posture of a reference date against a declaration's close -- open, due,
overdue, in plazo or extemporánea -- has one owner,
:meth:`~cadrumo.domain.deadlines.effective_close.EffectiveFilingDeadline.posture_on`.
This module proves that the deadline schedule the overview reads, the overview
calendar row, the declaration editor's deadline, the calculate command's plazo
posture and the local filing receipt's timeliness all report it alike, for every
filing year the published support envelope admits, on a close the business-day
shift moves (Ley 39/2015 art. 30.5 through Ley 58/2003 art. 7.2) and on one it
does not.

Nothing here names a year, an edition or a date. The years come from the
envelope, the cases are scanned from each year's real schedule, and the
expected posture is plain day arithmetic on the effective close the schedule
publishes: on or before it the filer is in plazo with the days left to it,
after it the filer is that many days late.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from typing import NamedTuple

import pytest

from ....core.filing_timeliness import FilingTimeliness
from ....core.time.clock import MADRID_TZ
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.tests.published_authority import (
    published_selected_revision_id,
    published_supported_filing_years,
)
from ....domain.deadlines.effective_close import DEFAULT_DUE_SOON_DAYS, decide_filing_timeliness
from ....domain.deadlines.engine import DeadlineEngine, next_deadline
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.models import ModeloDeadline, ObligationStatus, Schedule, TaxpayerProfile
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...overview.calendar import build_overview_calendar
from ...overview.calendar_models import OverviewCalendarRange
from ...overview.tests.calendar_test_support import profile
from ..work_form_service import modelo_form_deadline
from ..work_plazo import modelo_work_deadline_posture

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "e" * 64
_DAY = timedelta(days=1)


def _supported_years() -> tuple[int, ...]:
    envelope = published_supported_filing_years()
    assert envelope is not None, "the published authority declares no supported filing years"
    return tuple(envelope.years)


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


@pytest.fixture(scope="module")
def taxpayer() -> TaxpayerProfile:
    return profile()


class _Posture(NamedTuple):
    """One surface's answer, reduced to what every surface states."""

    effective_close: date
    overdue: bool
    days_remaining: int | None
    days_overdue: int | None


def _expected(effective_close: date, reference_on: date) -> _Posture:
    """The posture worked by hand from the effective close: no resolver is consulted."""
    if reference_on > effective_close:
        return _Posture(effective_close, True, None, (reference_on - effective_close).days)
    return _Posture(effective_close, False, (effective_close - reference_on).days, None)


def _known_obligations(
    engine: DeadlineEngine, taxpayer: TaxpayerProfile, filing_year: int
) -> tuple[ModeloDeadline, ...]:
    schedule = engine.compute(taxpayer, filing_year, today=date(filing_year, 1, 1))
    return tuple(
        row
        for row in schedule.obligations
        if row.holiday_coverage is DeadlineHolidayCoverage.NATIONAL_ONLY and row.period.filing_year == filing_year
    )


def _cases(
    operation: PinnedAuthorityOperation, taxpayer: TaxpayerProfile, filing_year: int
) -> dict[str, ModeloDeadline]:
    """The first shifted and the first unshifted close of the year's real schedule."""
    rows = _known_obligations(DeadlineEngine(authority=operation), taxpayer, filing_year)
    shifted = next((row for row in rows if row.adjusted_closes_on > row.closes_on), None)
    unshifted = next((row for row in rows if row.adjusted_closes_on == row.closes_on), None)
    assert shifted is not None, f"filing year {filing_year} has no verified close the business-day shift moves"
    assert unshifted is not None, f"filing year {filing_year} has no verified close that stands unshifted"
    return {"shifted": shifted, "unshifted": unshifted}


def _work_unit(obligation: ModeloDeadline) -> WorkUnit:
    period = obligation.period
    revision_id = published_selected_revision_id(
        str(obligation.modelo), filing_year=period.filing_year, period=period.registry_token
    )
    created = datetime.combine(obligation.opens_on, time(), tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=str(obligation.modelo),
            filing_year=period.filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(str(obligation.modelo)),
        filing_year=period.filing_year,
        period=period,
        revision_id=revision_id,
        name=f"posture-{obligation.modelo}-{period.registry_token}",
        created_at=created,
        updated_at=created,
    )


def _schedule_posture(
    obligation: ModeloDeadline, reference_on: date, operation: PinnedAuthorityOperation, taxpayer: TaxpayerProfile
) -> _Posture:
    schedule = DeadlineEngine(authority=operation).compute(taxpayer, obligation.period.filing_year, today=reference_on)
    rows = [row for row in schedule.obligations if row.modelo == obligation.modelo and row.period == obligation.period]
    assert len(rows) == 1
    row = rows[0]
    overdue = row.status is ObligationStatus.OVERDUE
    if not overdue:
        assert row.status in {ObligationStatus.UPCOMING, ObligationStatus.DUE_SOON, ObligationStatus.DUE_TODAY}
        expected_open = (
            ObligationStatus.DUE_TODAY
            if reference_on == row.adjusted_closes_on
            else ObligationStatus.DUE_SOON
            if (row.adjusted_closes_on - reference_on).days <= DEFAULT_DUE_SOON_DAYS
            else ObligationStatus.UPCOMING
        )
        assert row.status is expected_open
    remaining = (row.adjusted_closes_on - reference_on).days if not overdue else None
    days_overdue = (reference_on - row.adjusted_closes_on).days if overdue else None
    return _Posture(row.adjusted_closes_on, overdue, remaining, days_overdue)


def _calendar_posture(
    obligation: ModeloDeadline, reference_on: date, operation: PinnedAuthorityOperation, taxpayer: TaxpayerProfile
) -> _Posture:
    calendar = build_overview_calendar(
        taxpayer,
        OverviewCalendarRange(from_date=obligation.closes_on, to_date=obligation.adjusted_closes_on + _DAY),
        operation=operation,
        today=reference_on,
        engine=DeadlineEngine(authority=operation),
        work_units=(_work_unit(obligation),),
    )
    rows = [
        entry
        for entry in calendar.entries
        if entry.modelo == str(obligation.modelo) and entry.period == obligation.period
    ]
    assert len(rows) == 1, f"the calendar lists Modelo {obligation.modelo} {obligation.period} once"
    row = rows[0]
    overdue = row.status is ObligationStatus.OVERDUE
    remaining = None if overdue else (row.adjusted_closes_on - reference_on).days
    return _Posture(row.adjusted_closes_on, overdue, remaining, row.days_overdue)


def _form_posture(obligation: ModeloDeadline, reference_on: date, operation: PinnedAuthorityOperation) -> _Posture:
    deadline = modelo_form_deadline(
        operation, ModeloCode(str(obligation.modelo)), obligation.period, reference_on=reference_on
    )
    assert deadline is not None
    return _Posture(
        deadline.closes_on, deadline.days_overdue is not None, deadline.days_remaining, deadline.days_overdue
    )


def _plazo_posture(obligation: ModeloDeadline, reference_on: date, operation: PinnedAuthorityOperation) -> _Posture:
    posture = modelo_work_deadline_posture(_work_unit(obligation), reference_on=reference_on, operation=operation)
    assert posture is not None
    return _Posture(posture.closes_on, posture.days_overdue is not None, posture.days_remaining, posture.days_overdue)


def _receipt_overdue(obligation: ModeloDeadline, presented_on: date, operation: PinnedAuthorityOperation) -> bool:
    timeliness = decide_filing_timeliness(
        modelo=str(obligation.modelo),
        filing_year=obligation.period.filing_year,
        period=obligation.period,
        filed_at=datetime.combine(presented_on, time(12), tzinfo=MADRID_TZ),
        operation=operation,
    )
    assert timeliness is not FilingTimeliness.UNKNOWN, "a verified close always decides the receipt's posture"
    return timeliness is FilingTimeliness.EXTEMPORANEA


def _reference_dates(obligation: ModeloDeadline) -> tuple[date, ...]:
    """The days either side of both closes: a shifted close puts its nominal day inside the plazo."""
    return tuple(
        sorted(
            {
                obligation.closes_on - _DAY,
                obligation.closes_on,
                obligation.closes_on + _DAY,
                obligation.adjusted_closes_on,
                obligation.adjusted_closes_on + _DAY,
            }
        )
    )


@pytest.mark.parametrize("filing_year", _supported_years(), ids=str)
def test_every_surface_takes_one_posture_in_every_supported_year(
    filing_year: int, operation: PinnedAuthorityOperation, taxpayer: TaxpayerProfile
) -> None:
    for kind, obligation in _cases(operation, taxpayer, filing_year).items():
        for reference_on in _reference_dates(obligation):
            expected = _expected(obligation.adjusted_closes_on, reference_on)
            surfaces = {
                "schedule": _schedule_posture(obligation, reference_on, operation, taxpayer),
                "calendar": _calendar_posture(obligation, reference_on, operation, taxpayer),
                "form": _form_posture(obligation, reference_on, operation),
                "plazo": _plazo_posture(obligation, reference_on, operation),
            }
            for surface, posture in surfaces.items():
                assert posture == expected, (
                    f"{filing_year} {kind} Modelo {obligation.modelo} {obligation.period} on {reference_on}: "
                    f"{surface} says {posture}, expected {expected}"
                )
            assert _receipt_overdue(obligation, reference_on, operation) is expected.overdue, (
                f"{filing_year} {kind} receipt on {reference_on}"
            )


@pytest.mark.parametrize("filing_year", _supported_years(), ids=str)
def test_the_day_after_a_shifted_nominal_close_is_still_open_on_every_surface(
    filing_year: int, operation: PinnedAuthorityOperation, taxpayer: TaxpayerProfile
) -> None:
    """The regression a nominal-close classification fails: the filer still has the moved day.

    The schedule must also still offer this obligation as the next deadline on
    that day; selecting by the nominal close dropped it.
    """
    shifted = _cases(operation, taxpayer, filing_year)["shifted"]
    reference_on = shifted.closes_on + _DAY
    assert reference_on <= shifted.adjusted_closes_on

    assert _schedule_posture(shifted, reference_on, operation, taxpayer).overdue is False
    assert _calendar_posture(shifted, reference_on, operation, taxpayer).overdue is False
    assert _form_posture(shifted, reference_on, operation).overdue is False
    assert _plazo_posture(shifted, reference_on, operation).overdue is False
    assert _receipt_overdue(shifted, reference_on, operation) is False

    only_shifted = Schedule(profile=taxpayer, year=filing_year, obligations=(shifted,), generated_at=datetime.now(UTC))
    assert next_deadline(only_shifted, today=reference_on) == shifted


def _unknown_close_obligation(operation: PinnedAuthorityOperation, taxpayer: TaxpayerProfile) -> ModeloDeadline:
    """Scan the years past the horizon for a close whose shift calendar is not yet published.

    Such a year is answered by projection from the nearest edition. The scan
    stops at the first one, so it names no year; a registry that publishes
    every calendar the scan reaches fails it loudly rather than passing empty.
    """
    envelope = published_supported_filing_years()
    assert envelope is not None
    engine = DeadlineEngine(authority=operation)
    for filing_year in range(envelope.horizon + 1, envelope.horizon + 1 + len(envelope.years)):
        schedule = engine.compute(taxpayer, filing_year, today=date(filing_year, 1, 1))
        for row in schedule.obligations:
            if row.holiday_coverage is DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE:
                return row
    raise AssertionError("no projected year past the horizon reaches an unpublished holiday calendar")


def test_an_unknown_close_is_unknown_on_every_surface_and_never_overdue(
    operation: PinnedAuthorityOperation, taxpayer: TaxpayerProfile
) -> None:
    """A close whose holiday calendar is unpublished is judged the same way on every surface.

    Before its nominal date the filer is in plazo with at least the days to it;
    after it nothing is judged. The editor and the plazo posture called it
    overdue while the schedule, the calendar and the receipt called it unknown.
    """
    obligation = _unknown_close_obligation(operation, taxpayer)
    nominal = obligation.closes_on
    year = obligation.period.filing_year
    engine = DeadlineEngine(authority=operation)

    for reference_on in (nominal - _DAY, nominal + _DAY):
        rows = [
            row
            for row in engine.compute(taxpayer, year, today=reference_on).obligations
            if row.modelo == obligation.modelo and row.period == obligation.period
        ]
        assert [row.status for row in rows] == [ObligationStatus.UNKNOWN]
        calendar = build_overview_calendar(
            taxpayer,
            OverviewCalendarRange(from_date=nominal, to_date=nominal + _DAY),
            operation=operation,
            today=reference_on,
            engine=engine,
            work_units=(_work_unit(obligation),),
        )
        entries = [
            entry
            for entry in calendar.entries
            if entry.modelo == str(obligation.modelo) and entry.period == obligation.period
        ]
        assert [(entry.status, entry.days_overdue) for entry in entries] == [(ObligationStatus.UNKNOWN, None)]

        form = modelo_form_deadline(
            operation, ModeloCode(str(obligation.modelo)), obligation.period, reference_on=reference_on
        )
        plazo = modelo_work_deadline_posture(_work_unit(obligation), reference_on=reference_on, operation=operation)
        timeliness = decide_filing_timeliness(
            modelo=str(obligation.modelo),
            filing_year=year,
            period=obligation.period,
            filed_at=datetime.combine(reference_on, time(12), tzinfo=MADRID_TZ),
            operation=operation,
        )
        if reference_on < nominal:
            assert form is not None and (form.days_remaining, form.days_overdue) == (1, None)
            assert plazo is not None and (plazo.days_remaining, plazo.days_overdue) == (1, None)
            assert timeliness is FilingTimeliness.EN_PLAZO
        else:
            assert form is None, "past an unknown close's lower bound the editor states no deadline"
            assert plazo is None, "past an unknown close's lower bound no plazo posture is stated"
            assert timeliness is FilingTimeliness.UNKNOWN
