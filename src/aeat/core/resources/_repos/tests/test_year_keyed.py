"""Real-behaviour tests for the three year-keyed Repositories."""

from __future__ import annotations

import pytest

from ..._errors import ResourceNotFoundError
from .. import (
    CategoryProfileRepository,
    HolidayCalendarRepository,
    IvaCatalogueRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_holiday_calendar_loads_real_year() -> None:
    repo = HolidayCalendarRepository()

    cal_2025 = repo.get(2025)
    cal_2025_again = repo.get(2025)

    assert cal_2025 is not None
    assert cal_2025 is cal_2025_again  # Identity Map cached


def test_holiday_calendar_distinct_years_yield_distinct_values() -> None:
    repo = HolidayCalendarRepository()

    cal_2024 = repo.get(2024)
    cal_2025 = repo.get(2025)

    assert cal_2024 is not cal_2025


def test_category_profile_loads_real_year() -> None:
    repo = CategoryProfileRepository()

    profiles_2025 = repo.get(2025)
    profiles_2025_again = repo.get(2025)

    assert profiles_2025 is not None
    assert len(profiles_2025) > 0
    assert profiles_2025 is profiles_2025_again


def test_iva_catalogue_loads_real_year() -> None:
    repo = IvaCatalogueRepository()

    catalogue = repo.get(2025)
    catalogue_again = repo.get(2025)

    assert catalogue is not None
    assert catalogue is catalogue_again


def test_iva_catalogue_unknown_year_raises_resource_not_found() -> None:
    repo = IvaCatalogueRepository()

    with pytest.raises(ResourceNotFoundError):
        repo.get(1801)


def test_year_keyed_clear_cache_empties_identity_map() -> None:
    repo = HolidayCalendarRepository()
    repo.get(2025)
    repo.clear_cache()

    assert repo._cache == {}
