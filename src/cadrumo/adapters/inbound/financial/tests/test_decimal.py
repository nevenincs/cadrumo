"""Unit tests for the canonical decimal-string helper used in the financial ingest layer.

Asserts the helper renders :class:`decimal.Decimal` values in the canonical
fixed-point form expected by the financial-ingest layer: zeros collapse to
``"0"``, trailing zeros are stripped, and exponent notation is never used —
so JSON round-trips remain byte-stable across precision-equivalent inputs.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....domain.identifiers import canonical_decimal_string

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_canonical_decimal_renders_zero_without_precision_noise() -> None:
    """Every zero representation must collapse to the bare '0' literal."""
    assert canonical_decimal_string(Decimal("0")) == "0"
    assert canonical_decimal_string(Decimal("0.0")) == "0"
    assert canonical_decimal_string(Decimal("0.00")) == "0"
    assert canonical_decimal_string(Decimal("0E-10")) == "0"


def test_canonical_decimal_strips_trailing_zeros_from_non_zero_values() -> None:
    """Normalized non-zero values must render without trailing zeros or exponent."""
    assert canonical_decimal_string(Decimal("1.0")) == "1"
    assert canonical_decimal_string(Decimal("1.50")) == "1.5"
    assert canonical_decimal_string(Decimal("-42.100")) == "-42.1"


def test_canonical_decimal_preserves_small_magnitudes_without_exponent() -> None:
    """Sub-unit precision must not flip to exponent notation."""
    assert canonical_decimal_string(Decimal("0.000000001")) == "0.000000001"


def test_canonical_decimal_preserves_large_integers_without_exponent() -> None:
    """Large integer values must render as fixed-point digits."""
    assert canonical_decimal_string(Decimal("1234567890")) == "1234567890"
