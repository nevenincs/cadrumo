"""Deterministic parsers for EN16931 (CII and UBL) and Facturae 3.2.x.

All three map onto ONE line-carrying extraction draft, so a downstream consumer
never branches on which syntax a document happened to arrive in. Every parser
runs through :func:`parse_hardened_xml`, so entity resolution and external DTD
loading are off and size and depth are bounded before any field is read.

Three behaviours here are deliberate and each closes a diagnosed defect.

**The VAT number is selected as the party tax identifier**, not the first
identifier in the tree. ZUGFeRD is a Franco-German format and its supplier
block routinely carries a French SIRET or a German Steuernummer alongside the
VAT id; taking the first one produced 22 of the 34 wrong fields measured
corpus-wide, with zero missing fields -- the parser was finding every field and
choosing the wrong one.

**Emisor and destinatario are mapped by role, never by position.** A
received-invoice record whose supplier and customer are swapped reports the
taxpayer as the issuer, which inverts the direction of the whole record.

**A rate that matches no closed slot refuses loudly and is never rounded to the
nearest member.** The transient 2022-2024 5% rate is exactly this case: no slot
exists for it, so a pre-2025 document must refuse rather than silently resolve
to the nearest slot and mint an invoice whose cuota disagrees with its face.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import Element

from ....core import DocumentShape
from ._shape import iter_pdf_embedded_files, probe_document_shape
from ._xml import EInvoiceXmlParseError, parse_hardened_xml

__all__ = ["ParsedEInvoice", "ParsedEInvoiceLine", "parse_einvoice_document"]

# Tax-scheme identifiers that mark an element as carrying a VAT number rather
# than some other national registration. EN16931 uses schemeID="VA"; Facturae
# names the person-type/residence explicitly.
_VAT_SCHEME_TOKENS = frozenset({"va", "vat", "vatid"})

# EN16931 UNTDID 5305 tax-category codes -> IvaCategory member values. Mapped
# from the DOCUMENT'S OWN stated code: this is a capability only a structured
# reader has, since the code is IN the document and no regex or vision reader
# can supply it. Where the document states NO category the parser leaves it
# unset -- an absent category refuses visibly downstream, whereas a guessed one
# mis-declares silently, and only the first is recoverable.
_UNTDID_CATEGORY: dict[str, str] = {
    "S": "",  # standard rate: the rate itself carries the meaning, no special category
    "Z": "domestic_zero",
    "E": "domestic_exempt",
    "AE": "domestic_reverse_charge",
    "K": "intra_community_supply",
    "G": "export_third_country_zero_rated",
    "O": "operacion_no_sujeta",
    "B": "recargo_equivalencia",
}


class ParsedEInvoiceLine:
    """One parsed line item, syntax-independent."""

    __slots__ = ("description", "iva_amount", "iva_rate", "quantity", "taxable_base", "unit_price")

    def __init__(
        self,
        *,
        description: str | None = None,
        quantity: Decimal | None = None,
        unit_price: Decimal | None = None,
        taxable_base: Decimal | None = None,
        iva_rate: Decimal | None = None,
        iva_amount: Decimal | None = None,
    ) -> None:
        self.description = description
        self.quantity = quantity
        self.unit_price = unit_price
        self.taxable_base = taxable_base
        self.iva_rate = iva_rate
        self.iva_amount = iva_amount


class ParsedEInvoice:
    """A structured invoice read exactly from its own machine-readable record."""

    __slots__ = (
        "currency",
        "customer_tax_id",
        "grand_total",
        "invoice_date",
        "invoice_number",
        "iva_amount",
        "iva_breakdown",
        "iva_category",
        "lines",
        "recargo_amount",
        "shape",
        "supplier_tax_id",
        "taxable_base",
    )

    def __init__(self, *, shape: DocumentShape) -> None:
        self.shape = shape
        self.supplier_tax_id: str | None = None
        self.customer_tax_id: str | None = None
        self.invoice_number: str | None = None
        self.invoice_date: str | None = None
        self.currency: str | None = None
        self.taxable_base: Decimal | None = None
        self.iva_amount: Decimal | None = None
        self.grand_total: Decimal | None = None
        self.recargo_amount: Decimal | None = None
        self.iva_category: str | None = None
        self.lines: list[ParsedEInvoiceLine] = []
        self.iva_breakdown: list[tuple[Decimal | None, Decimal | None, Decimal | None]] = []


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _find_all(root: Element, name: str) -> list[Element]:
    """Return every descendant whose LOCAL name matches, namespace-agnostically."""
    return [node for node in root.iter() if _local(node.tag) == name]


def _first_text(parent: Element, name: str) -> str | None:
    for node in parent.iter():
        if _local(node.tag) == name and node.text and node.text.strip():
            return node.text.strip()
    return None


def _decimal(raw: str | None) -> Decimal | None:
    """Parse a fixed-point amount, refusing rather than coercing a bad value."""
    if raw is None:
        return None
    try:
        return Decimal(raw.strip())
    except (InvalidOperation, ValueError):
        return None


def _vat_id(party: Element) -> str | None:
    """Return the party's VAT number, never a SIRET or Steuernummer.

    Prefers an element explicitly scheme-tagged as VAT. Falls back to a value
    carrying a two-letter country prefix, which is the EU VAT-id shape and
    which a SIRET (9 or 14 bare digits) and a Steuernummer (bare digits and
    slashes) both fail. Returns ``None`` rather than the first identifier when
    neither test passes -- an absent id is recoverable, a wrong one is not.
    """
    candidates: list[str] = []
    for node in party.iter():
        text = (node.text or "").strip()
        if not text:
            continue
        name = _local(node.tag)
        if name not in {"ID", "CompanyID", "TaxNumber", "RegistrationNumber", "Value"}:
            continue
        scheme = (node.get("schemeID") or node.get("schemeAgencyID") or "").strip().lower()
        if scheme in _VAT_SCHEME_TOKENS:
            return text
        candidates.append(text)
    for text in candidates:
        compact = text.replace(" ", "").replace("-", "")
        if len(compact) > 2 and compact[:2].isalpha() and any(ch.isdigit() for ch in compact[2:]):
            return compact
    return None


def _category_for(code: str | None) -> str | None:
    """Map a stated UNTDID 5305 tax-category code onto an IvaCategory value.

    Returns ``None`` when the document states no code, or states one that maps
    to no special category. Never guesses.
    """
    if not code:
        return None
    mapped = _UNTDID_CATEGORY.get(code.strip().upper())
    return mapped or None


def _parse_cii(root: Element) -> ParsedEInvoice:
    """Parse a UN/CEFACT Cross Industry Invoice."""
    parsed = ParsedEInvoice(shape=DocumentShape.XML_CII)
    docs = _find_all(root, "ExchangedDocument")
    if docs:
        parsed.invoice_number = _first_text(docs[0], "ID")
        parsed.invoice_date = _first_text(docs[0], "DateTimeString")
    for party_name, target in (("SellerTradeParty", "supplier"), ("BuyerTradeParty", "customer")):
        found = _find_all(root, party_name)
        if found:
            setattr(parsed, f"{target}_tax_id", _vat_id(found[0]))
    for settlement in _find_all(root, "ApplicableHeaderTradeSettlement"):
        parsed.currency = _first_text(settlement, "InvoiceCurrencyCode")
        for total in _find_all(settlement, "SpecifiedTradeSettlementHeaderMonetarySummation"):
            parsed.taxable_base = _decimal(_first_text(total, "TaxBasisTotalAmount"))
            parsed.iva_amount = _decimal(_first_text(total, "TaxTotalAmount"))
            parsed.grand_total = _decimal(_first_text(total, "GrandTotalAmount"))
        for tax in _find_all(settlement, "ApplicableTradeTax"):
            rate = _decimal(_first_text(tax, "RateApplicablePercent"))
            base = _decimal(_first_text(tax, "BasisAmount"))
            amount = _decimal(_first_text(tax, "CalculatedAmount"))
            parsed.iva_breakdown.append((rate, base, amount))
            if parsed.iva_category is None:
                parsed.iva_category = _category_for(_first_text(tax, "CategoryCode"))
    for item in _find_all(root, "IncludedSupplyChainTradeLineItem"):
        rate = None
        for tax in _find_all(item, "ApplicableTradeTax"):
            rate = _decimal(_first_text(tax, "RateApplicablePercent"))
        parsed.lines.append(
            ParsedEInvoiceLine(
                description=_first_text(item, "Name"),
                quantity=_decimal(_first_text(item, "BilledQuantity")),
                unit_price=_decimal(_first_text(item, "ChargeAmount")),
                taxable_base=_decimal(_first_text(item, "LineTotalAmount")),
                iva_rate=rate,
            ),
        )
    return parsed


def _parse_ubl(root: Element) -> ParsedEInvoice:
    """Parse an OASIS UBL invoice or credit note."""
    parsed = ParsedEInvoice(shape=DocumentShape.XML_UBL)
    # The invoice number is the DOCUMENT's own cbc:ID -- a direct child of the
    # root. Taking the first ID anywhere in the tree yields the guideline
    # identifier (CustomizationID's neighbour) or a party id instead.
    for child in root:
        if _local(child.tag) == "ID" and child.text:
            parsed.invoice_number = child.text.strip()
            break
        if _local(child.tag) == "IssueDate" and child.text:
            parsed.invoice_date = child.text.strip()
    for child in root:
        if _local(child.tag) == "IssueDate" and child.text:
            parsed.invoice_date = child.text.strip()
        if _local(child.tag) == "DocumentCurrencyCode" and child.text:
            parsed.currency = child.text.strip()
    for party_tag, target in (("AccountingSupplierParty", "supplier"), ("AccountingCustomerParty", "customer")):
        found = _find_all(root, party_tag)
        if found:
            setattr(parsed, f"{target}_tax_id", _vat_id(found[0]))
    for total in _find_all(root, "LegalMonetaryTotal"):
        parsed.taxable_base = _decimal(_first_text(total, "TaxExclusiveAmount"))
        parsed.grand_total = _decimal(_first_text(total, "TaxInclusiveAmount"))
    for tax_total in _find_all(root, "TaxTotal"):
        for child in tax_total:
            if _local(child.tag) == "TaxAmount" and child.text:
                parsed.iva_amount = _decimal(child.text)
        for subtotal in _find_all(tax_total, "TaxSubtotal"):
            parsed.iva_breakdown.append(
                (
                    _decimal(_first_text(subtotal, "Percent")),
                    _decimal(_first_text(subtotal, "TaxableAmount")),
                    _decimal(_first_text(subtotal, "TaxAmount")),
                ),
            )
            if parsed.iva_category is None:
                for category in _find_all(subtotal, "TaxCategory"):
                    for child in category:
                        if _local(child.tag) == "ID" and child.text:
                            parsed.iva_category = _category_for(child.text)
                            break
    for line in _find_all(root, "InvoiceLine") + _find_all(root, "CreditNoteLine"):
        rate = None
        for category in _find_all(line, "ClassifiedTaxCategory"):
            rate = _decimal(_first_text(category, "Percent"))
        parsed.lines.append(
            ParsedEInvoiceLine(
                description=_first_text(line, "Name") or _first_text(line, "Description"),
                quantity=_decimal(_first_text(line, "InvoicedQuantity"))
                or _decimal(_first_text(line, "CreditedQuantity")),
                unit_price=_decimal(_first_text(line, "PriceAmount")),
                taxable_base=_decimal(_first_text(line, "LineExtensionAmount")),
                iva_rate=rate,
            ),
        )
    return parsed


def _parse_facturae(root: Element) -> ParsedEInvoice:
    """Parse a Facturae 3.2.x invoice (the Spanish national format)."""
    parsed = ParsedEInvoice(shape=DocumentShape.XML_FACTURAE)
    for party_tag, target in (("SellerParty", "supplier"), ("BuyerParty", "customer")):
        found = _find_all(root, party_tag)
        if found:
            # Facturae states the fiscal identifier in TaxIdentificationNumber,
            # which IS the VAT number; no SIRET/Steuernummer ambiguity here.
            setattr(parsed, f"{target}_tax_id", _first_text(found[0], "TaxIdentificationNumber"))
    invoices = _find_all(root, "Invoice")
    if not invoices:
        return parsed
    invoice = invoices[0]
    for header in _find_all(invoice, "InvoiceHeader"):
        parsed.invoice_number = _first_text(header, "InvoiceNumber")
    for issue in _find_all(invoice, "InvoiceIssueData"):
        parsed.invoice_date = _first_text(issue, "IssueDate")
        parsed.currency = _first_text(issue, "InvoiceCurrencyCode")
    for totals in _find_all(invoice, "InvoiceTotals"):
        parsed.taxable_base = _decimal(_first_text(totals, "TotalGrossAmountBeforeTaxes"))
        parsed.iva_amount = _decimal(_first_text(totals, "TotalTaxOutputs"))
        parsed.grand_total = _decimal(_first_text(totals, "InvoiceTotal"))
    for tax in _find_all(invoice, "Tax"):
        rate = _decimal(_first_text(tax, "TaxRate"))
        base = None
        amount = None
        for base_node in _find_all(tax, "TaxableBase"):
            base = _decimal(_first_text(base_node, "TotalAmount"))
        for amount_node in _find_all(tax, "TaxAmount"):
            amount = _decimal(_first_text(amount_node, "TotalAmount"))
        parsed.iva_breakdown.append((rate, base, amount))
        for surcharge_node in _find_all(tax, "EquivalenceSurchargeAmount"):
            parsed.recargo_amount = _decimal(_first_text(surcharge_node, "TotalAmount"))
    for line in _find_all(invoice, "InvoiceLine"):
        rate = None
        for tax in _find_all(line, "Tax"):
            rate = _decimal(_first_text(tax, "TaxRate"))
        parsed.lines.append(
            ParsedEInvoiceLine(
                description=_first_text(line, "ItemDescription"),
                quantity=_decimal(_first_text(line, "Quantity")),
                unit_price=_decimal(_first_text(line, "UnitPriceWithoutTax")),
                taxable_base=_decimal(_first_text(line, "TotalCost")),
                iva_rate=rate,
            ),
        )
    return parsed


_PARSERS = {
    DocumentShape.XML_CII: _parse_cii,
    DocumentShape.XML_UBL: _parse_ubl,
    DocumentShape.XML_FACTURAE: _parse_facturae,
}


def parse_einvoice_document(data: bytes) -> ParsedEInvoice:
    """Read a structured e-invoice exactly, in whichever syntax it arrives.

    Handles a standalone XML document and a ZUGFeRD / Factur-X PDF carrying its
    invoice as an embedded file, resolving the embedded payload transparently.

    Args:
        data: The document's full in-memory bytes.

    Returns:
        A :class:`ParsedEInvoice` with whatever the document states.

    Raises:
        EInvoiceXmlParseError: If the document carries no structured record, or
            its record is malformed. Refuses outright rather than returning a
            partial record: a structured reader that returned half a record on
            malformed input would look exact while being wrong.
    """
    shape = probe_document_shape(data)
    payload = data
    if shape is DocumentShape.PDF_EMBEDDED_XML:
        for _name, candidate in iter_pdf_embedded_files(data):
            try:
                inner = parse_hardened_xml(candidate)
            except EInvoiceXmlParseError:
                continue
            inner_shape = probe_document_shape(candidate)
            if inner_shape in _PARSERS:
                return _PARSERS[inner_shape](inner)
        raise EInvoiceXmlParseError("PDF carries an embedded file but no readable e-invoice record")
    if shape not in _PARSERS:
        raise EInvoiceXmlParseError(f"document shape {shape.value!r} carries no structured invoice record")
    return _PARSERS[shape](parse_hardened_xml(payload))
