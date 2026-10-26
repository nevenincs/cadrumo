"""Tests for the canonical core money primitive.

These cases pin :data:`~core.money.CENT` and :func:`~core.money.round_to_cents`
as the euro-cent boundary used by AEAT calculation surfaces. The expected
values are independently enumerated to prove :data:`~decimal.ROUND_HALF_UP`
behaviour, including the negative half-cent cases where banker's rounding would
drift.

See Also:
    :mod:`~core.money`
        Canonical ``Decimal`` money primitive module under test.
    :class:`~decimal.Decimal`
        Value type quantized to the two-decimal euro-cent exponent.
    :data:`~decimal.ROUND_HALF_UP`
        Rounding mode required at filed-money boundaries.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..rounding import CENT, round_to_cents

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_cent_constant_is_the_euro_cent_quantum() -> None:
    """CENT pins the euro-cent quantum."""
    assert Decimal("0.01") == CENT
    assert CENT.as_tuple().exponent == -2


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        pytest.param("1.234", "1.23", id="truncate-positive"),
        pytest.param("0.004", "0.00", id="below-half-cent"),
        pytest.param("1.005", "1.01", id="half-up-positive"),
        pytest.param("1.015", "1.02", id="next-half-up-positive"),
        pytest.param("2.345", "2.35", id="half-up-two-decimals"),
        pytest.param("-1.005", "-1.01", id="half-up-negative"),
        pytest.param("-1.234", "-1.23", id="truncate-negative"),
        pytest.param("3.14159265", "3.14", id="long-tail-down"),
        pytest.param("3.14999", "3.15", id="long-tail-up"),
    ),
)
def test_round_to_cents_quantizes_half_up_to_the_cent_quantum(raw: str, expected: str) -> None:
    result = round_to_cents(Decimal(raw))
    assert result == Decimal(expected)
    assert result.as_tuple().exponent == -2


def test_round_to_cents_pads_whole_euro_to_cent_exponent() -> None:
    result = round_to_cents(Decimal("1"))
    assert result.as_tuple().exponent == -2
    assert result == Decimal("1.00")


def test_round_to_cents_preserves_already_quantized_value() -> None:
    already = Decimal("100.99")
    assert round_to_cents(already) == already
