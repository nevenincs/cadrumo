"""Deterministic parsers for EN16931 (CII and UBL) and Facturae 3.2.x.

All three map onto ONE line-carrying extraction draft, so a downstream consumer
never branches on which syntax a document happened to arrive in. Every parser
runs through :func:`parse_hardened_xml`, so entity resolution and external DTD
loading are off and size and depth are bounded before any field is read.

Three behaviours here are deliberate and each closes a diagnosed defect.

**The IVA number is selected as the party tax identifier**, not the first
identifier in the tree. ZUGFeRD is a Franco-German format and its supplier
block routinely carries a French SIRET or a German Steuernummer alongside the
IVA id; taking the first one produced 22 of the 34 wrong fields measured
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

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Final
from xml.etree.ElementTree import Element

from ....core.document_shape import DocumentShape
from ....domain.calculations.registry.facturae_tax_type_codes import facturae_irpf_tax_type_code
from .element_readers import (
    category_for,
    cii_country_code,
    cii_postal_code,
    decimal,
    direct_child_text,
    facturae_country_code,
    facturae_party_name,
    facturae_postal_code,
    find_all,
    first_text,
    record_text,
    ubl_country_code,
    ubl_party_name,
    ubl_postal_code,
)
from .shape import iter_pdf_embedded_files, probe_document_shape
from .xml import EInvoiceXmlParseError, local_tag_name, parse_hardened_xml

__all__ = [
    "FacturaeInvoiceClass",
    "ParsedEInvoice",
    "ParsedEInvoiceLine",
    "ParsedWithheldTax",
    "parse_einvoice_document",
]

# Tax-scheme identifiers that mark an element as carrying an IVA number rather
# than some other national registration. EN16931 uses schemeID="VA"; Facturae
# names the person-type/residence explicitly.
_IVA_SCHEME_TOKENS = frozenset({"va", "vat", "vatid"})

#: How a tax-scheme element names IRPF. UBL and CII publish no code for it.
_IRPF_SCHEME_NAME: Final = "IRPF"


class FacturaeInvoiceClass(StrEnum):
    """Class code stated by Facturae's ``InvoiceHeader/InvoiceClass``."""

    ORIGINAL = "OO"
    ORIGINAL_CORRECTIVE = "OR"
    ORIGINAL_SUMMARY = "OC"
    COPY = "CO"
    COPY_CORRECTIVE = "CR"
    COPY_SUMMARY = "CC"


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
        """Initialize the parsed line item with its optional syntax-independent fields."""
        self.description = description
        self.quantity = quantity
        self.unit_price = unit_price
        self.taxable_base = taxable_base
        self.iva_rate = iva_rate
        self.iva_amount = iva_amount


@dataclass(frozen=True, slots=True)
class ParsedWithheldTax:
    """One withholding a record states, and whether its format names it as IRPF."""

    stated_type: str | None
    is_irpf: bool
    rate: Decimal | None
    base: Decimal | None
    amount: Decimal | None


