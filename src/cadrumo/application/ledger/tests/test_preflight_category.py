"""Category-readiness checks for ledger modelo preflight."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ..preflight import LedgerPreflightIssueReason, preflight_transaction_catalogue
from ._preflight_test_support import _BUCKET_ID, _Q2_2026, _raw_transaction, _transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_preflight_does_not_flag_missing_category_on_income_transaction() -> None:
    """Income direction does not require the deductible-expense category key."""
    income = _transaction(
        "row-income",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("1500.00"),
        category_id=None,
        taxable_base=Decimal("1239.67"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("260.33"),
    )

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((income,)),
    )

    assert report.checked_transaction_count == 1
    assert LedgerPreflightIssueReason.MISSING_CATEGORY not in {issue.reason for issue in report.issues}
    assert report.ready is True


def test_preflight_still_flags_missing_category_on_expense_transaction() -> None:
    """Expense direction still requires the deductible-expense category key."""
    expense = _transaction(
        "row-expense",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("121.00"),
        category_id=None,
    )

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((expense,)),
    )

    assert LedgerPreflightIssueReason.MISSING_CATEGORY in {issue.reason for issue in report.issues}


def test_preflight_flags_missing_category_on_income_refund_with_purchase_evidence() -> None:
    """Purchase-evidence income is an expense refund, so it needs a category."""
    refund = Transaction.model_validate(
        {
            "raw": _raw_transaction("row-refund", amount=Decimal("45.00")),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "business_pct": None,
            "category_id": None,
            "purchase_invoice_evidence_id": "evidence-001",
            "taxable_base": Decimal("37.19"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("7.81"),
            "usage_ratio_id": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((refund,)),
    )

    assert LedgerPreflightIssueReason.MISSING_CATEGORY in {issue.reason for issue in report.issues}
