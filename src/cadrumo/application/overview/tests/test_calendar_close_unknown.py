"""A projected window whose close is unknown is shown as unknown, never as due or overdue.

Modelo 303 for the first exercise without a published holiday calendar has no
authored window, so its close cannot be classified. The calendar shows the
opening and the nominal close (20 April for the first quarter, RD 1624/1992
art. 71.4) as a lower bound, and every date cohort leaves the row out.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.models import ObligationStatus
from ....domain.deadlines.tests.effective_close_scan import first_unpublished_calendar_year
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..agenda import build_overview_agenda
from ..backlog import build_overview_backlog
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendarEntry, OverviewCalendarRange, OverviewPeriodState
from .calendar_test_support import BUCKET_ID, profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

with bundled_indexed_authority().operation() as _pinned:
    _YEAR = first_unpublished_calendar_year(_pinned)
_FIRST_QUARTER = Period.from_year_and_code(_YEAR, "1T")
_NOMINAL_CLOSE = date(_YEAR, 4, 20)
_APRIL = OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 30))


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _first_quarter_303(entries: tuple[OverviewCalendarEntry, ...]) -> OverviewCalendarEntry:
    matches = [entry for entry in entries if entry.modelo == "303" and entry.period == _FIRST_QUARTER]
    assert len(matches) == 1, matches
    return matches[0]


def _work_unit() -> WorkUnit:
    revision_id = "close-unknown"
    created_at = datetime(_YEAR, 4, 2, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=BUCKET_ID,
            modelo=ModeloCode("303"),
            filing_year=_YEAR,
            period=_FIRST_QUARTER,
            revision_id=revision_id,
        ),
        bucket_id=BUCKET_ID,
        modelo=ModeloCode("303"),
        filing_year=_YEAR,
        period=_FIRST_QUARTER,
        revision_id=revision_id,
        name="close-unknown-303",
        created_at=created_at,
        updated_at=created_at,
    )


def test_the_calendar_row_shows_the_nominal_close_as_unknown_after_it_passes(
    operation: PinnedAuthorityOperation,
) -> None:
    calendar = build_overview_calendar(profile(), _APRIL, operation=operation, today=date(_YEAR, 6, 1))

    entry = _first_quarter_303(calendar.entries)
    assert entry.status is ObligationStatus.UNKNOWN
    assert entry.user_state is OverviewPeriodState.UNKNOWN
    assert entry.opens_on == date(_YEAR, 4, 1)
    assert entry.closes_on == _NOMINAL_CLOSE
    assert entry.adjusted_closes_on == _NOMINAL_CLOSE
    assert entry.holiday_coverage is DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE
    assert entry.days_overdue is None
    assert entry.recovery is None
    assert entry.payment_cutoff_on is None


def test_a_local_work_unit_keeps_the_unknown_close(operation: PinnedAuthorityOperation) -> None:
    calendar = build_overview_calendar(
        profile(), _APRIL, operation=operation, today=date(_YEAR, 6, 1), work_units=(_work_unit(),)
    )

    entry = _first_quarter_303(calendar.entries)
    assert entry.local_work_unit_id == _work_unit().work_unit_id
    assert entry.status is ObligationStatus.UNKNOWN
    assert entry.days_overdue is None


def test_the_agenda_makes_no_date_claim_for_an_unknown_close(operation: PinnedAuthorityOperation) -> None:
    # Five days before the nominal close: a dated window would be due soon.
    agenda = build_overview_agenda(profile(), as_of=date(_YEAR, 4, 15), operation=operation)

    cohorts = (*agenda.due_today, *agenda.due_soon, *agenda.overdue)
    assert all(entry.status is not ObligationStatus.UNKNOWN for entry in cohorts)
    assert not any(entry.modelo == "303" and entry.period == _FIRST_QUARTER for entry in cohorts)
    assert agenda.next_due is None or agenda.next_due.status is not ObligationStatus.UNKNOWN


def test_the_backlog_never_lists_an_unknown_close(operation: PinnedAuthorityOperation) -> None:
    backlog = build_overview_backlog(
        profile(), operation=operation, from_date=_APRIL.from_date, to_date=_APRIL.to_date, as_of=date(_YEAR, 6, 1)
    )

    assert not any(entry.modelo == "303" and entry.period == _FIRST_QUARTER for entry in backlog.items)
