"""Date membership at the registry's optional-upper validity window boundary."""

from collections.abc import Callable
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from ..schema_references import PeriodSelector, RegistryValidityWindow
from ..temporal import RevisionSelectionMetadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_START = date(2024, 1, 1)
_END = date(2024, 12, 31)


def _registry_window(valid_from: date, valid_to: date | None) -> RegistryValidityWindow:
    return RegistryValidityWindow(valid_from=valid_from, valid_to=valid_to)


def _revision_metadata(valid_from: date, valid_to: date | None) -> RevisionSelectionMetadata:
    return RevisionSelectionMetadata(
        id="2024",
        valid_from=valid_from,
        valid_to=valid_to,
        period_selector=PeriodSelector(year_from=2024, periods=("0A",)),
        filing_schedules=(),
    )


_WINDOW_FACTORIES: tuple[Callable[[date, date | None], RegistryValidityWindow | RevisionSelectionMetadata], ...] = (
    _registry_window,
    _revision_metadata,
)


@pytest.mark.parametrize("window_factory", _WINDOW_FACTORIES, ids=["registry-validity", "revision-metadata"])
@pytest.mark.parametrize(
    ("coordinate", "expected"),
    [
        (date(2023, 12, 31), False),
        (_START, True),
        (_END, True),
        (date(2025, 1, 1), False),
    ],
)
def test_contains_date_includes_finite_window_endpoints(
    window_factory: Callable[[date, date | None], RegistryValidityWindow | RevisionSelectionMetadata],
    coordinate: date,
    expected: bool,
) -> None:
    assert window_factory(_START, _END).contains_date(coordinate) is expected


@pytest.mark.parametrize("window_factory", _WINDOW_FACTORIES, ids=["registry-validity", "revision-metadata"])
def test_contains_date_accepts_later_dates_for_open_ended_windows(
    window_factory: Callable[[date, date | None], RegistryValidityWindow | RevisionSelectionMetadata],
) -> None:
    assert window_factory(_START, None).contains_date(date(2035, 6, 30))


@pytest.mark.parametrize("window_factory", _WINDOW_FACTORIES, ids=["registry-validity", "revision-metadata"])
def test_contains_date_preserves_native_error_for_a_datetime_coordinate(
    window_factory: Callable[[date, date | None], RegistryValidityWindow | RevisionSelectionMetadata],
) -> None:
    with pytest.raises(TypeError):
        window_factory(_START, _END).contains_date(datetime(2024, 6, 1))


def test_same_day_window_includes_its_only_date() -> None:
    assert _registry_window(_START, _START).contains_date(_START)
    assert _revision_metadata(_START, _START).contains_date(_START)


def test_registry_window_still_refuses_reversed_bounds() -> None:
    with pytest.raises(ValidationError, match="valid_to must be on or after valid_from"):
        RegistryValidityWindow(valid_from=_END, valid_to=_START)