class ParsedEInvoice:
    """A structured invoice read exactly from its own machine-readable record."""

    __slots__ = (
        "currency",
        "customer_country_code",
        "customer_name",
        "customer_postal_code",
        "customer_tax_id",
        "element_paths",
        "facturae_invoice_class",
        "grand_total",
        "invoice_date",
        "invoice_number",
        "invoice_series",
        "iva_amount",
        "iva_breakdown",
        "iva_category",
        "lines",
        "recargo_amount",
        "record_text",
        "rectifies_invoice_number",
        "regime_legend",
        "retencion_amount",
        "retencion_rate",
        "shape",
        "suplidos_amount",
        "supplier_country_code",
        "supplier_name",
        "supplier_postal_code",
        "supplier_tax_id",
        "taxable_base",
        "withheld_taxes",
        "withheld_total",
    )

    def __init__(self, *, shape: DocumentShape) -> None:
        """Initialize the parsed invoice for ``shape``, with every field unset."""
        self.shape = shape
        self.supplier_tax_id: str | None = None
        self.customer_tax_id: str | None = None
        self.supplier_name: str | None = None
        self.customer_name: str | None = None
        # The sub-national half of the establishment question. A country code
        # cannot separate Spain's three IVA territories, so a Spanish party's
        # territory is settled by its postal code or not at all. Read from the
        # format's own dedicated element in every case -- never split out of a
        # composite address string, which would be an inference rather than a
        # read. Absent stays None: the mainland is the majority population, so
        # defaulting to it would be invisible in testing while silently placing
        # Canarian and Ceutan parties outside the territory they belong to.
        self.supplier_postal_code: str | None = None
        self.customer_postal_code: str | None = None
        # The country half, carried VERBATIM in whichever code system the format
        # states it -- Facturae in ISO alpha-3, UBL and CII in alpha-2. Left
        # untranslated here on purpose: the correspondence between the two systems
        # is registry data, and resolving it inside a syntax parser would make this
        # module a second country authority. Absent stays None for the same reason
        # the postal code does.
        self.supplier_country_code: str | None = None
        self.customer_country_code: str | None = None
        self.invoice_number: str | None = None
        self.invoice_series: str | None = None
        self.facturae_invoice_class: FacturaeInvoiceClass | None = None
        self.rectifies_invoice_number: str | None = None
        self.invoice_date: str | None = None
        self.currency: str | None = None
        self.taxable_base: Decimal | None = None
        self.iva_amount: Decimal | None = None
        self.grand_total: Decimal | None = None
        self.recargo_amount: Decimal | None = None
        # The two terms of the invoice identity that are neither base nor cuota,
        # and that Facturae states in its own dedicated elements. Retencion is a
        # settlement-side deduction and the suplido is a third position on the
        # total, so a reader that recovers neither cannot reconstruct what the
        # document says the operation cost -- see the totals walk below for why
        # that is not merely a missing field but a wrong total.
        self.retencion_amount: Decimal | None = None
        self.retencion_rate: Decimal | None = None
        # Everything the document states as withheld, before any of it is taken
        # for a retencion. Kept so a withheld figure the format does not name as
        # IRPF stays visible instead of disappearing with the read.
        self.withheld_taxes: list[ParsedWithheldTax] = []
        self.withheld_total: Decimal | None = None
        self.suplidos_amount: Decimal | None = None
        self.iva_category: str | None = None
        # The statutory mention the document itself prints, copied verbatim.
        # Transcriptive evidence, never a classification: the category code
        # already says what the record MEANS, while this says what the issuer
        # WROTE. The two are read from different elements precisely so a
        # disagreement between them stays visible to the operator.
        self.regime_legend: str | None = None
        # Every TEXT NODE the record carries, and no markup. This is what the
        # anchor check must search: passing the whole decoded file lets a
        # two-character value match a TAG name -- "ID" occurs in `<cbc:ID>` --
        # so a document carrying no country element at all grounds one, and the
        # check certifies markup while claiming to catch a reader that pointed
        # at an element the document does not have. Every field read here comes
        # from a text node, so narrowing the haystack weakens no case that was
        # legitimately grounded before.
        self.record_text: str = ""
        # Where a field was actually read from, for the fields whose location is
        # not fixed by the format alone. A format that states a value in exactly
        # one element needs no entry here and gets its location from the
        # provenance table downstream; a format offering alternative blocks --
        # Facturae's Spanish and overseas addresses -- can only report the
        # element an operator would navigate to if the reader records it.
        self.element_paths: dict[str, str] = {}
        self.lines: list[ParsedEInvoiceLine] = []
        self.iva_breakdown: list[tuple[Decimal | None, Decimal | None, Decimal | None]] = []


def _iva_id_candidate_values(party: Element) -> tuple[str | None, tuple[str, ...]]:
    """Collect candidate identifiers while retaining the first explicit NIF-IVA."""
    candidates: list[str] = []
    for node in party.iter():
        text = (node.text or "").strip()
        if not text:
            continue
        name = local_tag_name(node.tag)
        if name not in {"ID", "CompanyID", "TaxNumber", "RegistrationNumber", "Value"}:
            continue
        scheme = (node.get("schemeID") or node.get("schemeAgencyID") or "").strip().lower()
        if scheme in _IVA_SCHEME_TOKENS:
            return text, tuple(candidates)
        candidates.append(text)
    return None, tuple(candidates)


def _prefixed_iva_id(text: str) -> str | None:
    """Return a candidate's compact EU IVA shape, or ``None`` when it is not one."""
    compact = text.replace(" ", "").replace("-", "")
    if len(compact) > 2 and compact[:2].isalpha() and any(ch.isdigit() for ch in compact[2:]):
        return compact
    return None


def _iva_id(party: Element) -> str | None:
    """Return the party's IVA number, never a SIRET or Steuernummer.

    Prefers an element explicitly scheme-tagged as ``VAT``. Falls back to a value
    carrying a two-letter country prefix, which is the EU IVA-id shape and
    which a SIRET (9 or 14 bare digits) and a Steuernummer (bare digits and
    slashes) both fail. Returns ``None`` rather than the first identifier when
    neither test passes -- an absent id is recoverable, a wrong one is not.
    """
    explicit, candidates = _iva_id_candidate_values(party)
    if explicit is not None:
        return explicit
    for text in candidates:
        candidate = _prefixed_iva_id(text)
        if candidate is not None:
            return candidate
    return None


def _apply_cii_document_header(root: Element, parsed: ParsedEInvoice) -> None:
    """Read the number, date and statutory mention off the ExchangedDocument."""
    docs = find_all(root, "ExchangedDocument")
    if not docs:
        return
    parsed.invoice_number = first_text(docs[0], "ID")
    parsed.invoice_date = first_text(docs[0], "DateTimeString")
    # CII's document-level IncludedNote is the BT-22 counterpart of UBL's
    # cbc:Note, scoped to the ExchangedDocument so a line-level note cannot
    # be mistaken for the document's statutory mention.
    for note in find_all(docs[0], "IncludedNote"):
        content = first_text(note, "Content")
        if content is not None and content:
            parsed.regime_legend = content
            break


