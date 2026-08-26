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
calculation tautologies: business proportion dispatch is verified
against its declared contract, and amount scaling is verified only
against the local non-negative magnitude contract.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import PROSE_ELISION_MARKER
from ....domain.renta import RentaExpenseDirection
from ....domain.transactions import BusinessClassification, TransactionDirection
from .._business_proportion import business_proportion
from .._renta_ledger import (
    RentaLedgerAggregationIssue,
    RentaLedgerAggregationIssueReason,
    _business_fact_amount,
    _renta_direction_for,
    _resolve_annual_period,
)
from ..errors import AggregationPeriodError
from ._renta_income_aggregation_support import _period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# _resolve_annual_period — accept ANNUAL, reject monthly / quarterly
# ---------------------------------------------------------------------------


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
# business_proportion + _business_fact_amount - classify then scale magnitude
# ---------------------------------------------------------------------------


def test_business_proportion_business_classification_preserves_magnitude() -> None:
    """BUSINESS rows pass through the canonical amount magnitude; business_pct ignored."""
    proportion = business_proportion(BusinessClassification.BUSINESS, None)

    assert proportion is not None
    assert proportion == Decimal("1")
    assert _business_fact_amount(Decimal("100.00"), proportion) == Decimal("100.00")


def test_business_proportion_mixed_classification_scales_by_business_pct() -> None:
    """MIXED rows multiply amount magnitude by the operator-declared
    business percentage — for example a 60% business-use phone bill of
    100 EUR yields a 60 EUR deductible base."""
    proportion = business_proportion(BusinessClassification.MIXED, Decimal("0.60"))
    assert proportion is not None
    assert proportion == Decimal("0.60")

    result = _business_fact_amount(Decimal("100.00"), proportion)

    assert result == Decimal("60.00")


def test_business_fact_amount_rejects_negative_amount() -> None:
    with pytest.raises(ValueError, match="non-negative magnitude"):
        _business_fact_amount(Decimal("-100.00"), Decimal("0.30"))


def test_business_proportion_personal_classification_returns_none() -> None:
    """PERSONAL spend never produces a deductible base."""
    assert business_proportion(BusinessClassification.PERSONAL, None) is None


# ---------------------------------------------------------------------------
# RentaLedgerAggregationIssue.detail — the cap elides, it does not refuse
# ---------------------------------------------------------------------------


#: A real hex-64 shape: RentaLedgerAggregationIssue.transaction_id is typed
#: core.identity.TransactionId, so a placeholder like the prior "tx-1"
#: literal no longer validates.
_TRANSACTION_ID = "9f14b6c1a8f16d4b5cf5f177797a2c5e1d0b3e6a5f6d0c3b1a8f16d4b5cf5f17"


def _issue(detail: str) -> RentaLedgerAggregationIssue:
    return RentaLedgerAggregationIssue(
        transaction_id=_TRANSACTION_ID,
        reason=RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
        detail=detail,
    )


def test_a_detail_within_the_cap_survives_exactly() -> None:
    """Eliding must not touch the overwhelming majority of exclusions."""
    detail = "ledger row rejected: booked date falls outside the resolved annual period"

    assert _issue(detail).detail == detail


def test_an_over_cap_detail_elides_rather_than_refusing_the_issue() -> None:
    """The behaviour that keeps a rejected row explainable.

    ``detail`` carries the reason a ledger row was excluded. Refusing to build
    the issue over its length would lose the explanation AND fail the
    aggregation that produced it, turning a traceable exclusion into a raw
    validation error — a silent under-declaration wearing a crash.
    """
    issue = _issue("word " * 400)

    assert len(issue.detail) <= 512
    assert issue.detail.endswith(PROSE_ELISION_MARKER)


def test_the_elision_is_visible_so_a_cut_reason_cannot_read_as_a_terse_one() -> None:
    """An operator deciding whether to reclassify a row must know words are missing."""
    assert PROSE_ELISION_MARKER not in _issue("a short reason").detail
