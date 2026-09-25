"""Translate e-invoice parser values into the ledger application contract."""

from __future__ import annotations

from ....application.ledger.structured_invoice_ports import (
    StructuredInvoiceClassification,
    StructuredInvoiceClassificationKind,
    StructuredInvoiceLine,
    StructuredInvoiceRecord,
)
from .parsers import FacturaeInvoiceClass, ParsedEInvoice

_FACTURAE_CLASS_KINDS: dict[FacturaeInvoiceClass, StructuredInvoiceClassificationKind] = {
    FacturaeInvoiceClass.ORIGINAL: StructuredInvoiceClassificationKind.ORDINARY,
    FacturaeInvoiceClass.COPY: StructuredInvoiceClassificationKind.ORDINARY,
    FacturaeInvoiceClass.ORIGINAL_CORRECTIVE: StructuredInvoiceClassificationKind.CORRECTIVE,
    FacturaeInvoiceClass.COPY_CORRECTIVE: StructuredInvoiceClassificationKind.CORRECTIVE,
    FacturaeInvoiceClass.ORIGINAL_SUMMARY: StructuredInvoiceClassificationKind.SUMMARY,
    FacturaeInvoiceClass.COPY_SUMMARY: StructuredInvoiceClassificationKind.SUMMARY,
}


def translate_parsed_einvoice(parsed: ParsedEInvoice) -> StructuredInvoiceRecord:
    """Return an application-owned record without exposing parser DTOs inward."""
    declared_class = parsed.facturae_invoice_class
    classification = (
        None
        if declared_class is None
        else StructuredInvoiceClassification(
            source_code=declared_class.value,
            kind=_FACTURAE_CLASS_KINDS[declared_class],
        )
    )
    return StructuredInvoiceRecord(
        shape=parsed.shape,
        supplier_tax_id=parsed.supplier_tax_id,
        customer_tax_id=parsed.customer_tax_id,
        supplier_name=parsed.supplier_name,
        customer_name=parsed.customer_name,
        supplier_postal_code=parsed.supplier_postal_code,
        customer_postal_code=parsed.customer_postal_code,
        supplier_country_code=parsed.supplier_country_code,
        customer_country_code=parsed.customer_country_code,
        invoice_number=parsed.invoice_number,
        invoice_series=parsed.invoice_series,
        invoice_classification=classification,
        rectifies_invoice_number=parsed.rectifies_invoice_number,
        invoice_date=parsed.invoice_date,
        currency=parsed.currency,
        taxable_base=parsed.taxable_base,
        iva_amount=parsed.iva_amount,
        grand_total=parsed.grand_total,
        recargo_amount=parsed.recargo_amount,
        retencion_amount=parsed.retencion_amount,
        suplidos_amount=parsed.suplidos_amount,
        iva_category=parsed.iva_category,
        regime_legend=parsed.regime_legend,
        record_text=parsed.record_text,
        lines=tuple(
            StructuredInvoiceLine(
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                taxable_base=line.taxable_base,
                iva_rate=line.iva_rate,
                iva_amount=line.iva_amount,
            )
            for line in parsed.lines
        ),
        iva_breakdown=tuple(parsed.iva_breakdown),
        element_paths=dict(parsed.element_paths),
    )


__all__ = ["translate_parsed_einvoice"]
