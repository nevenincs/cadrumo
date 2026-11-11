"""What each structured format can say about a retención, read by the real parser.

Facturae 3.2.2 names IRPF with ``TaxTypeCode`` 04 under ``TaxesWithheld``, at invoice
and line level, with ``TotalTaxesWithheld`` required in the totals. UBL 2.1 has
``cac:WithholdingTaxTotal``, whose ``cac:TaxScheme`` says which tax. The CII binding
of EN 16931 has no withholding element at all. Values are worked by hand in the
parameter comments; every document is synthetic.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.adapters.inbound.einvoice.application_translation import translate_parsed_einvoice
from cadrumo.adapters.inbound.einvoice.parsers import ParsedEInvoice, parse_einvoice_document
from cadrumo.application.ledger.withheld_tax_findings import withheld_tax_findings
from cadrumo.core.draft_discrepancy import DraftDiscrepancyKind
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _withheld(code: str, rate: str, base: str, amount: str | None) -> str:
    stated = "" if amount is None else f"<TaxAmount><TotalAmount>{amount}</TotalAmount></TaxAmount>"
    return (
        f"<Tax><TaxTypeCode>{code}</TaxTypeCode><TaxRate>{rate}</TaxRate>"
        f"<TaxableBase><TotalAmount>{base}</TotalAmount></TaxableBase>{stated}</Tax>"
    )


def _facturae(*, header: str = "", line: str = "", total: str | None = "150.00") -> bytes:
    """Return a document of base 1000.00 at IVA 21 %, withholding as told."""
    header_block = f"<TaxesWithheld>{header}</TaxesWithheld>" if header else ""
    line_block = f"<TaxesWithheld>{line}</TaxesWithheld>" if line else ""
    total_element = "" if total is None else f"<TotalTaxesWithheld>{total}</TotalTaxesWithheld>"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<fe:Facturae xmlns:fe="http://www.facturae.gob.es/formato/Versiones/Facturaev3_2_2.xml">
  <FileHeader><SchemaVersion>3.2.2</SchemaVersion></FileHeader>
  <Invoices><Invoice>
    <InvoiceHeader><InvoiceNumber>1</InvoiceNumber><InvoiceClass>OO</InvoiceClass></InvoiceHeader>
    <TaxesOutputs>
      <Tax><TaxTypeCode>01</TaxTypeCode><TaxRate>21.00</TaxRate>
        <TaxableBase><TotalAmount>1000.00</TotalAmount></TaxableBase>
        <TaxAmount><TotalAmount>210.00</TotalAmount></TaxAmount></Tax>
    </TaxesOutputs>
    {header_block}
    <InvoiceTotals>
      <TotalGrossAmountBeforeTaxes>1000.00</TotalGrossAmountBeforeTaxes>
      <TotalTaxOutputs>210.00</TotalTaxOutputs>
      {total_element}
    </InvoiceTotals>
    <Items><InvoiceLine>
      <ItemDescription>Consultoria</ItemDescription>
      <TotalCost>1000.00</TotalCost>
      {line_block}
      <TaxesOutputs><Tax><TaxTypeCode>01</TaxTypeCode><TaxRate>21.00</TaxRate></Tax></TaxesOutputs>
    </InvoiceLine></Items>
  </Invoice></Invoices>
</fe:Facturae>""".encode()


_UBL_NS = (
    'xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
    'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"'
)


def _ubl_subtotal(scheme: str | None, *, percent: str, base: str, amount: str) -> str:
    named = "" if scheme is None else f"<cac:TaxScheme><cbc:ID>{scheme}</cbc:ID></cac:TaxScheme>"
    return (
        f'<cac:TaxSubtotal><cbc:TaxableAmount currencyID="EUR">{base}</cbc:TaxableAmount>'
        f'<cbc:TaxAmount currencyID="EUR">{amount}</cbc:TaxAmount>'
        f"<cac:TaxCategory><cbc:ID>S</cbc:ID><cbc:Percent>{percent}</cbc:Percent>{named}</cac:TaxCategory>"
        "</cac:TaxSubtotal>"
    )


_UBL_IVA_TOTAL = (
    '<cac:TaxTotal><cbc:TaxAmount currencyID="EUR">210.00</cbc:TaxAmount>'
    + _ubl_subtotal("VAT", percent="21.00", base="1000.00", amount="210.00")
    + "</cac:TaxTotal>"
)


def _ubl(*blocks: str) -> bytes:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><Invoice {_UBL_NS}>'
        "<cbc:ID>U-1</cbc:ID><cbc:IssueDate>2026-04-02</cbc:IssueDate>"
        f"{''.join(blocks)}"
        '<cac:LegalMonetaryTotal><cbc:TaxExclusiveAmount currencyID="EUR">1000.00</cbc:TaxExclusiveAmount>'
        '<cbc:TaxInclusiveAmount currencyID="EUR">1210.00</cbc:TaxInclusiveAmount></cac:LegalMonetaryTotal>'
        "</Invoice>"
    ).encode()


