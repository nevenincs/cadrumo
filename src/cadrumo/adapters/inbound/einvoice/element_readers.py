"""Namespace-agnostic readers of the text and party fields of an e-invoice XML tree.

The three syntaxes (CII, UBL, Facturae) share these element lookups, so the
format parsers read through them instead of repeating the walk. Nothing here
builds a parsed record; each reader returns the value a document states, or
nothing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final
from xml.etree.ElementTree import Element

from ....core.decimal.coercion import coerce_decimal
from ....domain.calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from .xml import local_tag_name

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


def record_text(root: Element) -> str:
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
            if (raw is not None and raw) and raw.strip():
                fragments.append(raw.strip())
    return _TEXT_NODE_SEPARATOR.join(fragments)


def find_all(root: Element, name: str) -> list[Element]:
    """Return every descendant whose LOCAL name matches, namespace-agnostically."""
    return [node for node in root.iter() if local_tag_name(node.tag) == name]


def first_text(parent: Element, name: str) -> str | None:
    """Return the stripped text of the first matching descendant element, or None."""
    for node in parent.iter():
        if local_tag_name(node.tag) == name and (node.text is not None and node.text) and node.text.strip():
            return node.text.strip()
    return None


def direct_child_text(parent: Element, name: str) -> str | None:
    """Return the text of *parent*'s own child, never a deeper descendant.

    The descendant walk :func:`first_text` performs is right for a leaf stated
    once in a subtree, and wrong wherever the same local name is restated at a
    deeper level with a different meaning. A Facturae ``InvoiceHeader`` on a
    rectificativa carries the corrected invoice's identifier as
    ``Corrective/InvoiceNumber`` alongside its own ``InvoiceNumber``, so a
    descendant walk has two candidates and picks correctly only because the
    schema happens to fix their order.
    """
    for node in parent:
        if local_tag_name(node.tag) == name and (node.text is not None and node.text) and node.text.strip():
            return node.text.strip()
    return None


def ubl_party_name(party: Element) -> str | None:
    """Return a UBL party's name, preferring its registered legal name.

    EN16931 maps the party's legal name to ``PartyLegalEntity/RegistrationName``
    (BT-27 / BT-44) and its trading name to ``PartyName/Name`` (BT-28 / BT-45).
    The legal name is the one a filing reconciles against, so it wins; the
    trading name is the fallback for a document that states only that.
    """
    registration = first_text(party, "RegistrationName")
    if registration is not None and registration:
        return registration
    for named in find_all(party, "PartyName"):
        found = direct_child_text(named, "Name")
        if found is not None and found:
            return found
    return None


def facturae_party_name(party: Element) -> str | None:
    """Return a Facturae party's stated name, legal entity or natural person.

    Facturae states the name in one of two mutually exclusive blocks selected by
    ``PersonTypeCode``: ``LegalEntity/CorporateName`` for a company, or
    ``Individual`` split across ``Name``, ``FirstSurname`` and ``SecondSurname``
    for a natural person. The two surnames are joined back into the single
    display name the document means, because Spanish naming carries both and a
    counterparty recorded under the given name alone is not identifiable.
    """
    corporate = first_text(party, "CorporateName")
    if corporate is not None and corporate:
        return corporate
    for individual in find_all(party, "Individual"):
        parts = [direct_child_text(individual, part) for part in ("Name", "FirstSurname", "SecondSurname")]
        joined = " ".join(part for part in parts if (part is not None and part))
        if joined:
            return joined
    return None


#: Facturae's two mutually exclusive party address blocks.
#:
#: A party states its address in exactly one of them: ``AddressInSpain`` when it
#: is established here, ``OverseasAddress`` when it is established abroad. Both
#: carry a ``CountryCode``, so a reader that opens only the first recovers no
#: country at all from precisely the documents whose country decides the
#: treatment.
_FACTURAE_ADDRESS_BLOCKS: Final = ("AddressInSpain", "OverseasAddress")


def facturae_postal_code(party: Element) -> str | None:
    """Return a Facturae party's Spanish postal code, or nothing.

    Scoped to ``AddressInSpain/PostCode``, the element Facturae dedicates to the
    code. ``OverseasAddress`` has no counterpart element: it states the code
    jointly with the town as ``PostCodeAndTown``, and separating them would be an
    inference about an unspecified format rather than a read. So a party
    established abroad yields no postal code here, which is the honest result --
    and costs nothing downstream, because the postal rung is consulted only where
    the country evidence positively named Spain.
    """
    for address in find_all(party, "AddressInSpain"):
        found = direct_child_text(address, "PostCode")
        if found is not None and found:
            return found
    return None


def facturae_country_code(party: Element) -> tuple[str, str] | None:
    """Return ``(address block name, stated country code)``, or nothing.

    The country half of the establishment question the postal code answers only
    the sub-national half of, read from whichever of
    :data:`_FACTURAE_ADDRESS_BLOCKS` the party states. Both blocks name the
    country through the same ``CountryCode`` element, and the foreign one is the
    case that most needs reading: a party in the overseas block has no Spanish
    postal code to fall back on, so its stated country is the only establishment
    evidence the document carries.

    **The value is carried exactly as stated, in the code system Facturae uses.**
    That system is ISO 3166-1 alpha-3 -- ``ESP``, not ``ES`` -- and translating it
    here would put a country authority inside a syntax parser. The
    correspondence is registry data and the lookup belongs downstream; this is a
    read.

    The block name is returned with the value because the two blocks are
    different places in the document. Provenance that named the Spanish block for
    a value read from the overseas one would point an operator at an element the
    record does not contain.
    """
    for block in _FACTURAE_ADDRESS_BLOCKS:
        for address in find_all(party, block):
            found = direct_child_text(address, "CountryCode")
            if found is not None and found:
                return block, found
    return None


def ubl_country_code(party: Element) -> str | None:
    """Return a UBL party's stated country code (EN16931 BT-40 / BT-55).

    UBL carries it in ``cac:PostalAddress/cac:Country/cbc:IdentificationCode``,
    beside the ``PostalZone`` :func:`ubl_postal_code` already reads, and states
    it in ISO 3166-1 alpha-2. Carried verbatim for the same reason the Facturae
    code is: what a document states is a read, what a code MEANS is not the
    parser's question.

    Scoped to the ``Country`` element rather than taken from the first
    ``IdentificationCode`` in the address subtree: UBL uses that local name for
    other coded values, and a descendant walk would pick whichever the schema
    happened to order first.
    """
    for address in find_all(party, "PostalAddress"):
        for country in find_all(address, "Country"):
            found = direct_child_text(country, "IdentificationCode")
            if found is not None and found:
                return found
    return None


def ubl_postal_code(party: Element) -> str | None:
    """Return a UBL party's post code (EN16931 BT-38 / BT-53).

    UBL carries it in ``cac:PostalAddress/cbc:PostalZone``, its own element, so
    this is a lookup rather than a parse of the address's free-text lines.
    """
    for address in find_all(party, "PostalAddress"):
        found = direct_child_text(address, "PostalZone")
        if found is not None and found:
            return found
    return None


def cii_postal_code(party: Element) -> str | None:
    """Return a CII party's post code (EN16931 BT-38 / BT-53).

    CII carries it in ``ram:PostalTradeAddress/ram:PostcodeCode``, again its own
    element beside the free-text address lines rather than inside them.
    """
    for address in find_all(party, "PostalTradeAddress"):
        found = direct_child_text(address, "PostcodeCode")
        if found is not None and found:
            return found
    return None


def cii_country_code(party: Element) -> str | None:
    """Return a CII party's stated country code (EN16931 BT-40 / BT-55).

    CII carries it in ``ram:PostalTradeAddress/ram:CountryID``, its own element
    beside the ``PostcodeCode`` :func:`cii_postal_code` already reads, and
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
    for address in find_all(party, "PostalTradeAddress"):
        found = direct_child_text(address, "CountryID")
        if found is not None and found:
            return found
    return None


def decimal(raw: str | None) -> Decimal | None:
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


def category_for(code: str | None, *, issued_on: date | None) -> str | None:
    """Map a stated UNTDID 5305 tax-category code onto an IvaCategory value.

    Returns ``None`` when the document states no code, states no issue date to
    read the category vocabulary on, or states a code that maps to no special
    category. Never guesses.
    """
    if not (code is not None and code) or issued_on is None:
        return None
    return resolve_iva_category_catalogue(effective_date=issued_on).category_for_untdid_code(code.strip().upper())
