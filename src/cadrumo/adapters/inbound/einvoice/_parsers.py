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

from decimal import Decimal
from enum import StrEnum
from xml.etree.ElementTree import Element

from ....core.decimal.coercion import coerce_decimal
from ....core.document_shape import DocumentShape
from ._shape import iter_pdf_embedded_files, probe_document_shape
from ._xml import EInvoiceXmlParseError, parse_hardened_xml

__all__ = ["FacturaeInvoiceClass", "ParsedEInvoice", "ParsedEInvoiceLine", "parse_einvoice_document"]

# Tax-scheme identifiers that mark an element as carrying an IVA number rather
# than some other national registration. EN16931 uses schemeID="VA"; Facturae
# names the person-type/residence explicitly.
_IVA_SCHEME_TOKENS = frozenset({"va", "vat", "vatid"})

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
        "customer_country_code",
        "customer_name",
        "customer_postal_code",
        "customer_tax_id",
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
        "shape",
        "suplidos_amount",
        "supplier_country_code",
        "supplier_name",
        "supplier_postal_code",
        "supplier_tax_id",
        "taxable_base",
    )

    def __init__(self, *, shape: DocumentShape) -> None:
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
        self.lines: list[ParsedEInvoiceLine] = []
        self.iva_breakdown: list[tuple[Decimal | None, Decimal | None, Decimal | None]] = []


#: Separator between adjacent text nodes in a record's extracted text.
#:
#: A NUL rather than a newline, and that is load-bearing rather than exotic. The
#: anchor search normalises whitespace runs to single spaces before matching, so
#: joining on ANY whitespace makes two adjacent element values contiguous: a
#: Facturae party name split across ``Name``, ``FirstSurname`` and
#: ``SecondSurname`` reassembles into exactly the string the parser composes from
#: them, and an ASSEMBLED value then anchors as though the document printed it
#: verbatim. It does not -- the document prints three separate values -- and
#: refusing that is a property the raw-file haystack had and a naive text-node
#: haystack silently dropped. A NUL survives normalisation, so the boundary
#: between two nodes stays a boundary.
_TEXT_NODE_SEPARATOR = "\x00"


def _record_text(root: Element) -> str:
    """Return every text node in *root*, separated so no two of them merge.

    The haystack the anchor check searches. Markup is excluded because a tag name
    is not something the document states -- a two-character value would otherwise
    match one, and a record carrying no such element at all would ground a value.
    Adjacent nodes are kept apart by :data:`_TEXT_NODE_SEPARATOR`, because an
    anchor spanning two of them is an assembled value rather than a printed one.
    """
    fragments: list[str] = []
    for node in root.iter():
        for raw in (node.text, node.tail):
            if raw and raw.strip():
                fragments.append(raw.strip())
    return _TEXT_NODE_SEPARATOR.join(fragments)


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


def _direct_child_text(parent: Element, name: str) -> str | None:
    """Return the text of *parent*'s own child, never a deeper descendant.

    The descendant walk :func:`_first_text` performs is right for a leaf stated
    once in a subtree, and wrong wherever the same local name is restated at a
    deeper level with a different meaning. A Facturae ``InvoiceHeader`` on a
    rectificativa carries the corrected invoice's identifier as
    ``Corrective/InvoiceNumber`` alongside its own ``InvoiceNumber``, so a
    descendant walk has two candidates and picks correctly only because the
    schema happens to fix their order.
    """
    for node in parent:
        if _local(node.tag) == name and node.text and node.text.strip():
            return node.text.strip()
    return None


def _ubl_party_name(party: Element) -> str | None:
    """Return a UBL party's name, preferring its registered legal name.

    EN16931 maps the party's legal name to ``PartyLegalEntity/RegistrationName``
    (BT-27 / BT-44) and its trading name to ``PartyName/Name`` (BT-28 / BT-45).
    The legal name is the one a filing reconciles against, so it wins; the
    trading name is the fallback for a document that states only that.
    """
    registration = _first_text(party, "RegistrationName")
    if registration:
        return registration
    for named in _find_all(party, "PartyName"):
        found = _direct_child_text(named, "Name")
        if found:
            return found
    return None


