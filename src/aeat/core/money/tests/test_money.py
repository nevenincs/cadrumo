"""Tests for the canonical core money primitive."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .. import CENT, round_to_cents

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_cent_constant_is_two_decimal_places() -> None:
    """CENT pins the euro-cent quantum."""
    assert Decimal("0.01") == CENT
    assert CENT.as_tuple().exponent == -2


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        pytest.param("1.234", "1.23", id="below-half-down"),
        pytest.param("0.004", "0.00", id="below-half-to-zero"),
        pytest.param("1.005", "1.01", id="half-up-1005"),
        pytest.param("1.015", "1.02", id="half-up-1015"),
        pytest.param("2.345", "2.35", id="half-up-2345"),
        pytest.param("-1.005", "-1.01", id="negative-half-away-from-zero"),
        pytest.param("-1.234", "-1.23", id="negative-below-half"),
        pytest.param("3.14159265", "3.14", id="high-precision-down"),
        pytest.param("3.14999", "3.15", id="high-precision-up"),
    ),
)
def test_round_to_cents_quantizes_examples(raw: str, expected: str) -> None:
    assert round_to_cents(Decimal(raw)) == Decimal(expected)


def test_round_to_cents_returns_decimal_with_two_digit_exponent() -> None:
    """The result is always quantised to two fractional digits."""
    result = round_to_cents(Decimal("1"))
    assert result.as_tuple().exponent == -2
    assert result == Decimal("1.00")


def test_round_to_cents_is_idempotent_on_already_quantised_values() -> None:
    """A value already at two digits is returned unchanged."""
    already = Decimal("100.99")
    assert round_to_cents(already) == already

