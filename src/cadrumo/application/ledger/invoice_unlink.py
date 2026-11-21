"""Remove one movement's link to a catalogue invoice.

``ledger.link`` binds a movement and an invoice by writing both sides of the
relationship: the movement's ``invoice_id`` and the invoice's
``linked_transaction_ids``. A wrong link had no way back, so a person who linked
the wrong invoice could only remove the movement. This service is that way back.

The unlink clears both sides and records a
:attr:`~cadrumo.domain.buckets.event.BucketEventType.LEDGER_TRANSACTION_INVOICE_UNLINKED`
event naming the movement, the invoice and the actor, all in one revision-guarded
secure-object batch, exactly as the link co-commits its two catalogues and its
event. The link's own event stays in the history: the history is appended to,
never rewritten.

Every reason the unlink cannot go ahead is a typed refusal naming its cause and
the next step, decided before anything is written. A finalized calculation that
cites the movement sealed the link (the movement's filing snapshot carries its
``invoice_id``), so that is refused until the calculation is reopened.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ...core.errors.hierarchy import CadrumoError
from ...domain.buckets.event import BucketEventType
from ...domain.buckets.event_repository import bucket_event_history_write
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.models import Invoice
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ..invoices.transaction_linking import unlink_invoice_transaction_catalogues
from .action_ports import LedgerActionPorts
from .actions_common import (
    blocking_modelo_references,
    build_ledger_bucket_event,
    normalise_timestamp,
    require_actor,
    require_source_command,
    resolve_bucket_event_repository,
    resolve_invoice_repository,
    resolve_revision_guarded_transaction_repository,
    transaction_modelo_source_ids,
)
from .models import LedgerRemovalBlocker
from .persistence_ports import LedgerPersistenceConflictError

__all__ = [
    "InvoiceUnlinkCause",
    "InvoiceUnlinkNextStep",
    "InvoiceUnlinkRefusedError",
    "InvoiceUnlinkResult",
    "unlink_manual_transaction_invoice",
]


class InvoiceUnlinkCause(StrEnum):
    """Why removing a movement's invoice link was refused."""

    LINK_NOT_FOUND = "link_not_found"
    """Neither the movement nor the invoice cites the other, or one of them does not exist."""

    TRANSACTION_CHANGED = "transaction_changed"
    """The movement changed after the person opened it."""

    INVOICE_CHANGED = "invoice_changed"
    """The invoice's links changed after the person opened it."""

    FINALIZED_CALCULATION_REFERENCE = "finalized_calculation_reference"
    """A finalized calculation cites the movement, and the link is part of what it sealed."""


class InvoiceUnlinkNextStep(StrEnum):
    """What the person can do about a refused unlink."""

    REOPEN_TRANSACTION = "reopen_transaction"
    """Reopen the movement to see its current link, then decide again."""

    REOPEN_INVOICE = "reopen_invoice"
    """Reopen the invoice to see its current links, then decide again."""

    REOPEN_FINALIZED_CALCULATION = "reopen_finalized_calculation"
    """Reopen or amend the finalized calculation that cites the movement first."""


_NEXT_STEP: dict[InvoiceUnlinkCause, InvoiceUnlinkNextStep] = {
    InvoiceUnlinkCause.LINK_NOT_FOUND: InvoiceUnlinkNextStep.REOPEN_TRANSACTION,
    InvoiceUnlinkCause.TRANSACTION_CHANGED: InvoiceUnlinkNextStep.REOPEN_TRANSACTION,
    InvoiceUnlinkCause.INVOICE_CHANGED: InvoiceUnlinkNextStep.REOPEN_INVOICE,
    InvoiceUnlinkCause.FINALIZED_CALCULATION_REFERENCE: InvoiceUnlinkNextStep.REOPEN_FINALIZED_CALCULATION,
}


class InvoiceUnlinkRefusedError(CadrumoError):
    """An invoice unlink refused before any write."""

    def __init__(self, cause: InvoiceUnlinkCause, *, blockers: tuple[LedgerRemovalBlocker, ...] = ()) -> None:
        """Keep the typed cause, its next step and the finalized revisions that block it."""
        super().__init__(
            f"invoice unlink refused: {cause.value}",
            context={"cause": cause.value, "next_step": _NEXT_STEP[cause].value},
        )
        self.cause = cause
        self.next_step = _NEXT_STEP[cause]
        self.blockers = blockers


@dataclass(frozen=True, slots=True)
class InvoiceUnlinkResult:
    """The unlinked movement, the invoice's remaining links and the recorded event."""

    transaction: Transaction
    invoice: Invoice
    bucket_event_ids: tuple[str, ...]