def _facturae_party_name(party: Element) -> str | None:
    """Return a Facturae party's stated name, legal entity or natural person.

    Facturae states the name in one of two mutually exclusive blocks selected by
    ``PersonTypeCode``: ``LegalEntity/CorporateName`` for a company, or
    ``Individual`` split across ``Name``, ``FirstSurname`` and ``SecondSurname``
    for a natural person. The two surnames are joined back into the single
    display name the document means, because Spanish naming carries both and a
    counterparty recorded under the given name alone is not identifiable.
    """
    corporate = _first_text(party, "CorporateName")
    if corporate:
        return corporate
    for individual in _find_all(party, "Individual"):
        parts = [_direct_child_text(individual, part) for part in ("Name", "FirstSurname", "SecondSurname")]
        joined = " ".join(part for part in parts if part)
        if joined:
            return joined
    return None


def _facturae_postal_code(party: Element) -> str | None:
    """Return a Facturae party's Spanish postal code, or nothing.

    Scoped to ``AddressInSpain/PostCode``, the element Facturae dedicates to the
    code. The sibling ``OverseasAddress`` block is deliberately not read: a party
    established abroad has no Spanish IVA territory to resolve, so recovering
    anything from it would produce a value the resolver must then discard, and
    that block states its code jointly with the town rather than on its own.
    """
    for address in _find_all(party, "AddressInSpain"):
        found = _direct_child_text(address, "PostCode")
        if found:
            return found
    return None


def _facturae_country_code(party: Element) -> str | None:
    """Return a Facturae party's stated country code, VERBATIM and in ISO alpha-3.

    Scoped to ``AddressInSpain/CountryCode``, the sibling of the ``PostCode``
    element beside it, and read for the country half of the establishment
    question the postal code answers only the sub-national half of.

    **The value is carried exactly as stated, in the code system Facturae uses.**
    That system is ISO 3166-1 alpha-3 -- ``ESP``, not ``ES`` -- and translating it
    here would put a country authority inside a syntax parser. The
    correspondence is registry data and the lookup belongs downstream; this is a
    read.

    ``OverseasAddress`` is deliberately not consulted, matching
    :func:`_facturae_postal_code`: that block is how a foreign-established party
    states its address, and its country is reached through the same element name
    there, so widening this walk would silently change WHICH address a party's
    country is read from.
    """
    for address in _find_all(party, "AddressInSpain"):
        found = _direct_child_text(address, "CountryCode")
        if found:
            return found
    return None


def _ubl_country_code(party: Element) -> str | None:
    """Return a UBL party's stated country code (EN16931 BT-40 / BT-55).

    UBL carries it in ``cac:PostalAddress/cac:Country/cbc:IdentificationCode``,
    beside the ``PostalZone`` :func:`_ubl_postal_code` already reads, and states
    it in ISO 3166-1 alpha-2. Carried verbatim for the same reason the Facturae
    code is: what a document states is a read, what a code MEANS is not the
    parser's question.

    Scoped to the ``Country`` element rather than taken from the first
    ``IdentificationCode`` in the address subtree: UBL uses that local name for
    other coded values, and a descendant walk would pick whichever the schema
    happened to order first.
    """
    for address in _find_all(party, "PostalAddress"):
        for country in _find_all(address, "Country"):
            found = _direct_child_text(country, "IdentificationCode")
            if found:
                return found
    return None


def _ubl_postal_code(party: Element) -> str | None:
    """Return a UBL party's post code (EN16931 BT-38 / BT-53).

    UBL carries it in ``cac:PostalAddress/cbc:PostalZone``, its own element, so
    this is a lookup rather than a parse of the address's free-text lines.
    """
    for address in _find_all(party, "PostalAddress"):
        found = _direct_child_text(address, "PostalZone")
        if found:
            return found
    return None


def _cii_postal_code(party: Element) -> str | None:
    """Return a CII party's post code (EN16931 BT-38 / BT-53).

    CII carries it in ``ram:PostalTradeAddress/ram:PostcodeCode``, again its own
    element beside the free-text address lines rather than inside them.
    """
    for address in _find_all(party, "PostalTradeAddress"):
        found = _direct_child_text(address, "PostcodeCode")
        if found:
            return found
    return None


