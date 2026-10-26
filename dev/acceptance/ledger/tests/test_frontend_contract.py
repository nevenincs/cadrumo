"""Detection checks for the public LEDGER-01 continuation assertions."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from ..frontend_contract import (
    CONTINUATION_PLANS,
    InvoiceObservation,
    TransactionObservation,
    assert_invoice_metadata_continuation,
    assert_linked_identity_refusal,
    assert_unlinked_detail_continuation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _linked_pair() -> tuple[InvoiceObservation, TransactionObservation]:
    invoice = InvoiceObservation("synthetic-bucket", "invoice-1", "before", Decimal("121.00"), ("transaction-1",))
    transaction = TransactionObservation(
        "synthetic-bucket", "transaction-1", "settlement", Decimal("121.00"), invoice.invoice_id
    )
    return invoice, transaction


def test_continuations_require_a_meaningful_second_frontend_operation() -> None:
    assert {(plan.first, plan.second) for plan in CONTINUATION_PLANS} == {
        ("cli", "tui"),
        ("tui", "cli"),
    }
    assert all(
        plan.second_operation in {"update_invoice_notes", "edit_transaction_detail"} for plan in CONTINUATION_PLANS
    )


def test_metadata_edit_assertion_detects_a_dropped_link_and_a_false_success() -> None:
    before, _ = _linked_pair()
    after = replace(before, notes="after")
    assert_invoice_metadata_continuation(before, after, expected_notes="after")
    with pytest.raises(AssertionError, match="transition"):
        assert_invoice_metadata_continuation(before, before, expected_notes="after")
    with pytest.raises(AssertionError, match="links"):
        assert_invoice_metadata_continuation(before, replace(after, linked_transaction_ids=()), expected_notes="after")


def test_refusal_assertion_detects_one_sided_link_or_transaction_mutation() -> None:
    invoice, transaction = _linked_pair()
    assert_linked_identity_refusal(invoice, invoice, transaction, transaction)
    with pytest.raises(AssertionError, match="reciprocal"):
        assert_linked_identity_refusal(replace(invoice, linked_transaction_ids=()), invoice, transaction, transaction)
    with pytest.raises(AssertionError, match="changed persisted"):
        assert_linked_identity_refusal(invoice, invoice, transaction, replace(transaction, amount=Decimal("122.00")))


def test_unlinked_edit_assertion_requires_predecessor_lineage() -> None:
    before = TransactionObservation("synthetic-bucket", "old", "before", Decimal("10.00"), None)
    after = replace(before, transaction_id="new", description="after", predecessor_ids=("old",))
    assert_unlinked_detail_continuation(before, after, expected_description="after")
    with pytest.raises(AssertionError, match="predecessor"):
        assert_unlinked_detail_continuation(before, replace(after, predecessor_ids=()), expected_description="after")