def _apply_cii_parties(root: Element, parsed: ParsedEInvoice) -> None:
    """Read both parties' identity and address off their CII trade-party blocks."""
    for party_name, target in (("SellerTradeParty", "supplier"), ("BuyerTradeParty", "customer")):
        found = find_all(root, party_name)
        if not found:
            continue
        setattr(parsed, f"{target}_tax_id", _iva_id(found[0]))
        # A direct child: the party subtree also carries a contact's
        # PersonName and may carry a SpecifiedLegalOrganization trading
        # name, neither of which is the party's own stated name.
        setattr(parsed, f"{target}_name", direct_child_text(found[0], "Name"))
        setattr(parsed, f"{target}_postal_code", cii_postal_code(found[0]))
        setattr(parsed, f"{target}_country_code", cii_country_code(found[0]))


def _names_irpf(stated: str | None) -> bool:
    """Return whether a tax-scheme token names IRPF, the only retencion this models."""
    return stated is not None and stated.strip().upper() == _IRPF_SCHEME_NAME


def _apply_cii_trade_tax(tax: Element, parsed: ParsedEInvoice) -> None:
    """Append one ApplicableTradeTax tier, keeping the first stated category.

    EN 16931 models no withholding and its CII binding has no element for one, so
    a tier naming IRPF is outside the format's meaning. It is recorded as a withheld
    figure that was not read, never taken for an IVA tier.
    """
    stated_type = direct_child_text(tax, "TypeCode")
    if _names_irpf(stated_type):
        parsed.withheld_taxes.append(
            ParsedWithheldTax(
                stated_type=stated_type,
                is_irpf=False,
                rate=decimal(first_text(tax, "RateApplicablePercent")),
                base=decimal(first_text(tax, "BasisAmount")),
                amount=decimal(first_text(tax, "CalculatedAmount")),
            ),
        )
        return
    parsed.iva_breakdown.append(
        (
            decimal(first_text(tax, "RateApplicablePercent")),
            decimal(first_text(tax, "BasisAmount")),
            decimal(first_text(tax, "CalculatedAmount")),
        ),
    )
    if parsed.iva_category is None:
        parsed.iva_category = category_for(first_text(tax, "CategoryCode"), issued_on=_stated_issue_date(parsed))
    if parsed.regime_legend is None:
        parsed.regime_legend = first_text(tax, "ExemptionReason")


def _apply_cii_settlement(root: Element, parsed: ParsedEInvoice) -> None:
    """Read the currency, the header totals and the per-rate tax breakdown."""
    for settlement in find_all(root, "ApplicableHeaderTradeSettlement"):
        parsed.currency = first_text(settlement, "InvoiceCurrencyCode")
        for total in find_all(settlement, "SpecifiedTradeSettlementHeaderMonetarySummation"):
            parsed.taxable_base = decimal(first_text(total, "TaxBasisTotalAmount"))
            parsed.iva_amount = decimal(first_text(total, "TaxTotalAmount"))
            parsed.grand_total = decimal(first_text(total, "GrandTotalAmount"))
        for tax in find_all(settlement, "ApplicableTradeTax"):
            _apply_cii_trade_tax(tax, parsed)


def _cii_lines(root: Element) -> list[ParsedEInvoiceLine]:
    """Read each line item, taking the LAST stated rate as that line's rate."""
    lines: list[ParsedEInvoiceLine] = []
    for item in find_all(root, "IncludedSupplyChainTradeLineItem"):
        rate = None
        for tax in find_all(item, "ApplicableTradeTax"):
            if not _names_irpf(direct_child_text(tax, "TypeCode")):
                rate = decimal(first_text(tax, "RateApplicablePercent"))
        lines.append(
            ParsedEInvoiceLine(
                description=first_text(item, "Name"),
                quantity=decimal(first_text(item, "BilledQuantity")),
                unit_price=decimal(first_text(item, "ChargeAmount")),
                taxable_base=decimal(first_text(item, "LineTotalAmount")),
                iva_rate=rate,
            ),
        )
    return lines


def _parse_cii(root: Element) -> ParsedEInvoice:
    """Parse a UN/CEFACT Cross Industry Invoice."""
    parsed = ParsedEInvoice(shape=DocumentShape.XML_CII)
    _apply_cii_document_header(root, parsed)
    _apply_cii_parties(root, parsed)
    _apply_cii_settlement(root, parsed)
    parsed.lines.extend(_cii_lines(root))
    return parsed


def _ubl_invoice_number(root: Element) -> str | None:
    """Return the DOCUMENT's own cbc:ID, read as a direct child of the root.

    Scoped to direct children deliberately. Taking the first ID anywhere in
    the tree yields the guideline identifier (CustomizationID's neighbour) or
    a party id instead, both of which look like plausible invoice numbers.
    """
    for child in root:
        if local_tag_name(child.tag) == "ID" and (child.text is not None and child.text):
            return child.text.strip()
    return None


