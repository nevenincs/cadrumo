"""A structured document must be able to establish where each party sits.

The postal code is the sub-national half of the establishment question: the
country code cannot separate Spain's three IVA territories, so a Spanish party's
territory is settled by its postal code or not at all. The exact reader exposed
no address at all, so a Facturae, CII or UBL document resolved NEITHER party's
territory while a text-read document resolved both.

That is the same inversion this path has produced before -- the most
machine-readable documents in the corpus getting the least out of the pipeline,
because the data is structured, present, and simply never read. The regime
legend had exactly this shape until its structured carry landed.

Every case drives the REAL path: bytes are written through the real encrypted
evidence service and read back through
:func:`~application.ledger.evidence_draft.extract_invoice_draft_from_evidence`, the function the
CLI calls. Nothing constructs a draft or calls a parser directly, because a unit
test on the parser passes whether or not the draft path ever reaches it.

The safety asymmetry is the point of half these cases: an absent or unreadable
code resolves to NOTHING, never to the mainland. The peninsula is the majority
population, so a mainland default would be invisible in testing while silently
placing Canarian and Ceutan parties in a territory their operations are not
subject to.

See Also:
    :func:`~domain.iva.territorial_scope_for_spanish_postal_code`
        The resolver these codes are read for.
    :class:`~domain.iva.IvaTerritorialScope`
        The territory axis a resolved code establishes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.iva.classification import IvaTerritorialScope
from ....domain.iva.establishment import territorial_scope_for_spanish_postal_code
from ..evidence_draft import InvoiceDraft, extract_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects"]

_CORPUS = Path(__file__).parent / "_evidence_corpus"

# The Facturae specimen states both parties' addresses in full. The codes below
# are the ones the document itself prints, not values chosen for the test.
_FACTURAE_WITH_ADDRESSES = "facturae_32_series_and_parties_invoice.xml"
_PRINTED_SUPPLIER_CODE = "08009"  # <PostCode>08009 -- Barcelona
_PRINTED_CUSTOMER_CODE = "45007"  # <PostCode>45007 -- Toledo

# The recargo specimen carries no address block at all, which makes it the
# natural in-corpus case for "the document does not say".
_FACTURAE_WITHOUT_ADDRESSES = "facturae_32_recargo_invoice.xml"

_UBL_INVOICE = "en16931_ubl_two_rate_invoice.xml"

# EN16931 maps the supplier's post code to BT-38 and the customer's to BT-53,
# carried in UBL as cac:PostalAddress/cbc:PostalZone. The corpus UBL specimens
# state no address, so the element is injected into a copy in tmp_path -- the
# same technique the sibling structured-path suite uses, and the corpus tree is
# never written to.
_UBL_SUPPLIER_ADDRESS = "<cac:PostalAddress><cbc:PostalZone>35001</cbc:PostalZone></cac:PostalAddress>"
_UBL_CUSTOMER_ADDRESS = "<cac:PostalAddress><cbc:PostalZone>28001</cbc:PostalZone></cac:PostalAddress>"

# A Canarian code, deliberately. Reading it as the mainland is the exact failure
# the resolver's asymmetry exists to prevent, and a document is where that code
# has to survive from.
_CANARIAS_CODE = "35001"

# No Cross Industry Invoice is bundled anywhere in the corpus, so this specimen
# is built from the EN16931 mapping (BT-38 / BT-53 to
# ram:PostalTradeAddress/ram:PostcodeCode) rather than taken from a real
# document. Stated plainly in the case that uses it: it establishes that the CII
# branch is reached and scoped correctly, not that a real-world CII invoice
# states its address this way.
_CII_SPECIMEN = """<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100">
  <rsm:ExchangedDocument><ram:ID>CII-2026-0001</ram:ID></rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>Vendedor Insular SL</ram:Name>
        <ram:PostalTradeAddress><ram:PostcodeCode>38001</ram:PostcodeCode></ram:PostalTradeAddress>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>Comprador Ceuti SL</ram:Name>
        <ram:PostalTradeAddress><ram:PostcodeCode>51001</ram:PostcodeCode></ram:PostalTradeAddress>
      </ram:BuyerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""


def _stored(
    xml: str,
    *,
    settings: Settings,
    objects: SecureObjectRepository,
    tmp_path: Path,
    name: str,
) -> str:
    staged = tmp_path / name
    staged.write_text(xml, encoding="utf-8")
    return _make_svc(settings, objects).add(bucket_id=_BUCKET_ID, source_path=staged).record.evidence_id


def _draft(evidence_id: str, settings: Settings) -> InvoiceDraft:
    return extract_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        evidence_id=evidence_id,
        settings=settings,
    )


def _corpus(name: str) -> str:
    return (_CORPUS / name).read_text(encoding="utf-8")


