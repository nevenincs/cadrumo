"""Focused unit tests for the ``_format_decimal`` projection helper.

``_format_decimal(value)`` renders a :class:`Decimal` for display as
a string with normalised trailing zeros, defaulting to ``"0"`` when
the value is ``None``.

Previously exercised only indirectly through
``project_invoice_review`` integration tests. A regression in
``_format_decimal`` (e.g. emitting scientific notation for very
small / large values) would silently corrupt operator-facing
display lines.

Assertions pin the projection-contract output, not calculation
tautologies.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.decimal._format import format_decimal as _canonical_format_decimal

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _format_decimal(value: Decimal | None) -> str:
    """Thin wrapper matching the old projection._format_decimal contract."""
    return _canonical_format_decimal(value, normalize=True, none_value="0")


# ---------------------------------------------------------------------------
# _format_decimal — display contract
# ---------------------------------------------------------------------------


def test_format_decimal_returns_zero_string_for_none() -> None:
    """None projects to the literal ``"0"`` string so downstream
    rendering never has to special-case missing amounts."""
    assert _format_decimal(None) == "0"


def test_format_decimal_renders_integer_decimal_as_plain_integer() -> None:
    """An integer-valued Decimal renders as a plain integer string
    via the fixed-point ``f`` format spec, regardless of how the
    ``.normalize()`` step represents it internally."""
    assert _format_decimal(Decimal("100")) == "100"


def test_format_decimal_uses_fixed_point_format_no_scientific_for_fractional() -> None:
    """Fixed-point formatter is the ``f`` format spec — fractional
    Decimals retain decimal-point form."""
    assert _format_decimal(Decimal("12.34")) == "12.34"


def test_format_decimal_normalises_trailing_zeros() -> None:
    """``Decimal("12.30")`` normalises to ``12.3`` — the helper
    pins the normalised string output, not the input's precision."""
    assert _format_decimal(Decimal("12.30")) == "12.3"


def test_format_decimal_renders_negative_value() -> None:
    assert _format_decimal(Decimal("-7.50")) == "-7.5"


def test_format_decimal_renders_zero() -> None:
    """``Decimal("0")`` is distinct from ``None`` — the input must
    survive the projection, not be coalesced to the None branch."""
    assert _format_decimal(Decimal("0")) == "0"


def test_format_decimal_renders_zero_with_trailing_zeros_as_normalised_zero() -> None:
    assert _format_decimal(Decimal("0.00")) == "0"
