"""Independent public-state expectations for LEDGER-01 frontend continuation.

Installed drivers supply observations from each frontend.  These assertions
compare canonical facts, rather than trusting a screen-close or command status.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

type Frontend = Literal["cli", "tui"]


@dataclass(frozen=True, slots=True)
class ContinuationPlan:
    """One isolated store and the meaningful operation required at handoff."""

    first: Frontend
    second: Frontend
    first_operation: Literal["capture_invoice", "capture_transaction"]
    second_operation: Literal["update_invoice_notes", "edit_transaction_detail"]


CONTINUATION_PLANS = (
    ContinuationPlan("cli", "tui", "capture_invoice", "update_invoice_notes"),
    ContinuationPlan("tui", "cli", "capture_transaction", "edit_transaction_detail"),
)


@dataclass(frozen=True, slots=True)
class InvoiceObservation:
    """Canonical invoice values read from a public frontend after reopening."""

    bucket_id: str
    invoice_id: str
    notes: str | None
    grand_total: Decimal
    linked_transaction_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TransactionObservation:
    """Canonical transaction values read from a public frontend after reopening."""

    bucket_id: str
    transaction_id: str
    description: str
    amount: Decimal
    invoice_id: str | None
    predecessor_ids: tuple[str, ...] = ()


def assert_invoice_metadata_continuation(
    before: InvoiceObservation,
    after: InvoiceObservation,
    *,
    expected_notes: str,
) -> None:
    """Prove a supported note edit retained the same invoice and links."""
    if before.notes == expected_notes or after.notes != expected_notes:
        raise AssertionError("invoice notes did not make the required transition")
    if (
        before.bucket_id,
        before.invoice_id,
        before.grand_total,
        before.linked_transaction_ids,
    ) != (
        after.bucket_id,
        after.invoice_id,
        after.grand_total,
        after.linked_transaction_ids,
    ):
        raise AssertionError("invoice identity, amount, bucket or links changed during metadata edit")


def assert_linked_identity_refusal(
    before_invoice: InvoiceObservation,
    after_invoice: InvoiceObservation,
    before_transaction: TransactionObservation,
    after_transaction: TransactionObservation,
) -> None:
    """Require both public records to remain identical after a refused edit."""
    if before_transaction.invoice_id != before_invoice.invoice_id:
        raise AssertionError("starting transaction is not linked to the observed invoice")
    if before_transaction.transaction_id not in before_invoice.linked_transaction_ids:
        raise AssertionError("starting invoice lacks the reciprocal transaction link")
    if before_invoice != after_invoice or before_transaction != after_transaction:
        raise AssertionError("refused linked identity edit changed persisted public state")


def assert_unlinked_detail_continuation(
    before: TransactionObservation,
    after: TransactionObservation,
    *,
    expected_description: str,
) -> None:
    """Prove a public unlinked edit retained its scope and edit lineage."""
    if before.invoice_id is not None or after.invoice_id is not None:
        raise AssertionError("this continuation requires an unlinked transaction")
    if before.description == expected_description or after.description != expected_description:
        raise AssertionError("transaction detail did not make the required transition")
    if before.bucket_id != after.bucket_id or before.amount != after.amount:
        raise AssertionError("transaction bucket or amount changed during detail edit")
    if before.transaction_id != after.transaction_id and before.transaction_id not in after.predecessor_ids:
        raise AssertionError("replacement transaction lost its predecessor identity")


__all__ = [
    "CONTINUATION_PLANS",
    "ContinuationPlan",
    "InvoiceObservation",
    "TransactionObservation",
    "assert_invoice_metadata_continuation",
    "assert_linked_identity_refusal",
    "assert_unlinked_detail_continuation",
]
