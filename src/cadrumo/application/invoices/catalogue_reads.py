"""Application query projections for invoice CLI surfaces.

Query functions take an :class:`InvoiceCatalogue` the caller has already
loaded, so the bucket a read is scoped to stays the caller's decision.
:func:`verify_invoice_repository_links` is the exception: it loads both the
:class:`InvoiceCatalogueRepository` and the
:class:`TransactionCatalogueRepository` for an explicit bucket, because a
one-sided link is only meaningful across the pair.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core.identity import InvoiceId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.parsing import IsoCurrencyCode
from ...domain.invoices.models import Invoice, InvoiceCatalogue
from ...domain.invoices.service import LinkInconsistency, find_unmatched, verify_link_consistency
from ...domain.iva.classification import InvoiceKind


class InvoiceListRow(BaseModel):
    """Rendered invoice summary owned by the application layer."""

    model_config = STRICT_FROZEN_CONFIG

    invoice_id: InvoiceId
    kind: InvoiceKind
    issued_at: date
    counterparty_name: str
    grand_total: Decimal
    currency: IsoCurrencyCode
    payment_status: str


def list_invoice_rows(catalogue: InvoiceCatalogue, *, kind: InvoiceKind | None = None) -> tuple[InvoiceListRow, ...]:
    """Return sorted :class:`InvoiceListRow` summary rows from an :class:`InvoiceCatalogue`."""
    rows = (_row_from_invoice(invoice) for invoice in catalogue.values() if kind is None or invoice.kind is kind)
    return tuple(sorted(rows, key=lambda item: (item.issued_at, item.invoice_id)))


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
