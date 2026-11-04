"""The stored invoices and the recorded answer the duplicate rule's desktop recording holds."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast

from ...iva.schema import InvoiceKind
from ..duplicates import likely_duplicate_invoice
from ..models import Invoice


@dataclass(frozen=True)
class StoredInvoiceFacts:
    """The facts the rule reads, so its cases need no full invoice around them."""

    invoice_id: str
    kind: InvoiceKind
    invoice_number: str
    counterparty_tax_id: str | None
    issued_at: date
    grand_total: Decimal


def stored_invoice(entry: Mapping[str, str]) -> Invoice:
    """The stored invoice ``entry`` states, as far as the rule reads one."""
    return cast(
        Invoice,
        StoredInvoiceFacts(
            invoice_id=entry["invoice_id"],
            kind=InvoiceKind(entry["kind"]),
            invoice_number=entry["invoice_number"],
            counterparty_tax_id=entry["counterparty_tax_id"] or None,
            issued_at=date.fromisoformat(entry["issued_at"]),
            grand_total=Decimal(entry["grand_total"]),
        ),
    )


def recorded_duplicate_answer(
    invoices: Iterable[Mapping[str, str]], question: Mapping[str, str | None]
) -> dict[str, str | None]:
    """The stored invoice the rule names for ``question`` among ``invoices``, and the basis it names it on."""
    kind = question["kind"]
    number = question["invoice_number"]
    invoice_date = question["invoice_date"]
    grand_total = question["grand_total"]
    found = likely_duplicate_invoice(
        (stored_invoice(stored) for stored in invoices),
        kind=InvoiceKind(kind),
        invoice_number=number,
        counterparty_tax_id=question["counterparty_tax_id"],
        invoice_date=None if invoice_date is None else date.fromisoformat(invoice_date),
        grand_total=None if grand_total is None else Decimal(grand_total),
    )
    return {"invoice_id": found.invoice_id if found else None, "basis": found.basis if found else None}
