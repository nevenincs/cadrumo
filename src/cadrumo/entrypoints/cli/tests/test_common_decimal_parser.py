"""Boundary tests for the shared canonical decimal-amount parser.

Exercises the real :func:`parse_decimal_amount` /
:func:`parse_optional_decimal_amount` helpers in
:mod:`cadrumo.entrypoints.cli._common` — the single owned validator the six
duplicated ledger ``_parse_decimal`` copies now delegate to. No mocks, no
stubs, no skips: every case drives the real regex + ``is_finite()`` guard and
asserts a concrete accept or a real ``typer.BadParameter`` refusal.

The canonical grammar is a dot decimal separator with an optional one- or
two-digit (euro-cent) fractional part, no thousands grouping, no scientific
notation, and no ``NaN``/``Infinity``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import typer

from .._decimal_parsing import parse_decimal_amount, parse_optional_decimal_amount
from ._strict_cli_fixture_support import english_locale_fixture

__all__ = ["english_locale_fixture"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

# Inputs the canonical boundary MUST refuse. ``1.000`` is the Spanish
# thousands-grouping shape that previously became ``1.0`` silently (F1);
# ``1.234,56`` carries a decimal comma + grouping; ``1e3`` is scientific
# notation; ``NaN`` / ``Infinity`` / ``-Infinity`` are non-finite (F2).
_REJECTED = ("1.000", "1.234,56", "1e3", "NaN", "Infinity", "-Infinity", "1,000", "not-decimal", "", "  ")

# Inputs the canonical boundary MUST accept, with their parsed value.
_ACCEPTED_NONNEGATIVE = (
    ("1000", Decimal("1000")),
    ("1234.56", Decimal("1234.56")),
    ("0", Decimal("0")),
    ("0.5", Decimal("0.5")),
    ("21.00", Decimal("21.00")),
)


def test_parse_decimal_amount_refuses_non_canonical() -> None:
    for raw in _REJECTED:
        with pytest.raises(typer.BadParameter):
            parse_decimal_amount(raw, label="amount")


def test_parse_decimal_amount_accepts_canonical() -> None:
    for raw, expected in _ACCEPTED_NONNEGATIVE:
        assert parse_decimal_amount(raw, label="amount", signed=False) == expected, raw


def test_parse_decimal_amount_signed_accepts_negative() -> None:
    assert parse_decimal_amount("-50.00", label="amount", signed=True) == Decimal("-50.00")


def test_parse_decimal_amount_nonnegative_refuses_negative() -> None:
    with pytest.raises(typer.BadParameter):
        parse_decimal_amount("-50.00", label="amount", signed=False)


def test_parse_decimal_amount_refuses_three_digit_fraction_thousands_shape() -> None:
    # The whole point of F1: ``1.000`` must not silently survive as ``1.0``.
    with pytest.raises(typer.BadParameter):
        parse_decimal_amount("1.000", label="amount", signed=False)


def test_parse_optional_decimal_amount_passes_through_none() -> None:
    assert parse_optional_decimal_amount(None, label="amount") is None


def test_parse_optional_decimal_amount_validates_when_present() -> None:
    assert parse_optional_decimal_amount("12.34", label="amount", signed=False) == Decimal("12.34")
    with pytest.raises(typer.BadParameter):
        parse_optional_decimal_amount("1.000", label="amount", signed=False)


def test_refusal_message_names_field_raw_and_expected_format() -> None:
    with pytest.raises(typer.BadParameter) as excinfo:
        parse_decimal_amount("1.000", label="taxable-base", signed=False)
    message = excinfo.value.message
    assert "taxable-base" in message
    assert "1.000" in message
    # The hint must name the accepted form, not just declare the input invalid.
    assert "1234.56" in message
