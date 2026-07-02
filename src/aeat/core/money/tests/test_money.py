"""Tests for the canonical core money primitive."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .. import CENT, round_to_cents

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_round_to_cents_quantizes_half_up_to_the_cent_quantum() -> None:
    """CENT pins the euro-cent quantum and round_to_cents uses it."""
    assert Decimal("0.01") == CENT
    assert CENT.as_tuple().exponent == -2

    cases = (
        ("1.234", "1.23"),
        ("0.004", "0.00"),
        ("1.005", "1.01"),
        ("1.015", "1.02"),
        ("2.345", "2.35"),
        ("-1.005", "-1.01"),
        ("-1.234", "-1.23"),
        ("3.14159265", "3.14"),
        ("3.14999", "3.15"),
    )

    for raw, expected in cases:
        result = round_to_cents(Decimal(raw))
        assert result == Decimal(expected)
        assert result.as_tuple().exponent == -2

    result = round_to_cents(Decimal("1"))
    assert result.as_tuple().exponent == -2
    assert result == Decimal("1.00")

    already = Decimal("100.99")
    assert round_to_cents(already) == already
