"""Real-behavior tests for :func:`aeat.core.decimal.coerce_decimal`.

Expected values are derived from the Python :class:`decimal.Decimal`
specification and the three caller contracts consolidated in contract:

- ``_calc_sheets_pull``: nullable-cell pattern — no default, returns ``None``.
- ``_row_set_assembly``: aggregation pattern — ``default=Decimal("0")``, always returns
  a :class:`~decimal.Decimal`.
- ``invoices._models``: strict-validator pattern — no default; ``None`` result is
  handled by pydantic's ``ValidationError`` at the model boundary.

Tests are NOT tautological because the expected values are specified
from the type contract independently of the implementation.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest

from .. import coerce_decimal

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# Default policy: default=None (nullable-cell / no-default pattern)
# ---------------------------------------------------------------------------


def test_coerce_decimal_valid_inputs_no_default() -> None:
    """Valid inputs produce the expected Decimal regardless of default policy."""
    for value, expected in (
        # Well-formed Decimal passthrough
        (Decimal("12.34"), Decimal("12.34")),
        (Decimal("0"), Decimal("0")),
        (Decimal("-99.99"), Decimal("-99.99")),
        # Integer inputs → Decimal equivalent
        (0, Decimal("0")),
        (42, Decimal("42")),
        (-7, Decimal("-7")),
        # Float inputs → round-trip via str (exact for simple values)
        (1.5, Decimal("1.5")),
        # String inputs
        ("12.34", Decimal("12.34")),
        ("-0.01", Decimal("-0.01")),
        ("0", Decimal("0")),
        ("1000000.99", Decimal("1000000.99")),
        # Leading/trailing whitespace is handled by Decimal constructor
        (" 5.00 ", Decimal("5.00")),
    ):
        result = coerce_decimal(value)
        assert result == expected, repr(value)


def test_coerce_decimal_absent_returns_none_by_default() -> None:
    """None and empty string return None when no default is given."""
    for absent_value in (None, ""):
        assert coerce_decimal(absent_value) is None, repr(absent_value)


def test_coerce_decimal_malformed_returns_none_by_default() -> None:
    """Unparseable values return None when no default is given."""
    for bad_value in (
        "not-a-number",
        "1,234.56",  # locale-formatted — not valid Python Decimal syntax
        "€12.00",
        "NaN_custom",
        object(),
    ):
        assert coerce_decimal(bad_value) is None, repr(bad_value)


def test_coerce_decimal_debug_log_omits_raw_malformed_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_value = "not-a-decimal-secret"

    with caplog.at_level(logging.DEBUG, logger="aeat.core.decimal._coerce"):
        assert coerce_decimal(raw_value) is None

    relevant = [
        record
        for record in caplog.records
        if record.getMessage() == "coerce_decimal: could not parse value, returning configured default"
    ]
    assert len(relevant) == 1
    assert getattr(relevant[0], "value_type", None) == "str"
    assert getattr(relevant[0], "default_is_none", None) is True
    assert getattr(relevant[0], "error_type", None) == "InvalidOperation"
    assert raw_value not in relevant[0].getMessage()


# ---------------------------------------------------------------------------
# Aggregation policy: default=Decimal("0")
# Mirrors _row_set_assembly usage — always returns a Decimal.
# ---------------------------------------------------------------------------

_ZERO = Decimal("0")


def test_coerce_decimal_with_zero_default() -> None:
    """With default=Decimal('0') the helper never returns None."""
    for value, expected in (
        # Valid inputs still produce the parsed value (default unused)
        ("99.50", Decimal("99.50")),
        (Decimal("1.23"), Decimal("1.23")),
        (10, Decimal("10")),
        # Absent inputs fall back to zero
        (None, _ZERO),
        ("", _ZERO),
        # Malformed inputs fall back to zero
        ("bad", _ZERO),
        ("1,000", _ZERO),
    ):
        result = coerce_decimal(value, default=_ZERO)
        assert result is not None, repr(value)
        assert result == expected, repr(value)


# ---------------------------------------------------------------------------
# Custom non-zero default
# ---------------------------------------------------------------------------


def test_coerce_decimal_custom_default() -> None:
    """Arbitrary non-None defaults are respected."""
    for value, default, expected in (
        # Absent — use sentinel default
        (None, Decimal("-1"), Decimal("-1")),
        ("", Decimal("100"), Decimal("100")),
        # Malformed — use sentinel default
        ("oops", Decimal("99"), Decimal("99")),
        # Valid — default ignored
        ("5.5", Decimal("99"), Decimal("5.5")),
        (Decimal("2"), Decimal("99"), Decimal("2")),
    ):
        assert coerce_decimal(value, default=default) == expected, repr(value)


# ---------------------------------------------------------------------------
# Type identity: Decimal input is returned as-is (no unnecessary construction)
# ---------------------------------------------------------------------------


def test_coerce_decimal_passthrough_is_same_object() -> None:
    """Decimal inputs are returned without wrapping in a new Decimal instance."""
    d = Decimal("3.14")
    result = coerce_decimal(d)
    assert result is d


# ---------------------------------------------------------------------------
# Edge: NaN and Infinity (valid Decimal tokens — coerce_decimal accepts them)
# ---------------------------------------------------------------------------


def test_coerce_decimal_special_tokens_parsed() -> None:
    """Decimal's special tokens (Inf, NaN) are valid inputs and should parse."""
    for value in ("Inf", "-Inf", "Infinity", "NaN"):
        result = coerce_decimal(value)
        assert isinstance(result, Decimal), value
