"""Which window an activity's invoice accrues in, and what a zero in a ledger box rests on.

Activity income and expense follow accrual (LIRPF art. 14.1.b) unless the
taxpayer elected cash (RIRPF art. 7.2). A box that sums bank rows can read zero
while an invoice accrued inside its window was collected outside it, so a zero
is proven only when neither a row nor an accruing invoice exists.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from ...core.aggregation import BindingValueOutcome
from ...domain.calculations.registry.invoice_legal_classification import advance_payment_received_role
from ...domain.invoices.models import Invoice
from ...domain.iva.schema import InvoiceKind


def invoice_accrual_date(invoice: Invoice) -> date | None:
    """Return the date ``invoice`` accrues on, or ``None`` when its document does not state one.

    RD 1619/2012 art. 6.1.i records an operation date only when it differs from
    expedition, so an invoice stating none documents an operation on its issue
    date. An advance-payment date is when money arrived, not when the income
    accrued, so it answers nothing here.
    """
    if invoice.operation_date is None:
        return invoice.issued_at
    if invoice.operation_date_role == advance_payment_received_role():
        return None
    return invoice.operation_date


def accruing_invoices(
    invoices: Iterable[Invoice], *, kind: InvoiceKind, bucket_id: str, start: date, end: date
) -> tuple[Invoice, ...]:
    """Return the bucket's invoices of ``kind`` that accrue in the window, an unknown accrual read at its issue date."""
    return tuple(
        invoice
        for invoice in invoices
        if invoice.kind is kind
        and invoice.bucket_id == bucket_id
        and start <= (invoice_accrual_date(invoice) or invoice.issued_at) <= end
    )


def ledger_sum_outcome(value: Decimal, *, rows_present: bool, accruing_invoice_present: bool) -> BindingValueOutcome:
    """State what one ledger-summed activity box rests on: a proven zero needs no row and no accruing invoice."""
    if value != 0 or rows_present or accruing_invoice_present:
        return BindingValueOutcome.FROM_BEARING_ROWS
    return BindingValueOutcome.PROVEN_ZERO


__all__ = ["accruing_invoices", "invoice_accrual_date", "ledger_sum_outcome"]
