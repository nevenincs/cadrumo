"""One issued services invoice with a single 21 % line, for invoice record tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ...iva.schema import InvoiceKind
from ..enums import IvaRate, PaymentStatus
from ..models import Invoice, InvoiceLine

_YEAR = filing_year_envelope().horizon

_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")


def issued_services_invoice(invoice_number: str, **overrides: Any) -> Invoice:
    """Build a paid EUR invoice to a Spanish company; call it under a pinned authority."""
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=_CUOTA,
    )
    payload: dict[str, Any] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_number": invoice_number,
        "issued_at": date(_YEAR, 4, 15),
        "counterparty_name": "Cliente SL",
        "counterparty_tax_id": "B00015016",
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA,
        "currency": "EUR",
        "lines": (line,),
        "payment_status": PaymentStatus.PAID,
    }
    payload.update(overrides)
    return Invoice.model_validate(payload)
