"""A typed year is read once, the same way on every surface."""

from __future__ import annotations

import pytest

from ..filing_year import FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST, four_digit_year_in

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("year", [FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST])
def test_four_ascii_digits_are_a_year(year: int) -> None:
    assert four_digit_year_in(f"  {year}\t") == year


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        f"-{FOUR_DIGIT_YEAR_FIRST}",
        f"+{FOUR_DIGIT_YEAR_FIRST}",
        str(FOUR_DIGIT_YEAR_FIRST)[:-1],
        str(FOUR_DIGIT_YEAR_LAST + 1),
        f"{str(FOUR_DIGIT_YEAR_FIRST)[:2]}_{str(FOUR_DIGIT_YEAR_FIRST)[2:]}",
        str(FOUR_DIGIT_YEAR_FIRST).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")),
        "²" * 4,
    ],
)
def test_anything_else_is_not_a_year(text: str) -> None:
    assert four_digit_year_in(text) is None
