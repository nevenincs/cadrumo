"""Application service for explicit invoice-to-transaction linking."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceLinkError,
)
from ...domain.invoices._service import link_transaction
from ...domain.transactions import (
    TransactionCatalogue,
    TransactionCatalogueRepository,
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
    """Return catalogues where the invoice and transaction cite each other."""

    canonical_transaction_id = _canonical_transaction_id(transactions, transaction_id)
    updated_invoices = link_transaction(invoices, invoice_id, canonical_transaction_id)
    updated_transactions = link_invoice(transactions, canonical_transaction_id, invoice_id)
    linked_invoice = updated_invoices.get(invoice_id)
    if linked_invoice is None:
        raise InvoiceLinkError(f"invoice not found after link update: {invoice_id}")
    return InvoiceTransactionLinkResult(
        invoice_id=invoice_id,
        transaction_id=canonical_transaction_id,
        invoice=linked_invoice,
        invoices=updated_invoices,
        transactions=updated_transactions,
    )


def link_invoice_transaction_repositories(
    *,
    invoice_id: str,
    transaction_id: str,
    invoice_repository: InvoiceCatalogueRepository | None = None,
    transaction_repository: TransactionCatalogueRepository | None = None,
) -> InvoiceTransactionLinkResult:
    """Persist a bidirectional invoice link through the backend repositories."""

    invoices_repo = invoice_repository or InvoiceCatalogueRepository()
    transactions_repo = transaction_repository or TransactionCatalogueRepository()
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
    raise InvoiceLinkError(f"transaction not found in catalogue: {transaction_id}")
