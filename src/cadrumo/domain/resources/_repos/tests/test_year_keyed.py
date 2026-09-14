"""Real-behaviour tests for year-keyed resource repositories."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from .....core.resources.errors import ResourceNotFoundError
from ..holiday_calendars import HolidayCalendarRepository
from ..iva_catalogues import IvaCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_holiday_calendar_loads_distinct_years_and_clears_identity_map() -> None:
    repo = HolidayCalendarRepository()

    cal_2025 = repo.get(2025)
    cal_2025_again = repo.get(2025)
    cal_2024 = repo.get(2024)

    assert cal_2025 is not None
    assert cal_2025 is cal_2025_again  # Identity Map cached
    assert cal_2024 is not cal_2025

    repo.clear_cache()
    assert repo._cache == {}


def test_iva_catalogue_loads_real_year() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        repo = IvaCatalogueRepository()

        catalogue = repo.get(2025, operation=_authority_operation_for_test)
        catalogue_again = repo.get(2025, operation=_authority_operation_for_test)

        assert catalogue is not None
        assert catalogue == catalogue_again
        assert catalogue is not catalogue_again
        assert not hasattr(repo, "_cache")


def test_iva_catalogue_unknown_year_raises_resource_not_found() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        repo = IvaCatalogueRepository()

        with pytest.raises(ResourceNotFoundError):
            repo.get(1801, operation=_authority_operation_for_test)
