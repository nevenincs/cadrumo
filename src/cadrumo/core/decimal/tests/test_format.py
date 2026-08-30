"""Real-behavior tests for :func:`~core.decimal.format_decimal`.

Values are derived from the Decimal type contract and the four original
caller contracts (no external numeric oracle required for string formatting
of well-known inputs).  Tests are NOT tautological because the expected
strings are computed independently of the implementation.

See Also:
    :mod:`~core.decimal._format`
        Canonical formatter module that replaced the four former local helper
        copies.
    :class:`~core.errors.DecimalFormatError`
        Typed core error raised when ``None`` is passed without a
        ``none_value`` policy.
    :class:`~decimal.Decimal`
        Standard-library value contract whose fixed-point formatting and
        ``normalize`` behaviour these cases pin.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ...errors.hierarchy import DecimalFormatError
from .. import format_decimal

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("value", "normalize", "none_value", "expected"),
    (
        pytest.param(Decimal("12.34"), False, None, "12.34", id="plain-positive"),
        pytest.param(Decimal("-12.34"), False, None, "-12.34", id="plain-negative"),
        pytest.param(Decimal("0"), False, None, "0", id="plain-zero"),
        pytest.param(Decimal("0.00"), False, None, "0.00", id="plain-zero-scale"),
        pytest.param(Decimal("1000000.99"), False, None, "1000000.99", id="plain-large"),
        pytest.param(Decimal("0.001"), False, None, "0.001", id="plain-small"),
        pytest.param(Decimal("1.50"), False, None, "1.50", id="plain-preserves-trailing-zero"),
        pytest.param(Decimal("100.00"), False, None, "100.00", id="plain-preserves-trailing-zeros"),
        pytest.param(Decimal("12.34"), True, None, "12.34", id="normalize-positive"),
        pytest.param(Decimal("-12.34"), True, None, "-12.34", id="normalize-negative"),
        pytest.param(Decimal("0"), True, None, "0", id="normalize-zero"),
        pytest.param(Decimal("0.00"), True, None, "0", id="normalize-zero-scale"),
        pytest.param(Decimal("1.50"), True, None, "1.5", id="normalize-trailing-zero"),
        pytest.param(Decimal("12.50"), True, None, "12.5", id="normalize-censo-decimal"),
        pytest.param(Decimal("100"), True, None, "100", id="normalize-censo-integer"),
        pytest.param(Decimal("5.00"), True, None, "5", id="normalize-censo-scale"),
        pytest.param(Decimal("100.00"), True, None, "100", id="normalize-hundreds"),
        pytest.param(Decimal("0.001"), True, None, "0.001", id="normalize-small"),
        pytest.param(Decimal("1000000.99"), True, None, "1000000.99", id="normalize-large"),
        pytest.param(Decimal("1E+6"), True, None, "1000000", id="normalize-exponent"),
        pytest.param(None, False, "0", "0", id="none-zero-policy"),
        pytest.param(None, False, "", "", id="none-empty-policy"),
        pytest.param(None, False, "N/A", "N/A", id="none-na-policy"),
        pytest.param(Decimal("5.00"), False, "0", "5.00", id="non-none-ignores-none-policy"),
        pytest.param(None, True, "0", "0", id="normalize-none-policy"),
        pytest.param(Decimal("0"), True, "0", "0", id="normalize-none-zero"),
        pytest.param(Decimal("1.50"), True, "0", "1.5", id="normalize-none-trailing-zero"),
        pytest.param(Decimal("-3.00"), True, "0", "-3", id="normalize-none-negative"),
        pytest.param(Decimal("100.99"), True, "0", "100.99", id="normalize-none-decimal"),
    ),
)
def test_format_decimal_policy_cases(
    value: Decimal | None,
    normalize: bool,
    none_value: str | None,
    expected: str,
) -> None:
    if none_value is None:
        result = format_decimal(value, normalize=normalize)
    else:
        result = format_decimal(value, normalize=normalize, none_value=none_value)
    assert result == expected


def test_format_decimal_requires_none_value_for_absent_value() -> None:
    with pytest.raises(DecimalFormatError, match="none_value was not provided"):
        format_decimal(None)
