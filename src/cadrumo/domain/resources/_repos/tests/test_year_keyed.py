"""Real-behaviour tests for year-keyed resource repositories."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.deadlines.festivos import HolidayCalendar

from .....core.resources.errors import ResourceNotFoundError
from ..holiday_calendars import HolidayCalendarRepository
from ..iva_catalogues import IvaCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_holiday_calendar_resolves_years_within_one_pinned_operation() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        generation = _authority_operation_for_test.pin()
        repo = HolidayCalendarRepository()

        cal_2025 = repo.get(2025, operation=_authority_operation_for_test)
        cal_2025_again = repo.get(2025, operation=_authority_operation_for_test)
        cal_2024 = repo.get(2024, operation=_authority_operation_for_test)

        assert isinstance(cal_2025, HolidayCalendar)
        assert isinstance(cal_2025_again, HolidayCalendar)
        assert isinstance(cal_2024, HolidayCalendar)
        assert cal_2025.year == cal_2025_again.year == 2025
        assert cal_2025 == cal_2025_again
        assert cal_2025 is not cal_2025_again  # The repository does not cache domain projections.
        assert cal_2024.year == 2024
        assert cal_2024 != cal_2025
        assert cal_2024 is not cal_2025

        repo.clear_cache()
        cal_2025_after_clear = repo.get(2025, operation=_authority_operation_for_test)

        assert isinstance(cal_2025_after_clear, HolidayCalendar)
        assert cal_2025_after_clear == cal_2025
        assert cal_2025_after_clear is not cal_2025
        assert _authority_operation_for_test.pin() == generation


def test_iva_catalogue_loads_real_year() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        repo = IvaCatalogueRepository()

        catalogue = repo.get(2025, operation=_authority_operation_for_test)
        catalogue_again = repo.get(2025, operation=_authority_operation_for_test)

        assert catalogue is not None
        assert catalogue == catalogue_again
        assert catalogue is not catalogue_again


def test_iva_catalogue_unknown_year_raises_resource_not_found() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        repo = IvaCatalogueRepository()

        with pytest.raises(ResourceNotFoundError):
            repo.get(1801, operation=_authority_operation_for_test)
