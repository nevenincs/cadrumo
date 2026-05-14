"""Application query projections for invoice CLI surfaces."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceKind,
)
from ...domain.invoices._service import (
    LinkInconsistency,
    find_invoice,
    find_unmatched,
    verify_link_consistency,
)
from ...domain.transactions import TransactionCatalogueRepository


class InvoiceListRow(BaseModel):
    """Rendered invoice summary owned by the application layer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    invoice_id: str
    kind: InvoiceKind
    issued_at: date
    counterparty_name: str
    grand_total: Decimal
    currency: str
    payment_status: str


def list_invoice_rows(catalogue: InvoiceCatalogue, *, kind: InvoiceKind | None = None) -> tuple[InvoiceListRow, ...]:
    """Return sorted invoice summary rows from a catalogue."""

    rows = (_row_from_invoice(invoice) for invoice in catalogue.values() if kind is None or invoice.kind is kind)
    return tuple(sorted(rows, key=lambda item: (item.issued_at, item.invoice_id)))


def list_invoice_repository_rows(*, kind: InvoiceKind | None = None) -> tuple[InvoiceListRow, ...]:
    """Load the invoice catalogue and return sorted summary rows."""

    return list_invoice_rows(InvoiceCatalogueRepository().load(), kind=kind)


def get_invoice_from_repository(invoice_id: str) -> Invoice | None:
    """Load and return one invoice from the secure catalogue."""

    return find_invoice(InvoiceCatalogueRepository().load(), invoice_id)


def list_unmatched_invoice_rows(
    catalogue: InvoiceCatalogue,
    *,
    kind: InvoiceKind | None = None,
) -> tuple[InvoiceListRow, ...]:
    """Return sorted invoice summary rows that are not linked to transactions."""

    rows = tuple(_row_from_invoice(invoice) for invoice in find_unmatched(catalogue, kind=kind))
    return tuple(sorted(rows, key=lambda item: (item.issued_at, item.invoice_id)))


def list_unmatched_invoice_repository_rows(
    *,
    kind: InvoiceKind | None = None,
) -> tuple[InvoiceListRow, ...]:
    """Load the invoice catalogue and return unmatched summary rows."""

    return list_unmatched_invoice_rows(InvoiceCatalogueRepository().load(), kind=kind)


def verify_invoice_repository_links(*, bucket_id: str) -> tuple[LinkInconsistency, ...]:
    """Load both catalogues and return one-sided invoice/transaction links."""

    return verify_link_consistency(
        InvoiceCatalogueRepository().load(),
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