def _ubl_withholding(total: str, *subtotals: str) -> str:
    return (
        f'<cac:WithholdingTaxTotal><cbc:TaxAmount currencyID="EUR">{total}</cbc:TaxAmount>'
        f"{''.join(subtotals)}</cac:WithholdingTaxTotal>"
    )


def _cii(*taxes: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100" '
        'xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100" '
        'xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">'
        "<rsm:ExchangedDocument><ram:ID>C-1</ram:ID></rsm:ExchangedDocument>"
        "<rsm:SupplyChainTradeTransaction><ram:ApplicableHeaderTradeSettlement>"
        "<ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>"
        f"{''.join(taxes)}"
        "<ram:SpecifiedTradeSettlementHeaderMonetarySummation>"
        "<ram:TaxBasisTotalAmount>1000.00</ram:TaxBasisTotalAmount>"
        "<ram:TaxTotalAmount>210.00</ram:TaxTotalAmount>"
        "<ram:GrandTotalAmount>1210.00</ram:GrandTotalAmount>"
        "</ram:SpecifiedTradeSettlementHeaderMonetarySummation>"
        "</ram:ApplicableHeaderTradeSettlement></rsm:SupplyChainTradeTransaction>"
        "</rsm:CrossIndustryInvoice>"
    ).encode()


def _cii_tax(type_code: str, rate: str, amount: str) -> str:
    return (
        f"<ram:ApplicableTradeTax><ram:CalculatedAmount>{amount}</ram:CalculatedAmount>"
        f"<ram:TypeCode>{type_code}</ram:TypeCode><ram:BasisAmount>1000.00</ram:BasisAmount>"
        f"<ram:CategoryCode>S</ram:CategoryCode><ram:RateApplicablePercent>{rate}</ram:RateApplicablePercent>"
        "</ram:ApplicableTradeTax>"
    )


def _kinds(parsed: ParsedEInvoice) -> list[DraftDiscrepancyKind]:
    return [finding.kind for finding in withheld_tax_findings(translate_parsed_einvoice(parsed))]


@pytest.mark.parametrize(
    ("document", "rate", "amount"),
    [
        # 1000.00 x 15 / 100 = 150.00.
        (_facturae(header=_withheld("04", "15.00", "1000.00", "150.00")), "15.00", "150.00"),
        # The schema calls the line block informative, and it is all this one has.
        (_facturae(line=_withheld("04", "15.00", "1000.00", "150.00")), "15.00", "150.00"),
        # Stated at both levels: one withholding, so 150.00 rather than 300.00.
        (
            _facturae(
                header=_withheld("04", "15.00", "1000.00", "150.00"),
                line=_withheld("04", "15.00", "1000.00", "150.00"),
            ),
            "15.00",
            "150.00",
        ),
        # Two parts of the base at one rate: 600.00 + 400.00 = 1000.00, 90.00 + 60.00.
        (
            _facturae(
                header=_withheld("04", "15.00", "600.00", "90.00") + _withheld("04", "15.00", "400.00", "60.00"),
            ),
            "15.00",
            "150.00",
        ),
        # An amount the row omits falls back to the required total.
        (_facturae(header=_withheld("04", "15.00", "1000.00", None)), "15.00", "150.00"),
    ],
    ids=["header", "line_only", "header_and_line", "two_rows_one_rate", "row_without_amount"],
)
def test_facturae_reads_an_irpf_withholding(document: bytes, rate: str, amount: str) -> None:
    parsed = parse_einvoice_document(document)

    assert parsed.retencion_rate == Decimal(rate)
    assert parsed.retencion_amount == Decimal(amount)
    # Never the IVA: the cuota and its rate are the outputs' alone.
    assert parsed.iva_amount == Decimal("210.00")
    assert parsed.iva_breakdown == [(Decimal("21.00"), Decimal("1000.00"), Decimal("210.00"))]
    assert parsed.lines[0].iva_rate == Decimal("21.00")
    assert _kinds(parsed) == []


@pytest.mark.parametrize(
    "issued_on",
    [
        date(filing_year_envelope().floor - 1, 6, 30).isoformat(),
        date(filing_year_envelope().horizon, 6, 30).isoformat(),
        "not a date",
    ],
)
def test_the_irpf_code_is_read_whatever_date_the_invoice_states(issued_on: str) -> None:
    document = _facturae(header=_withheld("04", "15.00", "1000.00", "150.00")).replace(
        b"<TaxesOutputs>",
        f"<InvoiceIssueData><IssueDate>{issued_on}</IssueDate></InvoiceIssueData><TaxesOutputs>".encode(),
        1,
    )
    parsed = parse_einvoice_document(document)
    assert parsed.invoice_date == issued_on
    assert parsed.retencion_amount == Decimal("150.00")


def test_two_rates_keep_the_amount_and_no_single_rate() -> None:
    # 500.00 x 15 % = 75.00 and 500.00 x 7 % = 35.00, so 110.00 withheld at no one rate.
    parsed = parse_einvoice_document(
        _facturae(
            header=_withheld("04", "15.00", "500.00", "75.00") + _withheld("04", "7.00", "500.00", "35.00"),
            total="110.00",
        ),
    )

    assert parsed.retencion_rate is None
    assert parsed.retencion_amount == Decimal("110.00")
    assert _kinds(parsed) == []


