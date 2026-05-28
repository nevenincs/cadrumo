"""Real-behavior tests for the canonical fincas euro-cent rounding helper.

Expected values are derived from Python's decimal specification and the
ROUND_HALF_UP semantics documented in the IEEE 754-2008 standard, not
hand-computed from the same formula under test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._rounding import _round_to_cents

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        # Half-up boundary: 0.005 rounds up to 0.01, not down to 0.00
        (Decimal("0.005"), Decimal("0.01")),
        # 0.004 rounds down
        (Decimal("0.004"), Decimal("0.00")),
        # 0.014 rounds down to 0.01
        (Decimal("0.014"), Decimal("0.01")),
        # 0.015 rounds up to 0.02
        (Decimal("0.015"), Decimal("0.02")),
        # Exact cent — no change
        (Decimal("1.23"), Decimal("1.23")),
        # Large value with trailing sub-cent fraction
        (Decimal("1234.567"), Decimal("1234.57")),
        # Negative: half-up applied to absolute value, so -0.005 rounds to -0.01
        (Decimal("-0.005"), Decimal("-0.01")),
        # Negative rounds toward negative infinity under ROUND_HALF_UP
        (Decimal("-0.014"), Decimal("-0.01")),
        (Decimal("-0.015"), Decimal("-0.02")),
        # Zero is invariant
        (Decimal("0"), Decimal("0.00")),
        (Decimal("0.000"), Decimal("0.00")),
        # Already-exact edge
        (Decimal("99.99"), Decimal("99.99")),
    ],
)
def test_round_to_cents(input_value: Decimal, expected: Decimal) -> None:
    result = _round_to_cents(input_value)
    assert result == expected, (
        f"_round_to_cents({input_value!r}) = {result!r}, expected {expected!r}"
    )
    # Result must always be expressed to exactly two decimal places
    assert result.as_tuple().exponent == -2, (
        f"Result {result!r} does not have exactly 2 decimal places"
    )
