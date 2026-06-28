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

from ...domain.invoices import (
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceError,
)
from ...domain.invoices._protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.invoices._service import ReconciliationSuggestion, link_transaction, suggest_reconciliations
from ...domain.transactions import (
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionError,
    link_invoice,
)
from ...domain.transactions._protocols import TransactionCatalogueRepositoryProtocol


class ReconciliationSkippedSuggestion(BaseModel):
    """A reconciliation suggestion the backend could not safely apply."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoice_id: str
    transaction_id: str
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
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> InvoiceReconciliationResult:
    """Reconcile persisted invoice and transaction catalogues and return an :class:`InvoiceReconciliationResult`.

    This is the CLI-facing backend workflow. It owns catalogue loading,
    optional mutation, and persistence so entrypoints can remain a thin
    rendering layer.
    """
    invoices_repo = invoice_repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    transactions_repo = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    result = reconcile_invoice_catalogues(
        invoices_repo.load(),
        transactions_repo.load(),
        apply=apply,
    )
    if apply and result.applied:
        invoices_repo.save(result.invoices)
        transactions_repo.save(result.transactions)
    return result
