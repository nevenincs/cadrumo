"""Focused unit tests for reconciliation pure helpers.

The integration suite in test_reconcile.py covers the public
``reconcile`` orchestrator end-to-end but the small pure helpers it
delegates to (period canonicalisation, tax-id normalisation, decimal
formatting) had no direct unit-test coverage. A regression in the
period-dispatch regex order or the case-insensitive flag would
silently misroute canonical period selection for every filing
reconciliation report.

Tests here are structural / contract assertions on the helpers, not
calculation tautologies.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.decimal import format_decimal as _format_decimal
from ....domain.filing import ModeloBuilderError
from ._reconcile import (
    _canonical_draft_period_token,
    _canonical_tax_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


# ---------------------------------------------------------------------------
# _canonical_draft_period_token — map ModeloDraft period → registry token
# ---------------------------------------------------------------------------


def test_canonical_draft_period_token_maps_quarter_to_t_suffix() -> None:
    assert _canonical_draft_period_token("2025Q1") == "1T"
    assert _canonical_draft_period_token("2025Q2") == "2T"
    assert _canonical_draft_period_token("2025Q3") == "3T"
    assert _canonical_draft_period_token("2025Q4") == "4T"


def test_canonical_draft_period_token_quarter_is_case_insensitive() -> None:
    """The regex is compiled with re.IGNORECASE so lowercase `q` works."""
    assert _canonical_draft_period_token("2025q2") == "2T"


def test_canonical_draft_period_token_maps_annual_to_0a() -> None:
    assert _canonical_draft_period_token("2025A") == "0A"
    assert _canonical_draft_period_token("2030A") == "0A"


def test_canonical_draft_period_token_annual_is_case_insensitive() -> None:
    assert _canonical_draft_period_token("2025a") == "0A"


def test_canonical_draft_period_token_passes_canonical_month_through() -> None:
    """YYYY-MM is already canonical — the helper extracts the MM segment."""
    assert _canonical_draft_period_token("2025-01") == "01"
    assert _canonical_draft_period_token("2025-12") == "12"


def test_canonical_draft_period_token_raises_on_unparseable_input() -> None:
    with pytest.raises(ModeloBuilderError, match="cannot map draft period"):
        _canonical_draft_period_token("not-a-period")


def test_canonical_draft_period_token_raises_on_invalid_quarter_number() -> None:
    """Quarter regex only accepts 1-4; `2025Q5` falls through every branch."""
    with pytest.raises(ModeloBuilderError, match="cannot map draft period"):
        _canonical_draft_period_token("2025Q5")


def test_canonical_draft_period_token_raises_on_invalid_month_number() -> None:
    """Month regex only accepts 01-12; `2025-13` falls through every branch."""
    with pytest.raises(ModeloBuilderError, match="cannot map draft period"):
        _canonical_draft_period_token("2025-13")


# ---------------------------------------------------------------------------
# _canonical_tax_id — strip + upper for tolerant NIF/NIE comparison
# ---------------------------------------------------------------------------


def test_canonical_tax_id_strips_surrounding_whitespace() -> None:
    assert _canonical_tax_id("  12345678Z  ") == "12345678Z"


def test_canonical_tax_id_uppercases_lowercase_letters() -> None:
    assert _canonical_tax_id("12345678z") == "12345678Z"


def test_canonical_tax_id_is_idempotent_on_already_canonical_input() -> None:
    assert _canonical_tax_id("12345678Z") == "12345678Z"


def test_canonical_tax_id_combines_strip_and_upper_in_one_pass() -> None:
    assert _canonical_tax_id("  x1234567l  ") == "X1234567L"


# ---------------------------------------------------------------------------
# _format_decimal — fixed-point notation for mismatch records
# ---------------------------------------------------------------------------


def test_format_decimal_renders_integer_without_decimal_point() -> None:
    assert _format_decimal(Decimal("1234")) == "1234"


def test_format_decimal_preserves_two_place_money_precision() -> None:
    assert _format_decimal(Decimal("1234.56")) == "1234.56"


def test_format_decimal_preserves_trailing_zeros_for_money_form() -> None:
    """The ``f`` format spec keeps the declared scale, so ``1.50`` and
    ``1.5`` render distinctly — important for AEAT money fields which
    are scale-2 by convention."""
    assert _format_decimal(Decimal("1.50")) == "1.50"
    assert _format_decimal(Decimal("1.5")) == "1.5"


def test_format_decimal_renders_zero_without_scale() -> None:
    assert _format_decimal(Decimal("0")) == "0"


def test_format_decimal_renders_negative_with_leading_minus() -> None:
    assert _format_decimal(Decimal("-99.99")) == "-99.99"
