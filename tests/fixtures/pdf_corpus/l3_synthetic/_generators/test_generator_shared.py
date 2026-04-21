"""Unit tests for the shared synthetic-PDF generator primitives."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._generator_shared import format_amount

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("0"), "0,00"),
        (Decimal("0.00"), "0,00"),
        (Decimal("1234.56"), "1.234,56"),
        (Decimal("1000000"), "1.000.000,00"),
        (Decimal("-42.50"), "-42,50"),
        (Decimal("0.01"), "0,01"),
    ],
)
def test_format_amount_matches_aeat_style(value: Decimal, expected: str) -> None:
    """Spanish-style thousands (`.`) + comma decimal (`,`) — matches AEAT's receipts."""
    assert format_amount(value) == expected


def test_format_amount_quantises_to_two_decimals() -> None:
    assert format_amount(Decimal("100.5")) == "100,50"
    assert format_amount(Decimal("100.555")) == "100,56"  # ROUND_HALF_EVEN → 56
