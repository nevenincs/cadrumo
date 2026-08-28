"""Edge-case coverage for the row-set assembler coercion helpers.

The public assemblers test the happy path: operator-typed strings
arrive as Decimal / ISO date / text and convert cleanly. The helpers
themselves have edge cases (``None``, empty string, malformed
numeric, non-ISO date) that benefit from direct exercise rather
than hoping the public-API tests stumble across each one.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.decimal import coerce_decimal as _coerce_decimal
from ..row_set_assembly import _coerce_iso_date, _coerce_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# _coerce_decimal
# ---------------------------------------------------------------------------


def test_coerce_decimal_passes_through_decimal_value() -> None:
    assert _coerce_decimal(Decimal("1500.55"), default=Decimal("0")) == Decimal("1500.55")


def test_coerce_decimal_parses_decimal_string() -> None:
    assert _coerce_decimal("1500.55", default=Decimal("0")) == Decimal("1500.55")


def test_coerce_decimal_returns_default_for_none() -> None:
    assert _coerce_decimal(None, default=Decimal("42")) == Decimal("42")


def test_coerce_decimal_returns_default_for_empty_string() -> None:
    """An operator who clears a numeric cell ends up with empty string."""
    assert _coerce_decimal("", default=Decimal("99")) == Decimal("99")


def test_coerce_decimal_returns_default_for_malformed_string() -> None:
    assert _coerce_decimal("not-a-number", default=Decimal("7")) == Decimal("7")


def test_coerce_decimal_handles_scientific_notation() -> None:
    """Sheets-derived strings can be in scientific notation for very small / large values."""
    assert _coerce_decimal("1.5E3", default=Decimal("0")) == Decimal("1500")


def test_coerce_decimal_handles_negative_numbers() -> None:
    assert _coerce_decimal("-100.50", default=Decimal("0")) == Decimal("-100.50")


# ---------------------------------------------------------------------------
# _coerce_text
# ---------------------------------------------------------------------------


def test_coerce_text_passes_through_string() -> None:
    assert _coerce_text("Perceptor One") == "Perceptor One"


def test_coerce_text_returns_default_for_none() -> None:
    assert _coerce_text(None) == ""
    assert _coerce_text(None, default="UNKNOWN") == "UNKNOWN"


def test_coerce_text_formats_decimal_without_scientific_notation() -> None:
    """Decimals that round-trip through Sheets must surface as plain text.

    A NIF or operation-kind code that the operator typed as "01"
    might come back as Decimal('1') from Sheets unformatted
    rendering. ``format(value, "f")`` keeps the integer value
    plain (no `1E1` artifacts), even if information about leading
    zeros is lost.
    """
    assert _coerce_text(Decimal("12345")) == "12345"
    assert _coerce_text(Decimal("1500.55")) == "1500.55"


def test_coerce_text_preserves_empty_string() -> None:
    assert _coerce_text("") == ""


# ---------------------------------------------------------------------------
# _coerce_iso_date
# ---------------------------------------------------------------------------


def test_coerce_iso_date_parses_iso_format() -> None:
    assert _coerce_iso_date("2025-06-15", default=date(1900, 1, 1)) == date(2025, 6, 15)


def test_coerce_iso_date_returns_default_for_none() -> None:
    assert _coerce_iso_date(None, default=date(2025, 12, 31)) == date(2025, 12, 31)


def test_coerce_iso_date_returns_default_for_empty_string() -> None:
    assert _coerce_iso_date("", default=date(2025, 12, 31)) == date(2025, 12, 31)


def test_coerce_iso_date_returns_default_for_malformed_string() -> None:
    """Operator-typed dates in non-ISO format fall back rather than crashing."""
    assert _coerce_iso_date("15/06/2025", default=date(2025, 12, 31)) == date(2025, 12, 31)
    assert _coerce_iso_date("June 15, 2025", default=date(2025, 12, 31)) == date(2025, 12, 31)


def test_coerce_iso_date_returns_default_for_decimal_input() -> None:
    """A numeric cell value cannot be a date; fall back."""
    assert _coerce_iso_date(Decimal("20250615"), default=date(2025, 12, 31)) == date(2025, 12, 31)
