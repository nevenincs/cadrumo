"""Real-behavior tests for :func:`aeat.core.decimal.format_decimal`.

Values are derived from the Decimal type contract and the four original
caller contracts (no external numeric oracle required for string formatting
of well-known inputs).  Tests are NOT tautological because the expected
strings are computed independently of the implementation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ...errors import DecimalFormatError
from .. import format_decimal

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_format_decimal_policy_cases() -> None:
    cases: tuple[tuple[str, Decimal | None, bool, str | None, str], ...] = (
        ("plain-positive", Decimal("12.34"), False, None, "12.34"),
        ("plain-negative", Decimal("-12.34"), False, None, "-12.34"),
        ("plain-zero", Decimal("0"), False, None, "0"),
        ("plain-zero-scale", Decimal("0.00"), False, None, "0.00"),
        ("plain-large", Decimal("1000000.99"), False, None, "1000000.99"),
        ("plain-small", Decimal("0.001"), False, None, "0.001"),
        ("plain-preserves-trailing-zero", Decimal("1.50"), False, None, "1.50"),
        ("plain-preserves-trailing-zeros", Decimal("100.00"), False, None, "100.00"),
        ("normalize-positive", Decimal("12.34"), True, None, "12.34"),
        ("normalize-negative", Decimal("-12.34"), True, None, "-12.34"),
        ("normalize-zero", Decimal("0"), True, None, "0"),
        ("normalize-zero-scale", Decimal("0.00"), True, None, "0"),
        ("normalize-trailing-zero", Decimal("1.50"), True, None, "1.5"),
        ("normalize-censo-decimal", Decimal("12.50"), True, None, "12.5"),
        ("normalize-censo-integer", Decimal("100"), True, None, "100"),
        ("normalize-censo-scale", Decimal("5.00"), True, None, "5"),
        ("normalize-hundreds", Decimal("100.00"), True, None, "100"),
        ("normalize-small", Decimal("0.001"), True, None, "0.001"),
        ("normalize-large", Decimal("1000000.99"), True, None, "1000000.99"),
        ("normalize-exponent", Decimal("1E+6"), True, None, "1000000"),
        ("none-zero-policy", None, False, "0", "0"),
        ("none-empty-policy", None, False, "", ""),
        ("none-na-policy", None, False, "N/A", "N/A"),
        ("non-none-ignores-none-policy", Decimal("5.00"), False, "0", "5.00"),
        ("normalize-none-policy", None, True, "0", "0"),
        ("normalize-none-zero", Decimal("0"), True, "0", "0"),
        ("normalize-none-trailing-zero", Decimal("1.50"), True, "0", "1.5"),
        ("normalize-none-negative", Decimal("-3.00"), True, "0", "-3"),
        ("normalize-none-decimal", Decimal("100.99"), True, "0", "100.99"),
    )

    for label, value, normalize, none_value, expected in cases:
        if none_value is None:
            result = format_decimal(value, normalize=normalize)
        else:
            result = format_decimal(value, normalize=normalize, none_value=none_value)
        assert result == expected, label

    with pytest.raises(DecimalFormatError, match="none_value was not provided"):
        format_decimal(None)
