"""Application lifecycle services for the rich catalogue :class:`Invoice`.

Reads and mutates the :class:`InvoiceCatalogue` aggregate.

The reconciliation catalogue gained ``create`` and ``list`` operator verbs but
no way to inspect or delete a single record. Without a single-record read an
operator cannot confirm the long content-addressed ``invoice_id`` that
``aeat app ledger link --invoice-id`` resolves, nor see which transactions a
catalogue invoice already binds; without a delete a mistaken
``catalogue create`` is permanent. These two services close that CRUD gap over
the same sanctioned :class:`InvoiceCatalogueRepository` write path
(``composition-service-no-parallel-write-path``), keeping the slim-vs-rich
split intact.

:func:`resolve_catalogue_invoice` resolves a full id or an unambiguous prefix
to one :class:`Invoice`. :func:`remove_catalogue_invoice` deletes one record,
refusing an invoice that still carries ``linked_transaction_ids`` so the
bidirectional link recorded on the transaction side is never silently orphaned
into a one-sided inconsistency (``verify_link_consistency``).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceCatalogueRepositoryProtocol,
    InvoiceNotFoundError,
    InvoiceValidationError,
)


class CatalogueInvoiceRemoveResult(BaseModel):
    """Result of deleting one rich catalogue invoice."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoice: Invoice
    catalogue: InvoiceCatalogue


def resolve_catalogue_invoice(catalogue: InvoiceCatalogue, invoice_id: str) -> Invoice:
    """Return one :class:`InvoiceCatalogue` invoice by full id or unambiguous prefix.

    A catalogue invoice carries a long content-addressed id; operators rarely
    type it in full. An exact match wins outright. Otherwise a case-sensitive
    prefix is accepted only when it is unambiguous: a prefix that matches more
    than one invoice is refused with the candidate set named, never silently
    resolved to the first hit.

    Raises:
        InvoiceNotFoundError: when no invoice matches the id or prefix.
        InvoiceValidationError: when a prefix matches more than one invoice.
    """
    trimmed = invoice_id.strip()
    if not trimmed:
        raise InvoiceNotFoundError(
            "invoice id is required",
            translated_message="application.invoices.lifecycle.errors.invoice_id_required",
        )
    exact = catalogue.get(trimmed)
    if exact is not None:
        return exact
    matches = tuple(invoice for invoice in catalogue.values() if invoice.invoice_id.startswith(trimmed))
    if not matches:
        raise InvoiceNotFoundError(
            f"catalogue invoice not found: {trimmed}",
            translated_message="application.invoices.lifecycle.errors.invoice_not_found",
            context={"invoice_id": trimmed},
        )
    if len(matches) > 1:
        candidates = ", ".join(invoice.invoice_id for invoice in matches)
        raise InvoiceValidationError(
            "invoice id prefix is ambiguous",
            translated_message="application.invoices.lifecycle.errors.ambiguous_invoice_prefix",
            context={"invoice_id": trimmed, "candidates": candidates},
        )
    return matches[0]


def resolve_catalogue_invoice_from_repository(
    *,
    bucket_id: str,
    invoice_id: str,
    repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> Invoice:
    """Load the catalogue and resolve one invoice by id or unambiguous prefix."""
    repo = repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    return resolve_catalogue_invoice(repo.load(), invoice_id)


def remove_catalogue_invoice(
    *,
    bucket_id: str,
    invoice_id: str,
    repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> CatalogueInvoiceRemoveResult:
    """Delete one rich catalogue invoice and return the updated catalogue.

    The id is resolved by full match or unambiguous prefix. An invoice that
    still carries ``linked_transaction_ids`` is refused: deleting it from the
    catalogue alone would leave the transaction side citing a vanished invoice
    — a one-sided link ``verify_link_consistency`` flags. The operator must
    unlink first. The write rides the sanctioned
    :class:`InvoiceCatalogueRepository`; no parallel write path is introduced.
    """
    repo = repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    catalogue = repo.load()
    invoice = resolve_catalogue_invoice(catalogue, invoice_id)
    if invoice.linked_transaction_ids:
        linked = ", ".join(invoice.linked_transaction_ids)
        raise InvoiceValidationError(
            "cannot remove an invoice that is still linked to transactions",
            translated_message="application.invoices.lifecycle.errors.remove_linked_invoice",
            context={"invoice_id": invoice.invoice_id, "linked_transaction_ids": linked},
        )
    remaining = {key: value for key, value in catalogue.invoices.items() if key != invoice.invoice_id}
    new_catalogue = InvoiceCatalogue.model_validate({"invoices": remaining})
    repo.save(new_catalogue)
    return CatalogueInvoiceRemoveResult(invoice=invoice, catalogue=new_catalogue)


__all__ = [
    "CatalogueInvoiceRemoveResult",
    "remove_catalogue_invoice",
    "resolve_catalogue_invoice",
    "resolve_catalogue_invoice_from_repository",
]
