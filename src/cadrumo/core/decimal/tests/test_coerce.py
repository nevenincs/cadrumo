"""Real-behavior tests for :func:`cadrumo.core.decimal.coerce_decimal`.

Expected values are derived from the Python :class:`decimal.Decimal`
specification and the three caller contracts consolidated in contract:

- ``_calc_sheets_pull``: nullable-cell pattern — no default, returns ``None``.
- ``_row_set_assembly``: aggregation pattern — ``default=Decimal("0")``, always returns
  a :class:`~decimal.Decimal`.
- ``invoices.models``: strict-validator pattern — no default; ``None`` result is
  handled by pydantic's ``ValidationError`` at the model boundary.

Tests are NOT tautological because the expected values are specified
from the type contract independently of the implementation.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest

from ..coercion import coerce_decimal, coerce_finite_european_decimal

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_UNPARSEABLE_OBJECT = object()
_ZERO = Decimal("0")


def test_coerce_decimal_policy_cases() -> None:
    cases: tuple[tuple[str, object, Decimal | None, Decimal | None], ...] = (
        ("decimal-positive", Decimal("12.34"), None, Decimal("12.34")),
        ("decimal-zero", Decimal("0"), None, Decimal("0")),
        ("decimal-negative", Decimal("-99.99"), None, Decimal("-99.99")),
        ("int-zero", 0, None, Decimal("0")),
        ("int-positive", 42, None, Decimal("42")),
        ("int-negative", -7, None, Decimal("-7")),
        ("float-simple", 1.5, None, Decimal("1.5")),
        ("string-positive", "12.34", None, Decimal("12.34")),
        ("string-negative", "-0.01", None, Decimal("-0.01")),
        ("string-zero", "0", None, Decimal("0")),
        ("string-large", "1000000.99", None, Decimal("1000000.99")),
        ("string-whitespace", " 5.00 ", None, Decimal("5.00")),
        ("none-default-none", None, None, None),
        ("empty-default-none", "", None, None),
        ("bad-string-default-none", "not-a-number", None, None),
        ("locale-string-default-none", "1,234.56", None, None),
        ("currency-string-default-none", "€12.00", None, None),
        ("nan-custom-default-none", "NaN_custom", None, None),
        ("object-default-none", _UNPARSEABLE_OBJECT, None, None),
        ("zero-default-valid-string", "99.50", _ZERO, Decimal("99.50")),
        ("zero-default-valid-decimal", Decimal("1.23"), _ZERO, Decimal("1.23")),
        ("zero-default-valid-int", 10, _ZERO, Decimal("10")),
        ("zero-default-none", None, _ZERO, _ZERO),
        ("zero-default-empty", "", _ZERO, _ZERO),
        ("zero-default-bad", "bad", _ZERO, _ZERO),
        ("zero-default-locale", "1,000", _ZERO, _ZERO),
        ("custom-default-none", None, Decimal("-1"), Decimal("-1")),
        ("custom-default-empty", "", Decimal("100"), Decimal("100")),
        ("custom-default-bad", "oops", Decimal("99"), Decimal("99")),
        ("custom-default-valid-string", "5.5", Decimal("99"), Decimal("5.5")),
        ("custom-default-valid-decimal", Decimal("2"), Decimal("99"), Decimal("2")),
    )

    for label, value, default, expected in cases:
        result = coerce_decimal(value, default=default)
        assert result == expected, label
        if default is not None:
            assert result is not None, label

    passthrough = Decimal("3.14")
    assert coerce_decimal(passthrough) is passthrough

    for value in ("Inf", "-Inf", "Infinity", "NaN"):
        result = coerce_decimal(value)
        assert isinstance(result, Decimal), value


def test_coerce_decimal_debug_log_omits_raw_malformed_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_value = "not-a-decimal-secret"

    with caplog.at_level(logging.DEBUG, logger="cadrumo.core.decimal.coercion"):
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


def test_coerce_finite_european_decimal_preserves_amount_and_refuses_non_finite_values() -> None:
    """The tolerant spreadsheet boundary retains Spanish amount semantics without admitting non-finite Decimal."""
    assert coerce_finite_european_decimal("1.234,56") == Decimal("1234.56")
    assert coerce_finite_european_decimal("10000.50") == Decimal("10000.50")

    for raw_value in ("not-a-number", "NaN", "Infinity", "-Infinity"):
        assert coerce_finite_european_decimal(raw_value) is None, raw_value
