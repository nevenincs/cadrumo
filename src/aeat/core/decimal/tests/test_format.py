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


# ---------------------------------------------------------------------------
# normalize=False (default) — plain fixed-point
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("12.34"), "12.34"),
        (Decimal("-12.34"), "-12.34"),
        (Decimal("0"), "0"),
        (Decimal("0.00"), "0.00"),
        (Decimal("1000000.99"), "1000000.99"),
        (Decimal("0.001"), "0.001"),
        # trailing zeros preserved when not normalizing
        (Decimal("1.50"), "1.50"),
        (Decimal("100.00"), "100.00"),
    ],
)
def test_format_decimal_plain(value: Decimal, expected: str) -> None:
    assert format_decimal(value) == expected


# ---------------------------------------------------------------------------
# normalize=True — strips trailing zeros
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("12.34"), "12.34"),
        (Decimal("-12.34"), "-12.34"),
        (Decimal("0"), "0"),
        (Decimal("0.00"), "0"),
        (Decimal("1.50"), "1.5"),
        (Decimal("100.00"), "100"),
        (Decimal("0.001"), "0.001"),
        (Decimal("1000000.99"), "1000000.99"),
        # large exponent
        (Decimal("1E+6"), "1000000"),
    ],
)
def test_format_decimal_normalize(value: Decimal, expected: str) -> None:
    assert format_decimal(value, normalize=True) == expected


# ---------------------------------------------------------------------------
# None handling policies
# ---------------------------------------------------------------------------


def test_format_decimal_none_raises_by_default() -> None:
    """When none_value is not provided, passing None is a programming error."""
    with pytest.raises(DecimalFormatError, match="none_value was not provided"):
        format_decimal(None)


@pytest.mark.parametrize(
    ("value", "none_value", "expected"),
    [
        (None, "0", "0"),
        (None, "", ""),
        (None, "N/A", "N/A"),
        # non-None values still render normally
        (Decimal("5.00"), "0", "5.00"),
    ],
)
def test_format_decimal_none_value_policy(
    value: Decimal | None,
    none_value: str,
    expected: str,
) -> None:
    assert format_decimal(value, none_value=none_value) == expected


# ---------------------------------------------------------------------------
# Combination: normalize + none_value (mirrors _projection.py usage)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "0"),
        (Decimal("0"), "0"),
        (Decimal("1.50"), "1.5"),
        (Decimal("-3.00"), "-3"),
        (Decimal("100.99"), "100.99"),
    ],
)
def test_format_decimal_normalize_with_none_policy(value: Decimal | None, expected: str) -> None:
    """Mirrors the _projection.py call: normalize=True, none_value='0'."""
    assert format_decimal(value, normalize=True, none_value="0") == expected


# ---------------------------------------------------------------------------
# _censo_live.py call pattern: normalize=True then caller enforces ".00"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected_after_caller_patch"),
    [
        # value already has decimal part — no patch needed
        (Decimal("12.50"), "12.5"),
        # integer after normalize — caller adds ".00"
        (Decimal("100"), "100.00"),
        (Decimal("5.00"), "5.00"),
    ],
)
def test_format_decimal_censo_caller_pattern(value: Decimal, expected_after_caller_patch: str) -> None:
    """The _censo_live.py caller normalizes then appends .00 when no dot present.

    This test exercises the canonical output that the caller would produce.
    """
    text = format_decimal(value, normalize=True)
    result = text if "." in text else f"{text}.00"
    assert result == expected_after_caller_patch