def test_a_facturae_document_carries_both_parties_postal_codes(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Both codes the document prints reach the draft, supplier and customer.

    Both sides, because the establishment question is asked of both: which party
    is the counterparty is not decided until confirm, so a reader that recovered
    only the supplier would leave the other side unresolvable on exactly half the
    invoices.
    """
    evidence_id = _stored(
        _corpus(_FACTURAE_WITH_ADDRESSES),
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="facturae.xml",
    )

    draft = _draft(evidence_id, isolated_settings)

    assert draft.supplier_postal_code == _PRINTED_SUPPLIER_CODE
    assert draft.customer_postal_code == _PRINTED_CUSTOMER_CODE


def test_a_facturae_document_with_no_address_resolves_to_nothing(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """A document that does not state an address must not imply the mainland.

    The safety asymmetry, proven at the reader rather than only at the resolver.
    A reader that defaulted here would hand the resolver a well-formed mainland
    code, and the resolver's own refusal would never get the chance to fire.
    """
    evidence_id = _stored(
        _corpus(_FACTURAE_WITHOUT_ADDRESSES),
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="facturae-no-address.xml",
    )

    draft = _draft(evidence_id, isolated_settings)

    assert draft.supplier_postal_code is None
    assert draft.customer_postal_code is None
    assert territorial_scope_for_spanish_postal_code(draft.supplier_postal_code) is None
    assert territorial_scope_for_spanish_postal_code(draft.customer_postal_code) is None


def test_a_canarian_code_survives_the_document_as_canarias(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The whole chain, document to territory, on the case that actually matters.

    Canarias is outside the TAI and its supplies are subject to IGIC rather than
    IVA. This is the case a mainland default would silently swallow, and it is
    the reason the code has to travel exactly rather than approximately.
    """
    xml = _corpus(_FACTURAE_WITH_ADDRESSES).replace(
        f"<PostCode>{_PRINTED_SUPPLIER_CODE}</PostCode>",
        f"<PostCode>{_CANARIAS_CODE}</PostCode>",
        1,
    )
    assert _CANARIAS_CODE in xml

    evidence_id = _stored(
        xml,
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="facturae-canarias.xml",
    )
    draft = _draft(evidence_id, isolated_settings)

    assert draft.supplier_postal_code == _CANARIAS_CODE
    assert territorial_scope_for_spanish_postal_code(draft.supplier_postal_code) is IvaTerritorialScope.ES_CANARIAS
    # The other party is untouched and must still read as the mainland, so the
    # case proves a territory was RESOLVED rather than that everything moved.
    assert territorial_scope_for_spanish_postal_code(draft.customer_postal_code) is IvaTerritorialScope.ES_MAINLAND


def test_a_ubl_document_carries_the_postal_zone(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """UBL states the code in its own element, so it is read directly.

    EN16931 BT-38 and BT-53 map to cac:PostalAddress/cbc:PostalZone. Reading that
    element is a lookup, not a parse of a composite address string -- which is
    the distinction that keeps this deterministic.
    """
    # Anchored on each party's OWN wrapper rather than on the shared
    # `<cac:Party>` tag: replacing that tag twice would put both addresses in the
    # supplier and leave the customer bare, and the test would still pass on a
    # reader that only ever looked at one side.
    xml = _corpus(_UBL_INVOICE)
    xml = xml.replace(
        "<cac:AccountingSupplierParty>\n    <cac:Party>",
        f"<cac:AccountingSupplierParty>\n    <cac:Party>{_UBL_SUPPLIER_ADDRESS}",
        1,
    )
    xml = xml.replace(
        "<cac:AccountingCustomerParty>\n    <cac:Party>",
        f"<cac:AccountingCustomerParty>\n    <cac:Party>{_UBL_CUSTOMER_ADDRESS}",
        1,
    )
    # Assert the document really took both edits before reading it, so a fixture
    # whose anchors silently failed to match cannot pass this vacuously. Counted
    # on the opening tag: the element name alone appears twice per block.
    assert xml.count("<cbc:PostalZone>") == 2

    evidence_id = _stored(
        xml,
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="ubl.xml",
    )
    draft = _draft(evidence_id, isolated_settings)

    assert draft.supplier_postal_code == "35001"
    assert draft.customer_postal_code == "28001"


def test_a_cii_document_carries_the_postcode_code(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """CII states the code in its own element too, and the branch is reached.

    The corpus bundles no Cross Industry Invoice at all -- only a malformed
    fragment used to prove the parser refuses one. So this specimen is
    hand-built from the EN16931 mapping rather than taken from a real document,
    which is a weaker footing than the Facturae and UBL cases: it proves the CII
    branch is reached and correctly scoped, and it cannot prove a real-world CII
    invoice states its address the way this one does.

    It is here rather than omitted because the alternative is a reader that
    exists and is never exercised, a recurring shape in this codebase. Both
    codes name excluded territories -- Santa Cruz de Tenerife
    and Ceuta -- so a reader that silently produced the mainland would fail.
    """
    evidence_id = _stored(
        _CII_SPECIMEN,
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="cii.xml",
    )

    draft = _draft(evidence_id, isolated_settings)

    assert draft.supplier_postal_code == "38001"
    assert draft.customer_postal_code == "51001"
    assert territorial_scope_for_spanish_postal_code(draft.supplier_postal_code) is IvaTerritorialScope.ES_CANARIAS
    assert territorial_scope_for_spanish_postal_code(draft.customer_postal_code) is IvaTerritorialScope.ES_CEUTA_MELILLA
