"""Synthetic invoice facts shared by live calculation and installed Modelo 349 tests.

These three distinct intra-community supplies belong to the first quarter of
2026. Callers supply their isolated profile bucket; this module creates facts
and leaves storage and calculation to the owning test harness.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...domain.invoices.enums import PaymentStatus, resolve_iva_rate_slot
from ...domain.invoices.models import Invoice, InvoiceLine, derive_invoice_id
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.schema import IvaCategory

M349_INVOICES: tuple[tuple[str, str, str, date, Decimal], ...] = (
    ("F-2026-001", "DE", "DE123456789", date(2026, 1, 15), Decimal("1000.00")),
    ("F-2026-002", "FR", "FR12345678901", date(2026, 2, 10), Decimal("2500.50")),
    ("F-2026-003", "IT", "IT12345678901", date(2026, 3, 5), Decimal("740.25")),
)
M349_EXPECTED_IMPORTE = Decimal("4240.75")
M349_EXPECTED_OPERADORES = Decimal("3")


def intra_community_invoice(
    *,
    bucket_id: str,
    invoice_number: str,
    counterparty_country: str,
    counterparty_tax_id: str,
    issued_at: date,
    base_total: Decimal,
) -> Invoice:
    """Build one issued intra-community supply with a zero-rate line."""
    invoice_id = derive_invoice_id(
        kind=InvoiceKind.ISSUED,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_tax_id=counterparty_tax_id,
        currency="EUR",
        grand_total=base_total,
    )
    return Invoice(
        invoice_id=invoice_id,
        bucket_id=bucket_id,
        kind=InvoiceKind.ISSUED,
        invoice_number=invoice_number,
        issued_at=issued_at,
        counterparty_name="EU Customer GmbH",
        counterparty_tax_id=counterparty_tax_id,
        counterparty_country=counterparty_country,
        base_total=base_total,
        iva_total=Decimal("0"),
        grand_total=base_total,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Intra-community supply",
                quantity=Decimal("1"),
                unit_price=base_total,
                subtotal=base_total,
                iva_rate=resolve_iva_rate_slot(Decimal("0"), date.today()),
                iva_amount=Decimal("0"),
            ),
        ),
        payment_status=PaymentStatus.PENDING,
        iva_category=IvaCategory("intra_community_supply"),
    )
