"""Contract test for the A1 column-letter conversion helper.

The pull adapter uses `column_index_to_letters` to build the Sheets
batchGet range for each row-set's data block. Off-by-one or wrong
boundary handling would either skip columns silently or fetch
columns the engine never wrote — a class of silent-loss bug that
the engine + apply + pull tests don't otherwise catch.
"""

from __future__ import annotations

import pytest

from .....application.storage.calc_sheets._records import column_index_to_letters

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def testcolumn_index_to_letters_at_boundaries() -> None:
    cases: tuple[tuple[int, str], ...] = (
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
    )

    for column, expected in cases:
        assert column_index_to_letters(column) == expected, column


def testcolumn_index_to_letters_rejects_non_positive_values() -> None:
    cases: tuple[tuple[str, int], ...] = (
        ("zero", 0),
        ("negative", -1),
    )

    for case_id, column in cases:
        try:
            column_index_to_letters(column)
        except ValueError as exc:
            assert "must be 1-based and positive" in str(exc), case_id
        else:
            pytest.fail(f"{case_id}: expected ValueError")
