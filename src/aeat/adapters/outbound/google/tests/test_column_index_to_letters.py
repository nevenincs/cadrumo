"""Contract test for the A1 column-letter conversion helper.

The pull adapter uses `_column_index_to_letters` to build the Sheets
batchGet range for each row-set's data block. Off-by-one or wrong
boundary handling would either skip columns silently or fetch
columns the engine never wrote — a class of silent-loss bug that
the engine + apply + pull tests don't otherwise catch.
"""

from __future__ import annotations

import pytest

from .._calc_sheets_pull import _column_index_to_letters

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize(
    "column,expected",
    [
        (1, "A"),
        (2, "B"),
        (25, "Y"),
        (26, "Z"),
        (27, "AA"),
        (28, "AB"),
        (51, "AY"),
        (52, "AZ"),
        (53, "BA"),
        (78, "BZ"),
        (79, "CA"),
        (701, "ZY"),
        (702, "ZZ"),
        (703, "AAA"),
    ],
)
def test_column_index_to_letters_at_boundaries(column: int, expected: str) -> None:
    assert _column_index_to_letters(column) == expected


def test_column_index_to_letters_rejects_zero() -> None:
    with pytest.raises(ValueError, match="must be 1-based and positive"):
        _column_index_to_letters(0)


def test_column_index_to_letters_rejects_negative() -> None:
    with pytest.raises(ValueError, match="must be 1-based and positive"):
        _column_index_to_letters(-1)