def _cii_country_code(party: Element) -> str | None:
    """Return a CII party's stated country code (EN16931 BT-40 / BT-55).

    CII carries it in ``ram:PostalTradeAddress/ram:CountryID``, its own element
    beside the ``PostcodeCode`` :func:`_cii_postal_code` already reads, and
    states it in ISO 3166-1 alpha-2 -- the system UBL uses, not Facturae's
    alpha-3. Carried verbatim regardless: resolving what a code MEANS belongs to
    the country authority, and doing it here would make this module a second one.

    Scoped to the address element rather than searched across the party subtree.
    A CII party also carries ``ram:SpecifiedTaxRegistration``, whose id opens
    with the two letters of a country for every EU IVA number, so a descendant
    walk for a two-letter code would read a tax-scheme prefix as the party's
    place of establishment -- a value that is usually right and silently wrong
    exactly where a party is registered somewhere it is not established.
    """
    for address in _find_all(party, "PostalTradeAddress"):
        found = _direct_child_text(address, "CountryID")
        if found:
            return found
    return None


def _decimal(raw: str | None) -> Decimal | None:
    """Parse a fixed-point amount from machine-produced e-invoice XML text.

    Routes through the canonical machine-produced-text coercer rather than a
    bare ``Decimal(...)`` construction: the source is structured e-invoice
    XML (UBL/Facturae), not operator-typed text, so ``coerce_decimal``'s
    silent-``None``-on-failure contract is the correct one, not
    ``try_parse_canonical_decimal``'s operator-grammar validation.
    """
    # DECIMAL-TEXT-RATIONALE-EINVOICE-XML: the separator convention is fixed by
    # the format, not chosen by a writer. UBL and Facturae both specify a
    # dot-decimal xsd:decimal amount with no thousands grouping, so the
    # ``1.000`` that is ambiguous in operator text is unambiguously one here.
    return coerce_decimal(raw)


def _iva_id(party: Element) -> str | None:
    """Return the party's IVA number, never a SIRET or Steuernummer.

    Prefers an element explicitly scheme-tagged as ``VAT``. Falls back to a value
    carrying a two-letter country prefix, which is the EU IVA-id shape and
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
        if scheme in _IVA_SCHEME_TOKENS:
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


def _apply_cii_document_header(root: Element, parsed: ParsedEInvoice) -> None:
    """Read the number, date and statutory mention off the ExchangedDocument."""
    docs = _find_all(root, "ExchangedDocument")
    if not docs:
        return
    parsed.invoice_number = _first_text(docs[0], "ID")
    parsed.invoice_date = _first_text(docs[0], "DateTimeString")
    # CII's document-level IncludedNote is the BT-22 counterpart of UBL's
    # cbc:Note, scoped to the ExchangedDocument so a line-level note cannot
    # be mistaken for the document's statutory mention.
    for note in _find_all(docs[0], "IncludedNote"):
        content = _first_text(note, "Content")
        if content:
            parsed.regime_legend = content
            break


def _apply_cii_parties(root: Element, parsed: ParsedEInvoice) -> None:
    """Read both parties' identity and address off their CII trade-party blocks."""
    for party_name, target in (("SellerTradeParty", "supplier"), ("BuyerTradeParty", "customer")):
        found = _find_all(root, party_name)
        if not found:
            continue
        setattr(parsed, f"{target}_tax_id", _iva_id(found[0]))
        # A direct child: the party subtree also carries a contact's
        # PersonName and may carry a SpecifiedLegalOrganization trading
        # name, neither of which is the party's own stated name.
        setattr(parsed, f"{target}_name", _direct_child_text(found[0], "Name"))
        setattr(parsed, f"{target}_postal_code", _cii_postal_code(found[0]))
        setattr(parsed, f"{target}_country_code", _cii_country_code(found[0]))


