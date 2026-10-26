"""ISO 6166 ISIN shape and check digit.

The positive cases are published ISINs whose check digits were assigned by their
national numbering agencies, so they are an oracle independent of the Luhn code
under test.
"""

from __future__ import annotations

import pytest

from ..isin import is_valid_isin, isin_check_digit

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PUBLISHED_ISINS = ("US0378331005", "ES0178430E18", "DE0005190003", "CH0038863350")


@pytest.mark.parametrize("isin", _PUBLISHED_ISINS)
def test_a_published_isin_verifies(isin: str) -> None:
    assert is_valid_isin(isin)
    assert isin_check_digit(isin[:11]) == int(isin[11])


@pytest.mark.parametrize("isin", _PUBLISHED_ISINS)
def test_any_other_check_digit_is_refused(isin: str) -> None:
    for digit in "0123456789":
        if digit != isin[11]:
            assert not is_valid_isin(isin[:11] + digit)


@pytest.mark.parametrize(
    "value",
    ("us0378331005", "US037833100", "US03783310055", "1S0378331005", "US037833100A", "US 378331005"),
)
def test_a_malformed_isin_is_refused(value: str) -> None:
    assert not is_valid_isin(value)
