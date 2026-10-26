"""The one repeated-coordinate refusal shared by every repeating-row channel."""

from __future__ import annotations

import pytest

from ..row_coordinate import index_unique_row_coordinates

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _BoundaryRefusalError(Exception):
    def __init__(self, coordinate: object) -> None:
        super().__init__(coordinate)
        self.coordinate = coordinate


def test_distinct_coordinates_are_indexed_in_supply_order() -> None:
    indexed = index_unique_row_coordinates(
        [(("b", 2), "second"), (("a", 1), "first"), (("b", 1), "third")],
        duplicate=_BoundaryRefusalError,
    )

    assert indexed == {("b", 2): "second", ("a", 1): "first", ("b", 1): "third"}
    assert list(indexed) == [("b", 2), ("a", 1), ("b", 1)]


def test_an_empty_channel_indexes_to_an_empty_mapping() -> None:
    assert index_unique_row_coordinates((), duplicate=_BoundaryRefusalError) == {}


def test_a_repeated_coordinate_raises_the_boundary_refusal_naming_it() -> None:
    with pytest.raises(_BoundaryRefusalError) as refused:
        index_unique_row_coordinates(
            [(("a", 1), "kept"), (("a", 2), "other"), (("a", 1), "rival")],
            duplicate=_BoundaryRefusalError,
        )

    assert refused.value.coordinate == ("a", 1)


def test_a_repeated_coordinate_is_refused_even_with_an_identical_value() -> None:
    with pytest.raises(_BoundaryRefusalError):
        index_unique_row_coordinates([(("a", 1), "same"), (("a", 1), "same")], duplicate=_BoundaryRefusalError)
