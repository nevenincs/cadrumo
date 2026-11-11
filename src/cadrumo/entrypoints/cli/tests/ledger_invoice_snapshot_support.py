"""A complete received-invoice snapshot for the CLI projector tests."""

from __future__ import annotations

from datetime import date

from ....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot, InvoiceLineSnapshot
from ....application.operations.public_scalar import PublicDecimal
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.invoices.enums import PaymentStatus
from ....domain.iva.schema import InvoiceKind


def received_invoice_snapshot(*, counterparty_tax_id: str | None) -> CatalogueInvoiceSnapshot:
    """Build a complete received-invoice snapshot of 121.00 EUR for the CLI projector."""
    return CatalogueInvoiceSnapshot(
        invoice_id="d" * 64,
        bucket_id="5aa00000-0000-4000-8000-0000000000aa",
        kind=InvoiceKind.RECEIVED,
        invoice_number="ES-2026-000019",
        issued_at=date(filing_year_envelope().horizon, 3, 11),
        counterparty_name="Acme Suministros SL",
        counterparty_tax_id=counterparty_tax_id,
        counterparty_country="ES",
        base_total=PublicDecimal(decimal="100.00"),
        iva_total=PublicDecimal(decimal="21.00"),
        grand_total=PublicDecimal(decimal="121.00"),
        currency="EUR",
        payment_status=PaymentStatus.PENDING,
        linked_transaction_ids=(),
        source_filename="factura.xml",
        source_sha256="b" * 64,
        source_row_index=None,
        notes="",
        retention_rate=None,
        retention_amount=None,
        recargo_amount=None,
        operation_type=None,
        lines=(
            InvoiceLineSnapshot(
                description="Komponenter",
                quantity=PublicDecimal(decimal="1"),
                unit_price=PublicDecimal(decimal="100.00"),
                subtotal=PublicDecimal(decimal="100.00"),
                iva_rate="21",
                iva_amount=PublicDecimal(decimal="21.00"),
            ),
        ),
        invoice_class="ORDINARIA",
        series=None,
        operation_date=None,
        operation_date_role=None,
        iva_category=None,
        rectifies_invoice_number=None,
        fx_rate=None,
        fx_rate_date=None,
        fx_rate_source=None,
        base_total_eur=None,
        iva_total_eur=None,
        grand_total_eur=None,
        referencia_catastral=None,
        settlement_amount=PublicDecimal(decimal="121.00"),
        documents=(),
    )