def _apply_cii_trade_tax(tax: Element, parsed: ParsedEInvoice) -> None:
    """Append one ApplicableTradeTax tier, keeping the first stated category."""
    parsed.iva_breakdown.append(
        (
            _decimal(_first_text(tax, "RateApplicablePercent")),
            _decimal(_first_text(tax, "BasisAmount")),
            _decimal(_first_text(tax, "CalculatedAmount")),
        ),
    )
    if parsed.iva_category is None:
        parsed.iva_category = _category_for(_first_text(tax, "CategoryCode"))
    if parsed.regime_legend is None:
        parsed.regime_legend = _first_text(tax, "ExemptionReason")


def _apply_cii_settlement(root: Element, parsed: ParsedEInvoice) -> None:
    """Read the currency, the header totals and the per-rate tax breakdown."""
    for settlement in _find_all(root, "ApplicableHeaderTradeSettlement"):
        parsed.currency = _first_text(settlement, "InvoiceCurrencyCode")
        for total in _find_all(settlement, "SpecifiedTradeSettlementHeaderMonetarySummation"):
            parsed.taxable_base = _decimal(_first_text(total, "TaxBasisTotalAmount"))
            parsed.iva_amount = _decimal(_first_text(total, "TaxTotalAmount"))
            parsed.grand_total = _decimal(_first_text(total, "GrandTotalAmount"))
        for tax in _find_all(settlement, "ApplicableTradeTax"):
            _apply_cii_trade_tax(tax, parsed)