def test_a_withholding_on_part_of_the_base_keeps_no_rate_the_invoice_would_refuse() -> None:
    # 200.00 x 15 % = 30.00, which is not 15 % of the invoice's 1000.00.
    parsed = parse_einvoice_document(_facturae(header=_withheld("04", "15.00", "200.00", "30.00"), total="30.00"))

    assert parsed.retencion_rate is None
    assert parsed.retencion_amount == Decimal("30.00")
    assert _kinds(parsed) == []


def test_another_withheld_tax_is_not_a_retencion_and_stays_visible() -> None:
    parsed = parse_einvoice_document(_facturae(header=_withheld("05", "15.00", "1000.00", "150.00")))

    assert parsed.retencion_amount is None
    assert parsed.retencion_rate is None
    assert _kinds(parsed) == [DraftDiscrepancyKind.ARITHMETIC_CLOSURE]


def test_a_total_naming_no_tax_is_unread_and_stays_visible() -> None:
    parsed = parse_einvoice_document(_facturae())

    assert parsed.retencion_amount is None
    assert _kinds(parsed) == [DraftDiscrepancyKind.ARITHMETIC_CLOSURE]


def test_a_total_disagreeing_with_its_rows_is_a_finding() -> None:
    # The row says 150.00; a total of 140.00 is ten euros away from it.
    parsed = parse_einvoice_document(_facturae(header=_withheld("04", "15.00", "1000.00", "150.00"), total="140.00"))

    assert parsed.retencion_amount == Decimal("150.00")
    assert _kinds(parsed) == [DraftDiscrepancyKind.ARITHMETIC_CLOSURE]


def test_a_stated_zero_is_zero_and_an_absent_figure_stays_absent() -> None:
    stated = parse_einvoice_document(_facturae(total="0.00"))
    absent = parse_einvoice_document(_facturae(total=None))

    assert stated.retencion_amount == Decimal("0.00")
    assert absent.retencion_amount is None
    assert _kinds(stated) == []
    assert _kinds(absent) == []


def test_ubl_reads_a_withholding_whose_scheme_names_irpf() -> None:
    parsed = parse_einvoice_document(
        _ubl(
            _UBL_IVA_TOTAL,
            _ubl_withholding("150.00", _ubl_subtotal("IRPF", percent="15.00", base="1000.00", amount="150.00")),
        ),
    )

    assert parsed.retencion_rate == Decimal("15.00")
    assert parsed.retencion_amount == Decimal("150.00")
    assert parsed.iva_amount == Decimal("210.00")
    assert parsed.iva_breakdown == [(Decimal("21.00"), Decimal("1000.00"), Decimal("210.00"))]
    assert _kinds(parsed) == []


@pytest.mark.parametrize("scheme", [None, "WHT"], ids=["no_scheme", "another_scheme"])
def test_ubl_leaves_a_withholding_it_cannot_name_unread(scheme: str | None) -> None:
    parsed = parse_einvoice_document(
        _ubl(
            _UBL_IVA_TOTAL,
            _ubl_withholding("150.00", _ubl_subtotal(scheme, percent="15.00", base="1000.00", amount="150.00")),
        ),
    )

    assert parsed.retencion_amount is None
    assert parsed.retencion_rate is None
    assert _kinds(parsed) == [DraftDiscrepancyKind.ARITHMETIC_CLOSURE]


def test_ubl_never_takes_irpf_in_a_tax_total_for_iva() -> None:
    misplaced = (
        '<cac:TaxTotal><cbc:TaxAmount currencyID="EUR">150.00</cbc:TaxAmount>'
        + _ubl_subtotal("IRPF", percent="15.00", base="1000.00", amount="150.00")
        + "</cac:TaxTotal>"
    )

    parsed = parse_einvoice_document(_ubl(_UBL_IVA_TOTAL, misplaced))

    assert parsed.iva_amount == Decimal("210.00")
    assert parsed.iva_breakdown == [(Decimal("21.00"), Decimal("1000.00"), Decimal("210.00"))]
    assert parsed.retencion_amount is None
    assert _kinds(parsed) == [DraftDiscrepancyKind.ARITHMETIC_CLOSURE]


def test_cii_has_no_withholding_element_so_nothing_is_read() -> None:
    parsed = parse_einvoice_document(_cii(_cii_tax("VAT", "21.00", "210.00")))

    assert parsed.retencion_amount is None
    assert parsed.retencion_rate is None
    assert _kinds(parsed) == []


def test_cii_never_takes_a_tier_naming_irpf_for_iva() -> None:
    parsed = parse_einvoice_document(_cii(_cii_tax("VAT", "21.00", "210.00"), _cii_tax("IRPF", "15.00", "150.00")))

    assert parsed.iva_breakdown == [(Decimal("21.00"), Decimal("1000.00"), Decimal("210.00"))]
    assert parsed.retencion_amount is None
    assert _kinds(parsed) == [DraftDiscrepancyKind.ARITHMETIC_CLOSURE]