def unlink_manual_transaction_invoice(
    *,
    bucket_id: str,
    transaction_id: str,
    invoice_id: str,
    expected_modified_at: datetime,
    expected_invoice_linked_transaction_ids: tuple[str, ...],
    actor: str,
    source_command: str,
    ports: LedgerActionPorts,
    occurred_at: datetime | None = None,
) -> InvoiceUnlinkResult:
    """Remove the link between one movement and one invoice, recording the removal.

    ``expected_modified_at`` is the movement's ``modified_at`` and
    ``expected_invoice_linked_transaction_ids`` the invoice's links the person saw;
    a movement or invoice that differs from them is refused rather than changed.
    A one-sided link (only the movement or only the invoice citing the other) is
    removed the same way, so the person can repair it.

    Raises:
        InvoiceUnlinkRefusedError: For every refusal, before any write.
    """
    trimmed_actor = require_actor(actor, operation="ledger invoice unlinkage")
    trimmed_source_command = require_source_command(source_command, operation="ledger invoice unlinkage")
    transactions_repo = resolve_revision_guarded_transaction_repository(
        bucket_id=bucket_id, repository=ports.transaction_repository
    )
    invoices_repo = resolve_invoice_repository(bucket_id=bucket_id, repository=ports.invoice_repository)
    event_repository = resolve_bucket_event_repository(bucket_id=bucket_id, repository=ports.bucket_event_repository)
    invoices, invoice_revision_id = invoices_repo.load_revisioned()
    transactions, transaction_revision_id = transactions_repo.load_revisioned()
    current = _plan(
        transactions,
        invoices,
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        invoice_id=invoice_id,
        expected_modified_at=expected_modified_at,
        expected_invoice_linked_transaction_ids=expected_invoice_linked_transaction_ids,
        ports=ports,
    )
    updated_invoices, updated_transactions = unlink_invoice_transaction_catalogues(
        invoices, transactions, invoice_id=invoice_id, transaction_id=current.transaction_id
    )
    event = build_ledger_bucket_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_INVOICE_UNLINKED,
        occurred_at=normalise_timestamp(occurred_at),
        actor=trimmed_actor,
        object_id=current.transaction_id,
        # Identifiers and the operator's verb only, as for the link: invoice
        # content never enters the event history.
        payload={
            "invoice_id": invoice_id,
            "source_command": trimmed_source_command,
            "mutation_kind": "invoice_unlinkage",
        },
    )
    try:
        transactions_repo.save_if_revision_with_secure_object_writes(
            updated_transactions,
            expected_revision_id=transaction_revision_id,
            extra_writes=(
                invoices_repo.to_secure_object_write(updated_invoices, expected_revision_id=invoice_revision_id),
                bucket_event_history_write(event_repository, (event,)),
            ),
        )
    except LedgerPersistenceConflictError as conflict:
        # The batch rolled back whole. Name what changed by re-deciding against
        # the stored state; a change the person's view still matches is a
        # concurrent write to the movement catalogue.
        fresh_invoices, _ = invoices_repo.load_revisioned()
        fresh_transactions, _ = transactions_repo.load_revisioned()
        _plan(
            fresh_transactions,
            fresh_invoices,
            bucket_id=bucket_id,
            transaction_id=transaction_id,
            invoice_id=invoice_id,
            expected_modified_at=expected_modified_at,
            expected_invoice_linked_transaction_ids=expected_invoice_linked_transaction_ids,
            ports=ports,
        )
        raise InvoiceUnlinkRefusedError(InvoiceUnlinkCause.TRANSACTION_CHANGED) from conflict
    transaction = updated_transactions.get(current.transaction_id)
    invoice = updated_invoices.get(invoice_id)
    if transaction is None or invoice is None:
        raise InvoiceUnlinkRefusedError(InvoiceUnlinkCause.LINK_NOT_FOUND)
    return InvoiceUnlinkResult(transaction=transaction, invoice=invoice, bucket_event_ids=(event.event_id,))


def _plan(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    bucket_id: str,
    transaction_id: str,
    invoice_id: str,
    expected_modified_at: datetime,
    expected_invoice_linked_transaction_ids: tuple[str, ...],
    ports: LedgerActionPorts,
) -> Transaction:
    """Decide every refusal from the stored movement, invoice and citing calculations."""
    current = transactions.get(transaction_id)
    invoice = invoices.get(invoice_id)
    if current is None or invoice is None or invoice.bucket_id not in (None, bucket_id):
        raise InvoiceUnlinkRefusedError(InvoiceUnlinkCause.LINK_NOT_FOUND)
    if current.invoice_id != invoice_id and current.transaction_id not in invoice.linked_transaction_ids:
        raise InvoiceUnlinkRefusedError(InvoiceUnlinkCause.LINK_NOT_FOUND)
    if current.modified_at != expected_modified_at:
        raise InvoiceUnlinkRefusedError(InvoiceUnlinkCause.TRANSACTION_CHANGED)
    if sorted(invoice.linked_transaction_ids) != sorted(expected_invoice_linked_transaction_ids):
        raise InvoiceUnlinkRefusedError(InvoiceUnlinkCause.INVOICE_CHANGED)
    blockers = blocking_modelo_references(
        bucket_id=bucket_id,
        transaction_ids=transaction_modelo_source_ids(current),
        work_unit_repository=ports.work_unit_repository,
        calculation_repository=ports.calculation_repository,
    )
    if blockers:
        # The movement's filing snapshot carries its invoice_id and the invoice
        # side pairs the movement as its payment, so removing the link under a
        # finalized revision would change what that revision sealed.
        raise InvoiceUnlinkRefusedError(InvoiceUnlinkCause.FINALIZED_CALCULATION_REFERENCE, blockers=blockers)
    return current
