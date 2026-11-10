"""Build invoice catalogues for tests."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal

from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ...iva.schema import InvoiceKind
from ..catalogue import InvoiceCatalogue
from ..enums import IvaRate, PaymentStatus
from ..models import Invoice, InvoiceLine

_YEAR = filing_year_envelope().horizon


def build_invoice_catalogue(invoices: Iterable[Invoice | Mapping[str, object]]) -> InvoiceCatalogue:
    """Validate ``invoices`` into an immutable catalogue."""
    return InvoiceCatalogue.model_validate(tuple(invoices))


def consulting_invoice(
    *,
    payment_status: PaymentStatus,
    invoice_number: str = "INV-001",
    issued_at: date = date(_YEAR, 4, 1),
    kind: InvoiceKind = InvoiceKind.ISSUED,
    linked_transaction_ids: tuple[str, ...] = (),
) -> Invoice:
    """One 100,00 consulting line at 21 % issued to Cliente SL; build it under a pinned authority."""
    line = InvoiceLine(
        description="Consultoría",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=Decimal("21.00"),
    )
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": invoice_number,
            "issued_at": issued_at,
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": payment_status,
            "linked_transaction_ids": linked_transaction_ids,
        },
    )
