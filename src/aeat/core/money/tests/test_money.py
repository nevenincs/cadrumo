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


def test_round_to_cents_truncates_below_half() -> None:
    """A residual under 0.5 cent rounds down."""
    assert round_to_cents(Decimal("1.234")) == Decimal("1.23")
    assert round_to_cents(Decimal("0.004")) == Decimal("0.00")


def test_round_to_cents_rounds_half_away_from_zero() -> None:
    """A residual of exactly 0.5 cent rounds AWAY from zero (HALF_UP, AEAT convention).

    Banker's rounding (HALF_EVEN) would round 1.005 to 1.00 and 1.015 to
    1.02; AEAT's published convention rounds both up by one cent.
    """
    assert round_to_cents(Decimal("1.005")) == Decimal("1.01")
    assert round_to_cents(Decimal("1.015")) == Decimal("1.02")
    assert round_to_cents(Decimal("2.345")) == Decimal("2.35")


def test_round_to_cents_handles_negative_amounts_symmetrically() -> None:
    """Negative residuals round away from zero too (away = more negative)."""
    assert round_to_cents(Decimal("-1.005")) == Decimal("-1.01")
    assert round_to_cents(Decimal("-1.234")) == Decimal("-1.23")


def test_round_to_cents_returns_decimal_with_two_digit_exponent() -> None:
    """The result is always quantised to two fractional digits."""
    result = round_to_cents(Decimal("1"))
    assert result.as_tuple().exponent == -2
    assert result == Decimal("1.00")


def test_round_to_cents_is_idempotent_on_already_quantised_values() -> None:
    """A value already at two digits is returned unchanged."""
    already = Decimal("100.99")
    assert round_to_cents(already) == already


def test_round_to_cents_preserves_high_precision_inputs() -> None:
    """Inputs with many fractional digits are quantised, not truncated mid-way."""
    assert round_to_cents(Decimal("3.14159265")) == Decimal("3.14")
    assert round_to_cents(Decimal("3.14999")) == Decimal("3.15")
