"""Application service for invoice reconciliation workflows.

:func:`reconcile_invoice_catalogues` accepts an :class:`InvoiceCatalogue`
and a :class:`TransactionCatalogue` directly.
:func:`reconcile_invoice_repositories` is the CLI-facing backend: it loads
an :class:`InvoiceCatalogueRepository` and a
:class:`TransactionCatalogueRepository`, optionally applies every suggested
link, and writes the mutated catalogues back.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core.identity import InvoiceId, TransactionId
from ...domain.invoices import (
    InvoiceCatalogue,
    InvoiceError,
    ReconciliationSuggestion,
    link_transaction,
    suggest_reconciliations,
)
from ...domain.transactions import (
    TransactionCatalogue,
    TransactionError,
    link_invoice,
)


class ReconciliationSkippedSuggestion(BaseModel):
    """A reconciliation suggestion the backend could not safely apply."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoice_id: InvoiceId
    transaction_id: TransactionId
    reason: str


class InvoiceReconciliationResult(BaseModel):
    """Complete backend result for an invoice reconciliation run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    suggestions: tuple[ReconciliationSuggestion, ...]
    applied: int = Field(default=0, ge=0)
    skipped: tuple[ReconciliationSkippedSuggestion, ...] = ()
    invoices: InvoiceCatalogue
    transactions: TransactionCatalogue


def reconcile_invoice_catalogues(
    invoices: InvoiceCatalogue,
    transactions: TransactionCatalogue,
    *,
    apply: bool = False,
) -> InvoiceReconciliationResult:
    """Build reconciliation suggestions and optionally apply them in memory.

    Args:
        invoices: The :class:`InvoiceCatalogue` to reconcile.
        transactions: The :class:`TransactionCatalogue` to reconcile against.
        apply: When ``True``, fold every safe suggestion into both
            catalogues before returning.

    Returns:
        An :class:`InvoiceReconciliationResult` containing suggestions,
        mutated catalogues when applied, and every skipped suggestion with
        its backend reason.
    """
    suggestions = suggest_reconciliations(invoices, transactions)
    if not apply or not suggestions:
        return InvoiceReconciliationResult(
            suggestions=suggestions,
            invoices=invoices,
            transactions=transactions,
        )

    pending_invoices = invoices
    pending_transactions = transactions
    skipped: list[ReconciliationSkippedSuggestion] = []
    applied = 0

    for suggestion in suggestions:
        try:
            updated_invoices = link_transaction(
                pending_invoices,
                suggestion.invoice_id,
                suggestion.transaction_id,
            )
            updated_transactions = link_invoice(
                pending_transactions,
                suggestion.transaction_id,
                suggestion.invoice_id,
            )
        except (InvoiceError, TransactionError) as exc:
            skipped.append(
                ReconciliationSkippedSuggestion(
                    invoice_id=suggestion.invoice_id,
                    transaction_id=suggestion.transaction_id,
                    reason=str(exc),
                ),
            )
            continue
        pending_invoices = updated_invoices
        pending_transactions = updated_transactions
        applied += 1

    return InvoiceReconciliationResult(
        suggestions=suggestions,
        applied=applied,
        skipped=tuple(skipped),
        invoices=pending_invoices,
        transactions=pending_transactions,
    )


def reconcile_invoice_repositories(
    *,
    bucket_id: str,
    apply: bool = False,
    # rationale: both repositories are concrete because this writer calls the
    # adapter-only co-commit escape hatches (to_secure_object_write /
    # save_with_secure_object_writes), absent from the domain protocols. The
    # sibling linking writer carries the identical note for the identical
    # reason.
    invoice_repository: InvoiceCatalogueRepository | None = None,
    transaction_repository: TransactionCatalogueRepository | None = None,
) -> InvoiceReconciliationResult:
    """Reconcile persisted invoice and transaction catalogues and return an :class:`InvoiceReconciliationResult`.

    This is the CLI-facing backend workflow. It owns catalogue loading,
    optional mutation, and persistence so entrypoints can remain a thin
    rendering layer.
    """
    invoices_repo = invoice_repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    transactions_repo = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    # Revisioned on the invoice side only: that catalogue is a SINGLETON row, so
    # an unguarded write rewrites it whole over any invoice added since the read.
    # The transaction store writes a row per transaction and carries no
    # equivalent whole-collection risk.
    invoice_catalogue, invoice_revision_id = invoices_repo.load_revisioned()
    result = reconcile_invoice_catalogues(
        invoice_catalogue,
        transactions_repo.load(),
        apply=apply,
    )
    if apply and result.applied:
        # ONE all-or-nothing write, not two. Reconciliation is what establishes
        # and removes the invoice/transaction links, so it is the last place
        # that can afford to persist one side without the other: two
        # independent saves leave a crash between them resting in exactly the
        # one-sided state verify_link_consistency reports, and the sibling
        # linking writer already commits both together for that reason.
        transactions_repo.save_with_secure_object_writes(
            result.transactions,
            (invoices_repo.to_secure_object_write(result.invoices, expected_revision_id=invoice_revision_id),),
        )
    return result
