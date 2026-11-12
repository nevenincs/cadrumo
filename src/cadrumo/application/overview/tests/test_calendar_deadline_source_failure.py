"""A deadline source that cannot resolve a year is reported unknown, never as an empty calendar."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from typing import override

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ....domain.deadlines.engine import DeadlineEngine
from ....domain.deadlines.errors import NoDeadlineWindowsError
from ....domain.deadlines.models import Schedule, TaxpayerProfile
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendarRange
from .calendar_test_support import profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WARNING_PREFIX = "deadline.windows_unavailable"
_YEAR = newest_authored_edition("303")


class _WindowlessYearEngine(DeadlineEngine):
    """The real engine, except that the registry has no windows for one year."""

    def __init__(self, *, authority: PinnedAuthorityOperation, windowless_year: int) -> None:
        super().__init__(authority=authority)
        self._windowless_year = windowless_year

    @override
    def compute(self, profile: TaxpayerProfile, year: int, *, today: date | None = None) -> Schedule:
        if year == self._windowless_year:
            raise NoDeadlineWindowsError(
                translated_message="application.overview.calendar.shift.modelo_exception",
                context={"filing_year": year},
            )
        return super().compute(profile, year, today=today)


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _unavailable_codes(warning_codes: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(code for code in warning_codes if code.startswith(_WARNING_PREFIX))


def test_year_without_deadline_windows_is_reported_unavailable_not_empty(
    operation: PinnedAuthorityOperation,
) -> None:
    rng = OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 30))

    calendar = build_overview_calendar(
        profile(),
        rng,
        operation=operation,
        today=date(_YEAR, 4, 1),
        engine=_WindowlessYearEngine(authority=operation, windowless_year=_YEAR),
    )

    codes = _unavailable_codes(tuple(warning.code for warning in calendar.warnings))
    assert codes == (f"{_WARNING_PREFIX}.{_YEAR}",)
    assert calendar.taxpayer_model_declared is True
    assert not [entry for entry in calendar.entries if entry.filing_year == _YEAR]


def test_resolvable_years_still_answer_when_another_year_is_unavailable(
    operation: PinnedAuthorityOperation,
) -> None:
    rng = OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 30))
    resolved = build_overview_calendar(profile(), rng, operation=operation, today=date(_YEAR, 4, 1))
    resolved_rows = {(e.modelo, e.period) for e in resolved.entries if e.filing_year == _YEAR}
    assert resolved_rows, "the control range holds no obligation, so this proves nothing"

    degraded = build_overview_calendar(
        profile(),
        rng,
        operation=operation,
        today=date(_YEAR, 4, 1),
        engine=_WindowlessYearEngine(authority=operation, windowless_year=_YEAR - 1),
    )

    assert {(e.modelo, e.period) for e in degraded.entries if e.filing_year == _YEAR} == resolved_rows


def test_genuinely_empty_range_carries_no_unavailable_warning(operation: PinnedAuthorityOperation) -> None:
    """A range the registry resolves and that holds no deadline stays empty and unwarned."""
    start = date(_YEAR, 8, 2)
    rng = OverviewCalendarRange(from_date=start, to_date=start + timedelta(days=1))

    calendar = build_overview_calendar(profile(), rng, operation=operation, today=start)

    assert calendar.entries == ()
    assert _unavailable_codes(tuple(warning.code for warning in calendar.warnings)) == ()
