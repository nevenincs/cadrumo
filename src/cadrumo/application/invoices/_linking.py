"""Application service for explicit invoice-to-transaction linking.

:func:`link_invoice_transaction_repositories` loads both the
:class:`InvoiceCatalogue` via :class:`InvoiceCatalogueRepository` and
the :class:`TransactionCatalogue` via :class:`TransactionCatalogueRepository`,
applies the bidirectional link, and commits both updated catalogues in one
unit of work through
:meth:`TransactionCatalogueRepository.save_with_secure_object_writes`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core import SecureObjectWrite
from ...core.identity import InvoiceId, TransactionId
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceLinkError,
    link_transaction,
)
from ...domain.transactions.models import TransactionCatalogue
from ...domain.transactions.service import link_invoice


class InvoiceTransactionLinkResult(BaseModel):
    """Result of a persisted bidirectional invoice link command."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoice_id: InvoiceId
    transaction_id: TransactionId
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
    # rationale: both repositories are concrete because this writer calls the
    # adapter-only co-commit escape hatches (to_secure_object_write /
    # save_with_secure_object_writes), absent from the domain protocols.
    invoice_repository: InvoiceCatalogueRepository | None = None,
    transaction_repository: TransactionCatalogueRepository | None = None,
    extra_writes: tuple[SecureObjectWrite, ...] = (),
) -> InvoiceTransactionLinkResult:
    """Persist a bidirectional invoice link as one all-or-nothing write.

    Both sides of the link commit together: the updated invoice catalogue is
    serialised into a
    :class:`~cadrumo.adapters.persistence.storage.SecureObjectWrite`
    and handed to
    :meth:`~cadrumo.adapters.persistence.profile.transactions.TransactionCatalogueRepository.save_with_secure_object_writes`
    alongside the transaction-catalogue diff, so both land in the single
    :meth:`~cadrumo.adapters.persistence.storage.SecureObjectRepository.apply_batch`
    transaction. A crash or error mid-write rolls both back, so the catalogues
    cannot come to rest in the one-sided state
    :func:`~cadrumo.domain.invoices.verify_link_consistency` reports.

    Args:
        bucket_id: Profile bucket owning both catalogues.
        invoice_id: Identifier of the invoice to link.
        transaction_id: Identifier of the transaction to link, resolved to its
            canonical catalogue form before linking.
        invoice_repository: The concrete :class:`InvoiceCatalogueRepository`,
            constructed for ``bucket_id`` when omitted.
        transaction_repository: The concrete
            :class:`TransactionCatalogueRepository`, constructed for
            ``bucket_id`` when omitted.
        extra_writes: Further secure-object upserts to commit in the same
            unit of work as the link, such as the caller's bucket-event
            history. Treated as opaque: this service commits them atomically
            with the two catalogues but never inspects or constructs them, so
            the invoice layer stays free of event-history concerns.

    Both repositories are the concrete adapters rather than the domain
    protocols, because this writer calls the co-commit escape hatches the
    protocols do not declare.

    Returns an :class:`InvoiceTransactionLinkResult` with the updated
    invoice and transaction catalogues after the link is written.
    """
    invoices_repo = invoice_repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    transactions_repo = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    # The invoice catalogue is a SINGLETON row, so its write is revisioned: an
    # unguarded one rewrites the whole catalogue over any invoice another caller
    # added between this read and the batch. The transaction store writes a row
    # per transaction, so its side carries no equivalent whole-collection risk.
    invoice_catalogue, invoice_revision_id = invoices_repo.load_revisioned()
    result = link_invoice_transaction_catalogues(
        invoice_catalogue,
        transactions_repo.load(),
        invoice_id=invoice_id,
        transaction_id=transaction_id,
    )
    transactions_repo.save_with_secure_object_writes(
        result.transactions,
        (
            invoices_repo.to_secure_object_write(result.invoices, expected_revision_id=invoice_revision_id),
            *extra_writes,
        ),
    )
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
