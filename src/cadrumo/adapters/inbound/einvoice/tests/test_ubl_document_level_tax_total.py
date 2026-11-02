"""A UBL invoice states its tax at document level; a line's own TaxTotal is not a second statement.

UBL 2.1 lets ``cac:InvoiceLine`` carry a ``cac:TaxTotal`` of its own. Reading every
descendant ``TaxTotal`` counted each line's tax again beside the document's, and the
last one read replaced the cuota.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..parsers import parse_einvoice_document

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter, pytest.mark.usefixtures("operation")]

_NS = (
    'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
    'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"'
)


def _tax_total(base: str, amount: str) -> str:
    return (
        f'<cac:TaxTotal><cbc:TaxAmount currencyID="EUR">{amount}</cbc:TaxAmount>'
        f'<cac:TaxSubtotal><cbc:TaxableAmount currencyID="EUR">{base}</cbc:TaxableAmount>'
        f'<cbc:TaxAmount currencyID="EUR">{amount}</cbc:TaxAmount>'
        "<cac:TaxCategory><cbc:ID>S</cbc:ID><cbc:Percent>21.00</cbc:Percent>"
        "<cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:TaxCategory>"
        "</cac:TaxSubtotal></cac:TaxTotal>"
    )


def _line(identifier: str, base: str, tax: str | None) -> str:
    return (
        f'<cac:InvoiceLine><cbc:ID>{identifier}</cbc:ID><cbc:InvoicedQuantity unitCode="C62">1</cbc:InvoicedQuantity>'
        f'<cbc:LineExtensionAmount currencyID="EUR">{base}</cbc:LineExtensionAmount>'
        f"{'' if tax is None else tax}"
        "<cac:Item><cbc:Name>Servicio</cbc:Name></cac:Item>"
        f'<cac:Price><cbc:PriceAmount currencyID="EUR">{base}</cbc:PriceAmount></cac:Price></cac:InvoiceLine>'
    )


def _document(*, line_level: bool) -> bytes:
    lines = _line("1", "600.00", _tax_total("600.00", "126.00") if line_level else None) + _line(
        "2", "400.00", _tax_total("400.00", "84.00") if line_level else None
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><Invoice {_NS}>'
        "<cbc:ID>U-9</cbc:ID><cbc:IssueDate>2026-04-02</cbc:IssueDate>"
        f"{_tax_total('1000.00', '210.00')}"
        '<cac:LegalMonetaryTotal><cbc:TaxExclusiveAmount currencyID="EUR">1000.00</cbc:TaxExclusiveAmount>'
        '<cbc:TaxInclusiveAmount currencyID="EUR">1210.00</cbc:TaxInclusiveAmount></cac:LegalMonetaryTotal>'
        f"{lines}</Invoice>"
    ).encode()


def test_line_level_tax_totals_neither_replace_the_cuota_nor_extend_the_breakdown() -> None:
    parsed = parse_einvoice_document(_document(line_level=True))

    assert parsed.iva_amount == Decimal("210.00")
    assert parsed.iva_breakdown == [(Decimal("21.00"), Decimal("1000.00"), Decimal("210.00"))]


def test_the_document_level_statement_reads_the_same_without_line_level_totals() -> None:
    parsed = parse_einvoice_document(_document(line_level=False))

    assert parsed.iva_amount == Decimal("210.00")
    assert parsed.iva_breakdown == [(Decimal("21.00"), Decimal("1000.00"), Decimal("210.00"))]
