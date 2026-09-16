"""Real-behaviour tests for :func:`cadrumo.core.decimal.printed_units.without_currency_unit`.

The rule removes only a unit it can name -- a closed symbol set, or the currency
code the document itself reported -- and leaves every other token for the
decimal authority to refuse.
"""

from __future__ import annotations

import pytest

from ..coercion import coerce_finite_european_decimal
from ..printed_units import CURRENCY_UNIT_SYMBOLS, without_currency_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("1200.00 EUR", "1200.00"),
        ("EUR 1200.00", "1200.00"),
        ("1200.00 eur", "1200.00"),
        ("  1.200,00  EUR ", "1.200,00"),
    ],
)
def test_the_reported_code_is_removed_on_either_side(printed: str, expected: str) -> None:
    assert without_currency_unit(printed, "EUR") == expected


@pytest.mark.parametrize("symbol", CURRENCY_UNIT_SYMBOLS)
def test_a_symbol_is_removed_without_naming_a_currency(symbol: str) -> None:
    assert without_currency_unit(f"1.200,00 {symbol}") == "1.200,00"
    assert without_currency_unit(f"{symbol}1200.00") == "1200.00"


@pytest.mark.parametrize(
    "printed",
    ["1200.00 EUR", "1200.00 IVA", "1200.00 XYZ", "1200 EUR EUR", "1200.00 EUROS", "21%"],
)
def test_an_unnamed_or_repeated_unit_is_left_for_the_authority(printed: str) -> None:
    """Nothing the rule cannot name is removed, so a misread still fails to parse."""
    currency = "EUR" if printed != "1200.00 EUR" else None
    remainder = without_currency_unit(printed, currency)
    assert remainder == printed.strip()
    assert coerce_finite_european_decimal(remainder) is None
