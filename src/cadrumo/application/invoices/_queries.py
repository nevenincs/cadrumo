"""Application query projections for invoice CLI surfaces.

Query functions accept an :class:`InvoiceCatalogue` or load one from the
:class:`InvoiceCatalogueRepository`; :func:`verify_invoice_repository_links`
additionally loads the :class:`TransactionCatalogueRepository` to detect
one-sided links.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core.identity import InvoiceId
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.invoices.models import Invoice, InvoiceCatalogue
from ...domain.invoices.service import LinkInconsistency, find_invoice, find_unmatched, verify_link_consistency
from ...domain.iva.classification import InvoiceKind


class InvoiceListRow(BaseModel):
    """Rendered invoice summary owned by the application layer."""

    model_config = STRICT_FROZEN_CONFIG

    invoice_id: InvoiceId
    kind: InvoiceKind
    issued_at: date
    counterparty_name: str
    grand_total: Decimal
    currency: str
    payment_status: str


def list_invoice_rows(catalogue: InvoiceCatalogue, *, kind: InvoiceKind | None = None) -> tuple[InvoiceListRow, ...]:
    """Return sorted :class:`InvoiceListRow` summary rows from an :class:`InvoiceCatalogue`."""
    rows = (_row_from_invoice(invoice) for invoice in catalogue.values() if kind is None or invoice.kind is kind)
    return tuple(sorted(rows, key=lambda item: (item.issued_at, item.invoice_id)))


def list_invoice_repository_rows(*, kind: InvoiceKind | None = None) -> tuple[InvoiceListRow, ...]:
    """Load the invoice catalogue and return sorted :class:`InvoiceListRow` summaries."""
    return list_invoice_rows(InvoiceCatalogueRepository().load(), kind=kind)


def get_invoice_from_repository(invoice_id: str) -> Invoice | None:
    """Load and return one invoice from the secure catalogue.

    Returns an :class:`Invoice` when found, or ``None`` when the id
    is not present in the catalogue.
    """
    return find_invoice(InvoiceCatalogueRepository().load(), invoice_id)


def list_unmatched_invoice_rows(
    catalogue: InvoiceCatalogue,
    *,
    kind: InvoiceKind | None = None,
) -> tuple[InvoiceListRow, ...]:
    """Return sorted :class:`InvoiceListRow` summaries for invoices that are not linked to transactions.

    Args:
        catalogue: The :class:`InvoiceCatalogue` to query for unlinked invoices.
        kind: When set, restricts results to invoices of that kind.
    """
    rows = tuple(_row_from_invoice(invoice) for invoice in find_unmatched(catalogue, kind=kind))
    return tuple(sorted(rows, key=lambda item: (item.issued_at, item.invoice_id)))


def list_unmatched_invoice_repository_rows(
    *,
    kind: InvoiceKind | None = None,
) -> tuple[InvoiceListRow, ...]:
    """Load the invoice catalogue and return unmatched summary rows.

    Each element is an :class:`InvoiceListRow` sorted by issue date and
    invoice id.
    """
    return list_unmatched_invoice_rows(InvoiceCatalogueRepository().load(), kind=kind)


def verify_invoice_repository_links(*, bucket_id: str) -> tuple[LinkInconsistency, ...]:
    """Load both catalogues and return one-sided invoice/transaction links as a tuple of :class:`LinkInconsistency`."""
    return verify_link_consistency(
        InvoiceCatalogueRepository(bucket_id=bucket_id).load(),
        TransactionCatalogueRepository(bucket_id=bucket_id).load(),
    )


def _row_from_invoice(invoice: Invoice) -> InvoiceListRow:
    """Build a stable application row from one invoice."""
    return InvoiceListRow(
        invoice_id=invoice.invoice_id,
        kind=invoice.kind,
        issued_at=invoice.issued_at,
        counterparty_name=invoice.counterparty_name,
        grand_total=invoice.grand_total,
        currency=invoice.currency,
        payment_status=invoice.payment_status.value,
    )
