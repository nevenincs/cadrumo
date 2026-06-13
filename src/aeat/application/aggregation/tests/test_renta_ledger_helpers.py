"""Focused unit tests for the pure helpers in _renta_ledger.

`_renta_ledger` ships four small pure helpers consumed by the public
``aggregate_renta_ledger_expenses`` orchestrator. The integration
suite in `test_renta_ledger.py` exercises the orchestrator end-to-
end against a synthetic ledger, but the small pure helpers it
delegates to (period resolution, direction dispatch, business-pct
scaling, detail truncation) had no direct unit-test coverage. A
regression in (for example) the MIXED-classification scaling would
silently halve every mixed-use deductible expense.

Tests here are structural / contract assertions on the helpers, not
calculation tautologies — `_business_amount` is verified against
the helper's declared contract (apply pct to amount magnitude), not
against any external authoritative-tax calculation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import Period
from ....domain.renta import RentaExpenseDirection
from ....domain.transactions import BusinessClassification, TransactionDirection
from .._errors import AggregationPeriodError
from .._renta_ledger import (
    _bounded_detail,
    _business_amount,
    _renta_direction_for,
    _resolve_annual_period,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# _resolve_annual_period — accept ANNUAL, reject monthly / quarterly
# ---------------------------------------------------------------------------


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


def test_resolve_annual_period_accepts_annual_period_instance() -> None:
    period = _period(2025, "0A")

    resolved = _resolve_annual_period(period)

    assert resolved is period


def test_resolve_annual_period_rejects_already_validated_quarterly_period() -> None:
    quarterly = _period(2025, "2T")

    with pytest.raises(AggregationPeriodError, match=r"annual|period|quarterly"):
        _resolve_annual_period(quarterly)


# ---------------------------------------------------------------------------
# _renta_direction_for — map ledger direction (+ invoice) to renta direction
# ---------------------------------------------------------------------------


def test_renta_direction_for_outgoing_maps_to_outgoing_expense() -> None:
    """OUTGOING flows out — always an expense."""
    assert _renta_direction_for(TransactionDirection.OUTGOING, None) is RentaExpenseDirection.OUTGOING_EXPENSE
    assert (
        _renta_direction_for(TransactionDirection.OUTGOING, "invoice-id-here") is RentaExpenseDirection.OUTGOING_EXPENSE
    )


def test_renta_direction_for_incoming_with_invoice_is_a_refund() -> None:
    """An INCOMING row attached to an outbound invoice is a refund."""
    assert _renta_direction_for(TransactionDirection.INCOMING, "invoice-id-here") is RentaExpenseDirection.REFUND


def test_renta_direction_for_incoming_without_invoice_is_unsupported() -> None:
    """An INCOMING row with no invoice anchor cannot map to a Renta
    expense direction — the helper must return None so the caller can
    flag the row as unsupported."""
    assert _renta_direction_for(TransactionDirection.INCOMING, None) is None


# ---------------------------------------------------------------------------
# _business_amount — apply BusinessClassification to the amount magnitude
# ---------------------------------------------------------------------------


def test_business_amount_business_classification_preserves_magnitude() -> None:
    """BUSINESS rows pass through the canonical amount magnitude; business_pct ignored."""
    assert _business_amount(Decimal("100.00"), BusinessClassification.BUSINESS, None) == Decimal("100.00")


def test_business_amount_mixed_classification_scales_by_business_pct() -> None:
    """MIXED rows multiply amount magnitude by the operator-declared
    business percentage — for example a 60% business-use phone bill of
    100 EUR yields a 60 EUR deductible base."""
    result = _business_amount(Decimal("100.00"), BusinessClassification.MIXED, Decimal("0.60"))

    assert result == Decimal("60.00")


def test_business_amount_rejects_negative_amount() -> None:
    with pytest.raises(ValueError, match="non-negative magnitude"):
        _business_amount(Decimal("-100.00"), BusinessClassification.MIXED, Decimal("0.30"))


def test_business_amount_personal_classification_returns_none() -> None:
    """PERSONAL spend never produces a deductible base."""
    assert _business_amount(Decimal("100.00"), BusinessClassification.PERSONAL, None) is None


# ---------------------------------------------------------------------------
# _bounded_detail — truncate to 512 chars with ellipsis on overflow
# ---------------------------------------------------------------------------


def test_bounded_detail_passes_short_string_through_unchanged() -> None:
    assert _bounded_detail("short") == "short"


def test_bounded_detail_passes_exactly_512_chars_through_unchanged() -> None:
    payload = "x" * 512

    assert _bounded_detail(payload) == payload


def test_bounded_detail_truncates_at_509_plus_ellipsis_when_over_512() -> None:
    """A 600-char string becomes 509 original chars + 3-char ellipsis = 512."""
    payload = "a" * 600

    result = _bounded_detail(payload)

    assert len(result) == 512
    assert result.endswith("...")
    assert result.startswith("a" * 509)
