"""The stored invoices and the recorded answer the duplicate rule's desktop recording holds."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from ...iva.schema import InvoiceKind
from ..duplicates import likely_duplicate_invoice
from ..models import Invoice
from .payment_matching_support import build_invoice

_CENT = Decimal("0.01")
_GENERAL_RATE_DIVISOR = Decimal("1.21")


def stored_invoice(entry: Mapping[str, str]) -> Invoice:
    """The stored invoice ``entry`` states, with a general-rate cuota inside its stated total."""
    grand_total = Decimal(entry["grand_total"])
    base = (grand_total / _GENERAL_RATE_DIVISOR).quantize(_CENT, rounding=ROUND_HALF_UP)
    invoice = build_invoice(
        entry["invoice_number"],
        kind=entry["kind"],
        issued=entry["issued_at"],
        tax_id=entry["counterparty_tax_id"] or None,
        base=str(base),
    )
    if invoice.grand_total != grand_total:
        raise ValueError(f"{entry['invoice_id']}: {grand_total} is not a base plus 21 % cuota")
    return invoice


def recorded_duplicate_answer(
    invoices: Iterable[Mapping[str, str]], question: Mapping[str, str | None]
) -> dict[str, str | None]:
    """The stored invoice the rule names for ``question`` among ``invoices``, and the basis it names it on."""
    kind = question["kind"]
    number = question["invoice_number"]
    invoice_date = question["invoice_date"]
    grand_total = question["grand_total"]
    labels: dict[str, str] = {}
    stored: list[Invoice] = []
    for entry in invoices:
        invoice = stored_invoice(entry)
        labels[invoice.invoice_id] = entry["invoice_id"]
        stored.append(invoice)
    found = likely_duplicate_invoice(
        stored,
        kind=InvoiceKind(kind),
        invoice_number=number,
        counterparty_tax_id=question["counterparty_tax_id"],
        invoice_date=None if invoice_date is None else date.fromisoformat(invoice_date),
        grand_total=None if grand_total is None else Decimal(grand_total),
    )
    return {"invoice_id": labels[found.invoice_id] if found else None, "basis": found.basis if found else None}
