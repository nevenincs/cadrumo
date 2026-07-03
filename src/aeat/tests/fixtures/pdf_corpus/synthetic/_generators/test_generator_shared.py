"""Unit tests for the shared synthetic-PDF generator primitives."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._generator_shared import format_amount

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_format_amount_matches_aeat_style() -> None:
    """Spanish-style thousands (`.`) + comma decimal (`,`) — matches AEAT's receipts."""
    cases = (
        ("zero-int", Decimal("0"), "0,00"),
        ("zero-decimal", Decimal("0.00"), "0,00"),
        ("thousands", Decimal("1234.56"), "1.234,56"),
        ("millions", Decimal("1000000"), "1.000.000,00"),
        ("negative", Decimal("-42.50"), "-42,50"),
        ("cents", Decimal("0.01"), "0,01"),
    )
    for case_id, value, expected in cases:
        assert format_amount(value) == expected, case_id


def test_format_amount_quantises_to_two_decimals() -> None:
    assert format_amount(Decimal("100.5")) == "100,50"
    assert format_amount(Decimal("100.555")) == "100,56"  # ROUND_HALF_EVEN -> 56


def test_format_amount_nbsp_thousands() -> None:
    """Generator must be able to render NBSP / narrow-NBSP thousands."""
    cases = (
        ("nbsp", Decimal("1234.56"), "\xa0", "1\xa0234,56"),
        ("plain-space", Decimal("1234.56"), " ", "1 234,56"),
        ("multi-group-nbsp", Decimal("1000000"), "\xa0", "1\xa0000\xa0000,00"),
    )
    for case_id, value, sep, expected in cases:
        assert format_amount(value, thousands_sep=sep) == expected, case_id