def _ubl_header_child_values(
    child: Element,
    *,
    existing_regime_legend: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Read one UBL root child, including its document-level statutory mention.

    A document-level cbc:Note is where UBL carries the statutory mention an issuer
    prints (EN16931 BT-22). It is read as free text in the document's OWN language,
    never matched against a Spanish phrase list: an intra-community invoice states
    its exemption in the issuer's language, and a phrase match would silently
    recover nothing there while appearing to work on every domestic document.
    """
    name = local_tag_name(child.tag)
    text = child.text
    if text is None or not text:
        return None, None, existing_regime_legend
    invoice_date = text.strip() if name == "IssueDate" else None
    currency = text.strip() if name == "DocumentCurrencyCode" else None
    regime_legend = existing_regime_legend
    if name == "Note" and regime_legend is None:
        regime_legend = text.strip() or None
    return invoice_date, currency, regime_legend


def _ubl_document_header_values(
    root: Element,
    *,
    existing_regime_legend: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Read UBL header values while preserving root order and existing legend state."""
    invoice_date: str | None = None
    currency: str | None = None
    regime_legend = existing_regime_legend
    for child in root:
        child_date, child_currency, regime_legend = _ubl_header_child_values(
            child,
            existing_regime_legend=regime_legend,
        )
        if child_date is not None:
            invoice_date = child_date
        if child_currency is not None:
            currency = child_currency
    if regime_legend is None:
        regime_legend = first_text(root, "TaxExemptionReason")
    return invoice_date, currency, regime_legend


def _apply_ubl_document_header(root: Element, parsed: ParsedEInvoice) -> None:
    """Read the issue date, currency and statutory mention off the root's children."""
    invoice_date, currency, regime_legend = _ubl_document_header_values(
        root,
        existing_regime_legend=parsed.regime_legend,
    )
    if invoice_date is not None:
        parsed.invoice_date = invoice_date
    if currency is not None:
        parsed.currency = currency
    if regime_legend is not None:
        parsed.regime_legend = regime_legend


def _apply_ubl_parties(root: Element, parsed: ParsedEInvoice) -> None:
    """Read both parties' identity and address off their UBL party blocks."""
    for party_tag, target in (("AccountingSupplierParty", "supplier"), ("AccountingCustomerParty", "customer")):
        found = find_all(root, party_tag)
        if found:
            setattr(parsed, f"{target}_tax_id", _iva_id(found[0]))
            setattr(parsed, f"{target}_name", ubl_party_name(found[0]))
            setattr(parsed, f"{target}_postal_code", ubl_postal_code(found[0]))
            setattr(parsed, f"{target}_country_code", ubl_country_code(found[0]))


def _ubl_subtotal_category(subtotal: Element, *, issued_on: date | None) -> str | None:
    """Return the tax category the subtotal's cbc:ID names, if it names one."""
    for category in find_all(subtotal, "TaxCategory"):
        for child in category:
            if local_tag_name(child.tag) == "ID" and (child.text is not None and child.text):
                return category_for(child.text, issued_on=issued_on)
    return None


def _ubl_subtotal_scheme_tokens(subtotal: Element) -> tuple[str, ...]:
    """Return what a subtotal's ``cac:TaxScheme`` states, by identifier and by name."""
    tokens: list[str] = []
    for scheme in find_all(subtotal, "TaxScheme"):
        for name in ("ID", "Name"):
            stated = direct_child_text(scheme, name)
            if stated is not None:
                tokens.append(stated)
    return tuple(tokens)


def _ubl_withheld_tax(subtotal: Element, *, is_irpf: bool) -> ParsedWithheldTax:
    tokens = _ubl_subtotal_scheme_tokens(subtotal)
    return ParsedWithheldTax(
        stated_type=tokens[0] if tokens else None,
        is_irpf=is_irpf,
        rate=decimal(first_text(subtotal, "Percent")),
        base=decimal(first_text(subtotal, "TaxableAmount")),
        amount=decimal(first_text(subtotal, "TaxAmount")),
    )


def _ubl_last_tax_amount_text(tax_total: Element) -> str | None:
    """Return the text of the last non-empty ``cbc:TaxAmount`` child of a tax total."""
    stated: str | None = None
    for child in tax_total:
        if local_tag_name(child.tag) == "TaxAmount" and (child.text is not None and child.text):
            stated = child.text
    return stated


def _append_ubl_iva_subtotal(subtotal: Element, parsed: ParsedEInvoice) -> None:
    """Record one IVA subtotal's rate, base and cuota, and the first category named."""
    parsed.iva_breakdown.append(
        (
            decimal(first_text(subtotal, "Percent")),
            decimal(first_text(subtotal, "TaxableAmount")),
            decimal(first_text(subtotal, "TaxAmount")),
        ),
    )
    if parsed.iva_category is None:
        parsed.iva_category = _ubl_subtotal_category(subtotal, issued_on=_stated_issue_date(parsed))


def _ubl_irpf_subtotals(subtotals: list[Element]) -> list[Element]:
    """Return the subtotals whose tax scheme names IRPF."""
    return [row for row in subtotals if any(_names_irpf(token) for token in _ubl_subtotal_scheme_tokens(row))]


def _apply_ubl_tax_total(tax_total: Element, parsed: ParsedEInvoice) -> None:
    """Read one ``cac:TaxTotal``: its IRPF subtotals as withheld, the rest as IVA."""
    subtotals = find_all(tax_total, "TaxSubtotal")
    irpf = _ubl_irpf_subtotals(subtotals)
    parsed.withheld_taxes.extend(_ubl_withheld_tax(row, is_irpf=False) for row in irpf)
    if subtotals and len(irpf) == len(subtotals):
        return
    stated_amount = _ubl_last_tax_amount_text(tax_total)
    if stated_amount is not None:
        parsed.iva_amount = decimal(stated_amount)
    for subtotal in subtotals:
        if any(subtotal is row for row in irpf):
            continue
        _append_ubl_iva_subtotal(subtotal, parsed)


def _apply_ubl_tax_totals(root: Element, parsed: ParsedEInvoice) -> None:
    """Read the cuota, the per-rate breakdown, and the first stated category.

    A subtotal naming IRPF inside ``cac:TaxTotal`` is not IVA whatever element
    carries it. UBL's own place for a withholding is ``cac:WithholdingTaxTotal``, so
    this one is recorded as a withheld figure that was not read.

    Only the document's own ``cac:TaxTotal`` children are read: UBL 2.1 lets an
    invoice line carry one too, and counting it beside the document's would
    state the same tax twice.
    """
    for tax_total in (child for child in root if local_tag_name(child.tag) == "TaxTotal"):
        _apply_ubl_tax_total(tax_total, parsed)


def _ubl_lines(root: Element) -> list[ParsedEInvoiceLine]:
    """Project both invoice and credit-note lines onto the shared line record."""
    lines: list[ParsedEInvoiceLine] = []
    for line in find_all(root, "InvoiceLine") + find_all(root, "CreditNoteLine"):
        rate = None
        for category in find_all(line, "ClassifiedTaxCategory"):
            rate = decimal(first_text(category, "Percent"))
        lines.append(
            ParsedEInvoiceLine(
                description=first_text(line, "Name") or first_text(line, "Description"),
                quantity=decimal(first_text(line, "InvoicedQuantity")) or decimal(first_text(line, "CreditedQuantity")),
                unit_price=decimal(first_text(line, "PriceAmount")),
                taxable_base=decimal(first_text(line, "LineExtensionAmount")),
                iva_rate=rate,
            ),
        )
    return lines


def _ubl_withholding_blocks(root: Element) -> list[Element]:
    """Return the document's ``cac:WithholdingTaxTotal`` blocks, the header's if it states any.

    UBL 2.1 allows the block on the document and on each line, and the two restate
    one withholding, so lines are consulted only when the document has none.
    """
    header = [child for child in root if local_tag_name(child.tag) == "WithholdingTaxTotal"]
    if header:
        return header
    return [
        block
        for line in find_all(root, "InvoiceLine") + find_all(root, "CreditNoteLine")
        for block in line
        if local_tag_name(block.tag) == "WithholdingTaxTotal"
    ]


def _apply_ubl_withholding(root: Element, parsed: ParsedEInvoice) -> None:
    """Read ``cac:WithholdingTaxTotal``, a UBL 2.1 element EN 16931 leaves out.

    The element says a tax was withheld and ``cac:TaxScheme`` says which one, so
    only a scheme naming IRPF is a retencion. Without that the figure stays unread:
    other jurisdictions use this element for other taxes.
    """
    totals: list[Decimal] = []
    for block in _ubl_withholding_blocks(root):
        stated = decimal(direct_child_text(block, "TaxAmount"))
        if stated is not None:
            totals.append(stated)
        for subtotal in find_all(block, "TaxSubtotal"):
            tokens = _ubl_subtotal_scheme_tokens(subtotal)
            parsed.withheld_taxes.append(_ubl_withheld_tax(subtotal, is_irpf=any(_names_irpf(t) for t in tokens)))
    if totals:
        parsed.withheld_total = sum(totals, Decimal("0"))
    _read_retention_from_withheld(parsed)


def _parse_ubl(root: Element) -> ParsedEInvoice:
    """Parse an OASIS UBL invoice or credit note."""
    parsed = ParsedEInvoice(shape=DocumentShape.XML_UBL)
    parsed.invoice_number = _ubl_invoice_number(root)
    _apply_ubl_document_header(root, parsed)
    _apply_ubl_parties(root, parsed)
    for total in find_all(root, "LegalMonetaryTotal"):
        parsed.taxable_base = decimal(first_text(total, "TaxExclusiveAmount"))
        parsed.grand_total = decimal(first_text(total, "TaxInclusiveAmount"))
    _apply_ubl_tax_totals(root, parsed)
    _apply_ubl_withholding(root, parsed)
    parsed.lines.extend(_ubl_lines(root))
    return parsed


def _retention_applies_to_the_whole_base(irpf: list[ParsedWithheldTax], taxable_base: Decimal | None) -> bool:
    """Return whether one flat rate on the invoice's base describes these withholdings."""
    if len({row.rate for row in irpf}) != 1:
        return False
    if taxable_base is None or any(row.base is None for row in irpf):
        return len(irpf) == 1
    return abs(sum((row.base or Decimal("0") for row in irpf), Decimal("0")) - taxable_base) <= Decimal("0.01")


def _assign_irpf_retention_amount(parsed: ParsedEInvoice, irpf: list[ParsedWithheldTax]) -> None:
    """Set the retencion from the IRPF rows' own amounts, else from a stated total when all rows are IRPF."""
    amounts = [row.amount for row in irpf if row.amount is not None]
    if len(amounts) == len(irpf):
        parsed.retencion_amount = sum(amounts, Decimal("0"))
    elif len(irpf) == len(parsed.withheld_taxes):
        parsed.retencion_amount = parsed.withheld_total


def _read_retention_from_withheld(parsed: ParsedEInvoice) -> None:
    """Take the IRPF withholdings a record states as its retencion, and nothing else.

    A stated total with no tax block identifies no tax, so only its zero is usable:
    a format requiring the element states zero when nothing was withheld. A rate is
    kept only where one flat rate on the invoice's own base describes the withholding,
    because the invoice holds a single rate and checks it against that base.
    """
    stated_total = parsed.withheld_total
    if not parsed.withheld_taxes:
        parsed.retencion_amount = stated_total if stated_total is not None and stated_total == 0 else None
        return
    irpf = [row for row in parsed.withheld_taxes if row.is_irpf]
    if not irpf:
        return
    _assign_irpf_retention_amount(parsed, irpf)
    if parsed.retencion_amount is not None and _retention_applies_to_the_whole_base(irpf, parsed.taxable_base):
        parsed.retencion_rate = irpf[0].rate


def _facturae_withheld_tax_nodes(invoice: Element) -> list[Element]:
    """Return the ``TaxesWithheld/Tax`` rows of the invoice, or of its lines if it has none.

    The schema allows the block at both levels and calls the line-level one
    informative, so reading both would count one withholding twice.
    """

    def rows(owner: Element) -> list[Element]:
        return [
            tax
            for block in owner
            if local_tag_name(block.tag) == "TaxesWithheld"
            for tax in block
            if local_tag_name(tax.tag) == "Tax"
        ]

    return rows(invoice) or [tax for line in find_all(invoice, "InvoiceLine") for tax in rows(line)]


def _stated_issue_date(parsed: ParsedEInvoice) -> date | None:
    """Return the issue date the record states, or ``None`` when it states none a date can be read from."""
    try:
        return None if parsed.invoice_date is None else date.fromisoformat(parsed.invoice_date.strip())
    except ValueError:
        return None


def _apply_facturae_withholding(invoice: Element, parsed: ParsedEInvoice) -> None:
    """Read the withheld taxes, of which only the ``TaxTypeCode`` the registry names is IRPF."""
    taxes = _facturae_withheld_tax_nodes(invoice)
    irpf_code = facturae_irpf_tax_type_code(issued_on=_stated_issue_date(parsed)) if taxes else None
    for tax in taxes:
        rate, base, amount, _surcharges = _facturae_tax_band(tax)
        stated_type = direct_child_text(tax, "TaxTypeCode")
        parsed.withheld_taxes.append(
            ParsedWithheldTax(
                stated_type=stated_type,
                is_irpf=stated_type == irpf_code,
                rate=rate,
                base=base,
                amount=amount,
            ),
        )
    _read_retention_from_withheld(parsed)


def _facturae_suplidos(totals: Element) -> Decimal | None:
    """Return the suplidos the invoice totals state, aggregate preferred.

    Facturae states them twice and both statements are optional: the itemised
    ``ReimbursableExpenses`` block (`Suplidos incorporados en la factura`) and
    the ``TotalReimbursableExpenses`` aggregate (`Total de suplidos`). The
    aggregate is the format's own sum, so it is taken where present; the block
    is summed only when it is not, which keeps this from disagreeing with the
    document about its own arithmetic.
    """
    aggregate = decimal(first_text(totals, "TotalReimbursableExpenses"))
    if aggregate is not None:
        return aggregate
    amounts = [
        amount
        for expense in find_all(totals, "ReimbursableExpense")
        if (amount := decimal(first_text(expense, "ReimbursableExpenseAmount"))) is not None
    ]
    return sum(amounts, Decimal("0")) if amounts else None


def _facturae_invoice_total(
    *,
    base: Decimal | None,
    output_tax: Decimal | None,
    suplidos: Decimal | None,
) -> Decimal | None:
    """Return the contraprestacion, derived from the elements that carry it.

    ``None`` when the document states no base: a total assembled from nothing is
    a figure this reader invented, and the closure check treats an absent total
    as nothing verified rather than as a zero.
    """
    if base is None:
        return None
    return base + (output_tax or Decimal("0")) + (suplidos or Decimal("0"))


def _apply_facturae_parties(root: Element, parsed: ParsedEInvoice) -> None:
    """Read both parties by ROLE, never by position, off their Facturae blocks."""
    for party_tag, target in (("SellerParty", "supplier"), ("BuyerParty", "customer")):
        found = find_all(root, party_tag)
        if found:
            # Facturae states the fiscal identifier in TaxIdentificationNumber,
            # which IS the IVA number; no SIRET/Steuernummer ambiguity here.
            setattr(parsed, f"{target}_tax_id", first_text(found[0], "TaxIdentificationNumber"))
            setattr(parsed, f"{target}_name", facturae_party_name(found[0]))
            setattr(parsed, f"{target}_postal_code", facturae_postal_code(found[0]))
            stated_country = facturae_country_code(found[0])
            if stated_country is not None:
                block, code = stated_country
                setattr(parsed, f"{target}_country_code", code)
                # Recorded from the walk rather than left to a per-format table:
                # the two address blocks are alternatives, so only the read knows
                # which one this party used.
                parsed.element_paths[f"{target}_country_code"] = f"{party_tag}/{block}/CountryCode"


def _apply_facturae_identification(invoice: Element, parsed: ParsedEInvoice) -> None:
    """Read the invoice's number, series, issue data and statutory mention."""
    for header in find_all(invoice, "InvoiceHeader"):
        # Scoped to the header's own children: a rectificativa restates the
        # CORRECTED invoice's number under Corrective/ in this same subtree.
        parsed.invoice_number = direct_child_text(header, "InvoiceNumber")
        parsed.invoice_series = direct_child_text(header, "InvoiceSeriesCode")
        stated_class = direct_child_text(header, "InvoiceClass")
        try:
            parsed.facturae_invoice_class = FacturaeInvoiceClass(stated_class) if stated_class is not None else None
        except ValueError:
            parsed.facturae_invoice_class = None
        # The number of the invoice this one CORRECTS, which the direct-child
        # scoping above deliberately steps past. It was read and discarded: a
        # rectificativa is a different CLASS of invoice by RD 1619/2012 art. 15,
        # and a confirm that cannot say so mints one as ordinaria with nothing
        # downstream able to tell -- the Invoice model's own rectificativa
        # invariants never fire, because nothing ever states the class.
        for corrective in find_all(header, "Corrective"):
            parsed.rectifies_invoice_number = direct_child_text(corrective, "InvoiceNumber")
            if parsed.rectifies_invoice_number is not None:
                break
    for issue in find_all(invoice, "InvoiceIssueData"):
        parsed.invoice_date = first_text(issue, "IssueDate")
        parsed.currency = first_text(issue, "InvoiceCurrencyCode")
    # Facturae states the statutory mention as a LegalLiterals/LegalReference
    # free-text line, the national counterpart of the EN16931 note.
    for literals in find_all(invoice, "LegalLiterals"):
        parsed.regime_legend = first_text(literals, "LegalReference")
        if parsed.regime_legend is not None:
            break


def _apply_facturae_totals(invoice: Element, parsed: ParsedEInvoice) -> Decimal | None:
    """Read the stated totals and derive the contraprestacion.

    Returns:
        ``TotalTaxOutputs`` as stated, which the cuota fallback needs when the
        document carries no per-band tax nodes to sum instead.
    """
    total_output_tax: Decimal | None = None
    for totals in find_all(invoice, "InvoiceTotals"):
        parsed.taxable_base = decimal(first_text(totals, "TotalGrossAmountBeforeTaxes"))
        total_output_tax = decimal(first_text(totals, "TotalTaxOutputs"))
        # `Total impuestos retenidos` -- the schema's own words, and a required
        # element, so a document withholding nothing states zero here. It names no
        # tax: which tax was withheld is said by the `TaxesWithheld` rows.
        parsed.withheld_total = decimal(first_text(totals, "TotalTaxesWithheld"))
        # `Total de suplidos`, with the block `Suplidos incorporados en la
        # factura` as the fallback: both are optional and a document may state
        # the itemised block without the aggregate, so the aggregate is
        # preferred and the block summed only when it is absent.
        parsed.suplidos_amount = _facturae_suplidos(totals)
        # DERIVED, never read. There is no Facturae element equal to the invoice
        # total this codebase means: `InvoiceTotal` is documented as
        # `TotalGrossAmountBeforeTaxes + TotalTaxOutputs - TotalTaxesWithheld`,
        # so it is already net of retencion, and reimbursable expenses join only
        # at `TotalExecutableAmount`. Reading it as the total therefore
        # understated a withheld invoice by exactly its retencion, and the
        # arithmetic-closure check refused correct professional invoices for it.
        #
        # `TotalTaxOutputs` is `Sumatorio de todas Cuotas y Recargos de
        # Equivalencia`, so it already carries both tax terms of the identity
        # `total = base + cuota + recargo + suplido`, and the sum below is that
        # identity read straight off the document's own documented parts.
        parsed.grand_total = _facturae_invoice_total(
            base=parsed.taxable_base,
            output_tax=total_output_tax,
            suplidos=parsed.suplidos_amount,
        )
    return total_output_tax


def _facturae_header_tax_nodes(invoice: Element) -> list[Element]:
    """Return ONLY the invoice-level Tax nodes, never the per-line ones.

    Facturae states taxes TWICE: once at invoice level under TaxesOutputs and
    again per line under Items/InvoiceLine/TaxesOutputs. A descendant walk
    collects both and double-counts every rate -- the invoice-level breakdown
    then reports each band twice, so a single-rate invoice looks like a
    two-rate one and the identity check fails on a document that is perfectly
    well formed. Scope to the INVOICE-level block only.
    """
    header_taxes: list[Element] = []
    for node in invoice:
        if local_tag_name(node.tag) == "TaxesOutputs":
            header_taxes.extend(child for child in node if local_tag_name(child.tag) == "Tax")
    return header_taxes


def _facturae_tax_band(
    tax: Element,
) -> tuple[Decimal | None, Decimal | None, Decimal | None, tuple[Decimal, ...]]:
    """Read one Facturae tax band and all of its stated surcharge amounts."""
    rate = decimal(first_text(tax, "TaxRate"))
    base = None
    amount = None
    for base_node in find_all(tax, "TaxableBase"):
        base = decimal(first_text(base_node, "TotalAmount"))
    for amount_node in find_all(tax, "TaxAmount"):
        amount = decimal(first_text(amount_node, "TotalAmount"))
    surcharges: list[Decimal] = []
    for surcharge_node in find_all(tax, "EquivalenceSurchargeAmount"):
        surcharge = decimal(first_text(surcharge_node, "TotalAmount"))
        if surcharge is not None:
            surcharges.append(surcharge)
    return rate, base, amount, tuple(surcharges)


def _apply_facturae_tax_bands(
    invoice: Element,
    parsed: ParsedEInvoice,
    *,
    total_output_tax: Decimal | None,
) -> None:
    """Read the per-band breakdown, the recargo term, and the cuota term."""
    header_taxes = _facturae_header_tax_nodes(invoice)
    band_cuotas: list[Decimal] = []
    band_recargos: list[Decimal] = []
    for tax in header_taxes:
        rate, base, amount, surcharges = _facturae_tax_band(tax)
        if amount is not None:
            band_cuotas.append(amount)
        parsed.iva_breakdown.append((rate, base, amount))
        band_recargos.extend(surcharges)
    # Summed, never last-wins: a document charging two rates surcharges each
    # band separately, so keeping only the final node silently under-reports the
    # recargo -- and it under-reports it into a term the printed-total identity
    # depends on, where the shortfall reads as a misread total rather than as a
    # dropped surcharge.
    parsed.recargo_amount = sum(band_recargos, Decimal("0")) if band_recargos else None
    # `iva_amount` is the identity's CUOTA term, which excludes the recargo de
    # equivalencia carried beside it. Facturae's `TotalTaxOutputs` is a different
    # figure: it is total repercutido output tax, cuota PLUS surcharge, so
    # assigning it here states 26,20 where the identity means 21,00 and the
    # recargo is then added a second time from its own term. The per-band
    # `TaxAmount` is the cuota by construction -- `EquivalenceSurchargeAmount` is
    # its sibling, not part of it -- so reading the term from there cannot carry
    # a surcharge into it, which is why the bands are preferred over correcting
    # the combined figure after the fact.
    if band_cuotas:
        parsed.iva_amount = sum(band_cuotas, Decimal("0"))
    elif total_output_tax is not None:
        parsed.iva_amount = total_output_tax - (parsed.recargo_amount or Decimal("0"))


def _facturae_lines(invoice: Element) -> list[ParsedEInvoiceLine]:
    """Project the Facturae line items onto the shared line record."""
    lines: list[ParsedEInvoiceLine] = []
    for line in find_all(invoice, "InvoiceLine"):
        rate = None
        # Scoped to the outputs: a line's `TaxesWithheld` holds `Tax` rows too, and
        # their rate is the retencion's, never this line's IVA.
        for block in line:
            if local_tag_name(block.tag) == "TaxesOutputs":
                for tax in find_all(block, "Tax"):
                    rate = decimal(first_text(tax, "TaxRate"))
        lines.append(
            ParsedEInvoiceLine(
                description=first_text(line, "ItemDescription"),
                quantity=decimal(first_text(line, "Quantity")),
                unit_price=decimal(first_text(line, "UnitPriceWithoutTax")),
                taxable_base=decimal(first_text(line, "TotalCost")),
                iva_rate=rate,
            ),
        )
    return lines


def _parse_facturae(root: Element) -> ParsedEInvoice:
    """Parse a Facturae 3.2.x invoice (the Spanish national format)."""
    parsed = ParsedEInvoice(shape=DocumentShape.XML_FACTURAE)
    _apply_facturae_parties(root, parsed)
    invoices = find_all(root, "Invoice")
    if not invoices:
        return parsed
    invoice = invoices[0]
    _apply_facturae_identification(invoice, parsed)
    total_output_tax = _apply_facturae_totals(invoice, parsed)
    _apply_facturae_tax_bands(invoice, parsed, total_output_tax=total_output_tax)
    _apply_facturae_withholding(invoice, parsed)
    parsed.lines.extend(_facturae_lines(invoice))
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
                embedded = _PARSERS[inner_shape](inner)
                embedded.record_text = record_text(inner)
                return embedded
        raise EInvoiceXmlParseError("PDF carries an embedded file but no readable e-invoice record")
    if shape not in _PARSERS:
        raise EInvoiceXmlParseError(f"document shape {shape.value!r} carries no structured invoice record")
    root = parse_hardened_xml(payload)
    parsed = _PARSERS[shape](root)
    parsed.record_text = record_text(root)
    return parsed
