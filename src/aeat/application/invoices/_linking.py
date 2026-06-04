"""Application service for explicit invoice-to-transaction linking.

:func:`link_invoice_transaction_repositories` loads both the
:class:`InvoiceCatalogue` via :class:`InvoiceCatalogueRepository` and
the :class:`TransactionCatalogue` via :class:`TransactionCatalogueRepository`,
applies the bidirectional link, and persists both updated catalogues.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceCatalogueRepositoryProtocol,
    InvoiceLinkError,
    link_transaction,
)
from ...domain.transactions import (
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionCatalogueRepositoryProtocol,
    link_invoice,
)


class InvoiceTransactionLinkResult(BaseModel):
    """Result of a persisted bidirectional invoice link command."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoice_id: str
    transaction_id: str
    invoice: Invoice
    invoices: InvoiceCatalogue
    transactions: TransactionCatalogue


def link_invoice_transaction_catalogues(
    invoices: InvoiceCatalogue,
    transactions: TransactionCatalogue,
    *,
    invoice_id: str,
    transaction_id: str,
) -> InvoiceTransactionLinkResult:
    """Link one invoice to one transaction, returning the updated catalogues.

    Returns an :class:`InvoiceTransactionLinkResult` where the invoice and
    transaction cite each other.

    Args:
        invoices: The :class:`InvoiceCatalogue` to update with the new link.
        transactions: The :class:`TransactionCatalogue` to update with the new link.
        invoice_id: Identifier of the invoice to link.
        transaction_id: Identifier of the transaction to link; resolved to its
            canonical form against ``transactions`` before linking.
    """
    canonical_transaction_id = _canonical_transaction_id(transactions, transaction_id)
    updated_invoices = link_transaction(invoices, invoice_id, canonical_transaction_id)
    updated_transactions = link_invoice(transactions, canonical_transaction_id, invoice_id)
    linked_invoice = updated_invoices.get(invoice_id)
    if linked_invoice is None:
        raise InvoiceLinkError(
            "invoice not found after link update",
            translated_message="application.invoices.linking.errors.linked_invoice_not_found",
            context={"invoice_id": invoice_id},
        )
    return InvoiceTransactionLinkResult(
        invoice_id=invoice_id,
        transaction_id=canonical_transaction_id,
        invoice=linked_invoice,
        invoices=updated_invoices,
        transactions=updated_transactions,
    )


def link_invoice_transaction_repositories(
    *,
    bucket_id: str,
    invoice_id: str,
    transaction_id: str,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> InvoiceTransactionLinkResult:
    """Persist a bidirectional invoice link through the backend repositories.

    Returns an :class:`InvoiceTransactionLinkResult` with the updated
    invoice and transaction catalogues after the link is written.
    """
    invoices_repo = invoice_repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    transactions_repo = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    result = link_invoice_transaction_catalogues(
        invoices_repo.load(),
        transactions_repo.load(),
        invoice_id=invoice_id,
        transaction_id=transaction_id,
    )
    invoices_repo.save(result.invoices)
    transactions_repo.save(result.transactions)
    return result


def _canonical_transaction_id(catalogue: TransactionCatalogue, transaction_id: str) -> str:
    """Return the catalogue key accepted by transaction services."""
    if transaction_id in catalogue:
        return transaction_id
    normalized = transaction_id.strip().lower()
    if normalized in catalogue:
        return normalized
    raise InvoiceLinkError(
        "transaction not found in catalogue",
        translated_message="application.invoices.linking.errors.transaction_not_found",
        context={"transaction_id": transaction_id},
    )
