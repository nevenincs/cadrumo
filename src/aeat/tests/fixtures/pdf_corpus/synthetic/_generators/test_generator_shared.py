"""Unit tests for the shared synthetic-PDF generator primitives."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._generator_shared import format_amount

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


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
    assert format_amount(Decimal("100.555")) == "100,56"  # ROUND_HALF_EVEN -> 56


@pytest.mark.parametrize(
    ("value", "sep", "expected"),
    [
        (Decimal("1234.56"), "\xa0", "1\xa0234,56"),  # U+00A0 NBSP
        (Decimal("1234.56"), " ", "1 234,56"),  # U+202F narrow NBSP
        (Decimal("1000000"), "\xa0", "1\xa0000\xa0000,00"),  # multi-group NBSP
    ],
    ids=["nbsp", "narrow-nbsp", "multi-group-nbsp"],
)
def test_format_amount_nbsp_thousands(value: Decimal, sep: str, expected: str) -> None:
    """Generator must be able to render NBSP / narrow-NBSP thousands."""
    assert format_amount(value, thousands_sep=sep) == expected
