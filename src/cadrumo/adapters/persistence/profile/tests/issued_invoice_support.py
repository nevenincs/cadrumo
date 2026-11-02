"""A minimal issued consulting invoice for the invoice catalogue persistence suites."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from .....domain.invoices.enums import IvaRate, PaymentStatus
from .....domain.invoices.models import Invoice, InvoiceLine
from .....domain.iva.schema import InvoiceKind


def issued_consulting_invoice(invoice_number: str, *, iva_rate: IvaRate, bucket_id: str | None = None) -> Invoice:
    """Build one issued 100.00 EUR invoice at 21 percent; ``bucket_id`` attributes it to a bucket when given."""
    line = InvoiceLine.model_validate(
        {
            "description": "Consultoría",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.00"),
            "iva_rate": iva_rate,
            "iva_amount": Decimal("21.00"),
        },
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": invoice_number,
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PENDING,
            "linked_transaction_ids": (),
            **({} if bucket_id is None else {"bucket_id": bucket_id}),
        },
    )