def _cii_lines(root: Element) -> list[ParsedEInvoiceLine]:
    """Read each line item, taking the LAST stated rate as that line's rate."""
    lines: list[ParsedEInvoiceLine] = []
    for item in _find_all(root, "IncludedSupplyChainTradeLineItem"):
        rate = None
        for tax in _find_all(item, "ApplicableTradeTax"):
            rate = _decimal(_first_text(tax, "RateApplicablePercent"))
        lines.append(
            ParsedEInvoiceLine(
                description=_first_text(item, "Name"),
                quantity=_decimal(_first_text(item, "BilledQuantity")),
                unit_price=_decimal(_first_text(item, "ChargeAmount")),
                taxable_base=_decimal(_first_text(item, "LineTotalAmount")),
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
        if _local(child.tag) == "ID" and child.text:
            return child.text.strip()
    return None


def _apply_ubl_document_header(root: Element, parsed: ParsedEInvoice) -> None:
    """Read the issue date, currency and statutory mention off the root's children."""
    for child in root:
        if _local(child.tag) == "IssueDate" and child.text:
            parsed.invoice_date = child.text.strip()
        if _local(child.tag) == "DocumentCurrencyCode" and child.text:
            parsed.currency = child.text.strip()
        # A document-level cbc:Note is where UBL carries the statutory mention
        # an issuer prints (EN16931 BT-22). Read as free text in the document's
        # OWN language, never matched against a Spanish phrase list: an
        # intra-community invoice states its exemption in the issuer's
        # language, and a phrase match would silently recover nothing there
        # while appearing to work on every domestic document.
        if _local(child.tag) == "Note" and child.text and parsed.regime_legend is None:
            parsed.regime_legend = child.text.strip() or None
    if parsed.regime_legend is None:
        parsed.regime_legend = _first_text(root, "TaxExemptionReason")


def _apply_ubl_parties(root: Element, parsed: ParsedEInvoice) -> None:
    """Read both parties' identity and address off their UBL party blocks."""
    for party_tag, target in (("AccountingSupplierParty", "supplier"), ("AccountingCustomerParty", "customer")):
        found = _find_all(root, party_tag)
        if found:
            setattr(parsed, f"{target}_tax_id", _iva_id(found[0]))
            setattr(parsed, f"{target}_name", _ubl_party_name(found[0]))
            setattr(parsed, f"{target}_postal_code", _ubl_postal_code(found[0]))
            setattr(parsed, f"{target}_country_code", _ubl_country_code(found[0]))


def _ubl_subtotal_category(subtotal: Element) -> str | None:
    """Return the tax category the subtotal's cbc:ID names, if it names one."""
    for category in _find_all(subtotal, "TaxCategory"):
        for child in category:
            if _local(child.tag) == "ID" and child.text:
                return _category_for(child.text)
    return None


def _apply_ubl_tax_totals(root: Element, parsed: ParsedEInvoice) -> None:
    """Read the cuota, the per-rate breakdown, and the first stated category."""
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
                parsed.iva_category = _ubl_subtotal_category(subtotal)


def _ubl_lines(root: Element) -> list[ParsedEInvoiceLine]:
    """Project both invoice and credit-note lines onto the shared line record."""
    lines: list[ParsedEInvoiceLine] = []
    for line in _find_all(root, "InvoiceLine") + _find_all(root, "CreditNoteLine"):
        rate = None
        for category in _find_all(line, "ClassifiedTaxCategory"):
            rate = _decimal(_first_text(category, "Percent"))
        lines.append(
            ParsedEInvoiceLine(
                description=_first_text(line, "Name") or _first_text(line, "Description"),
                quantity=_decimal(_first_text(line, "InvoicedQuantity"))
                or _decimal(_first_text(line, "CreditedQuantity")),
                unit_price=_decimal(_first_text(line, "PriceAmount")),
                taxable_base=_decimal(_first_text(line, "LineExtensionAmount")),
                iva_rate=rate,
            ),
        )
    return lines


def _parse_ubl(root: Element) -> ParsedEInvoice:
    """Parse an OASIS UBL invoice or credit note."""
    parsed = ParsedEInvoice(shape=DocumentShape.XML_UBL)
    parsed.invoice_number = _ubl_invoice_number(root)
    _apply_ubl_document_header(root, parsed)
    _apply_ubl_parties(root, parsed)
    for total in _find_all(root, "LegalMonetaryTotal"):
        parsed.taxable_base = _decimal(_first_text(total, "TaxExclusiveAmount"))
        parsed.grand_total = _decimal(_first_text(total, "TaxInclusiveAmount"))
    _apply_ubl_tax_totals(root, parsed)
    parsed.lines.extend(_ubl_lines(root))
    return parsed


def _facturae_suplidos(totals: Element) -> Decimal | None:
    """Return the suplidos the invoice totals state, aggregate preferred.

    Facturae states them twice and both statements are optional: the itemised
    ``ReimbursableExpenses`` block (`Suplidos incorporados en la factura`) and
    the ``TotalReimbursableExpenses`` aggregate (`Total de suplidos`). The
    aggregate is the format's own sum, so it is taken where present; the block
    is summed only when it is not, which keeps this from disagreeing with the
    document about its own arithmetic.
    """
    aggregate = _decimal(_first_text(totals, "TotalReimbursableExpenses"))
    if aggregate is not None:
        return aggregate
    amounts = [
        amount
        for expense in _find_all(totals, "ReimbursableExpense")
        if (amount := _decimal(_first_text(expense, "ReimbursableExpenseAmount"))) is not None
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
        found = _find_all(root, party_tag)
        if found:
            # Facturae states the fiscal identifier in TaxIdentificationNumber,
            # which IS the IVA number; no SIRET/Steuernummer ambiguity here.
            setattr(parsed, f"{target}_tax_id", _first_text(found[0], "TaxIdentificationNumber"))
            setattr(parsed, f"{target}_name", _facturae_party_name(found[0]))
            setattr(parsed, f"{target}_postal_code", _facturae_postal_code(found[0]))
            setattr(parsed, f"{target}_country_code", _facturae_country_code(found[0]))


def _apply_facturae_identification(invoice: Element, parsed: ParsedEInvoice) -> None:
    """Read the invoice's number, series, issue data and statutory mention."""
    for header in _find_all(invoice, "InvoiceHeader"):
        # Scoped to the header's own children: a rectificativa restates the
        # CORRECTED invoice's number under Corrective/ in this same subtree.
        parsed.invoice_number = _direct_child_text(header, "InvoiceNumber")
        parsed.invoice_series = _direct_child_text(header, "InvoiceSeriesCode")
        stated_class = _direct_child_text(header, "InvoiceClass")
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
        for corrective in _find_all(header, "Corrective"):
            parsed.rectifies_invoice_number = _direct_child_text(corrective, "InvoiceNumber")
            if parsed.rectifies_invoice_number is not None:
                break
    for issue in _find_all(invoice, "InvoiceIssueData"):
        parsed.invoice_date = _first_text(issue, "IssueDate")
        parsed.currency = _first_text(issue, "InvoiceCurrencyCode")
    # Facturae states the statutory mention as a LegalLiterals/LegalReference
    # free-text line, the national counterpart of the EN16931 note.
    for literals in _find_all(invoice, "LegalLiterals"):
        parsed.regime_legend = _first_text(literals, "LegalReference")
        if parsed.regime_legend is not None:
            break


def _apply_facturae_totals(invoice: Element, parsed: ParsedEInvoice) -> Decimal | None:
    """Read the stated totals and derive the contraprestacion.

    Returns:
        ``TotalTaxOutputs`` as stated, which the cuota fallback needs when the
        document carries no per-band tax nodes to sum instead.
    """
    total_output_tax: Decimal | None = None
    for totals in _find_all(invoice, "InvoiceTotals"):
        parsed.taxable_base = _decimal(_first_text(totals, "TotalGrossAmountBeforeTaxes"))
        total_output_tax = _decimal(_first_text(totals, "TotalTaxOutputs"))
        # `Total impuestos retenidos` -- the schema's own words. Read because the
        # total below is stated NET of it, so a reader that skips it cannot tell
        # a withheld invoice from one whose components do not add up.
        parsed.retencion_amount = _decimal(_first_text(totals, "TotalTaxesWithheld"))
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
        if _local(node.tag) == "TaxesOutputs":
            header_taxes.extend(child for child in node if _local(child.tag) == "Tax")
    return header_taxes


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
        rate = _decimal(_first_text(tax, "TaxRate"))
        base = None
        amount = None
        for base_node in _find_all(tax, "TaxableBase"):
            base = _decimal(_first_text(base_node, "TotalAmount"))
        for amount_node in _find_all(tax, "TaxAmount"):
            amount = _decimal(_first_text(amount_node, "TotalAmount"))
        if amount is not None:
            band_cuotas.append(amount)
        parsed.iva_breakdown.append((rate, base, amount))
        for surcharge_node in _find_all(tax, "EquivalenceSurchargeAmount"):
            surcharge = _decimal(_first_text(surcharge_node, "TotalAmount"))
            if surcharge is not None:
                band_recargos.append(surcharge)
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
    for line in _find_all(invoice, "InvoiceLine"):
        rate = None
        for tax in _find_all(line, "Tax"):
            rate = _decimal(_first_text(tax, "TaxRate"))
        lines.append(
            ParsedEInvoiceLine(
                description=_first_text(line, "ItemDescription"),
                quantity=_decimal(_first_text(line, "Quantity")),
                unit_price=_decimal(_first_text(line, "UnitPriceWithoutTax")),
                taxable_base=_decimal(_first_text(line, "TotalCost")),
                iva_rate=rate,
            ),
        )
    return lines


def _parse_facturae(root: Element) -> ParsedEInvoice:
    """Parse a Facturae 3.2.x invoice (the Spanish national format)."""
    parsed = ParsedEInvoice(shape=DocumentShape.XML_FACTURAE)
    _apply_facturae_parties(root, parsed)
    invoices = _find_all(root, "Invoice")
    if not invoices:
        return parsed
    invoice = invoices[0]
    _apply_facturae_identification(invoice, parsed)
    total_output_tax = _apply_facturae_totals(invoice, parsed)
    _apply_facturae_tax_bands(invoice, parsed, total_output_tax=total_output_tax)
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
                embedded.record_text = _record_text(inner)
                return embedded
        raise EInvoiceXmlParseError("PDF carries an embedded file but no readable e-invoice record")
    if shape not in _PARSERS:
        raise EInvoiceXmlParseError(f"document shape {shape.value!r} carries no structured invoice record")
    root = parse_hardened_xml(payload)
    parsed = _PARSERS[shape](root)
    parsed.record_text = _record_text(root)
    return parsed
