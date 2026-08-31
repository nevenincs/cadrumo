"""A structured document must be able to say which country each party is in.

The postal code answers only the sub-national half of the establishment
question, and it is consulted only where the country evidence positively named
Spain. So a reader that recovers postal codes and no country recovers a code
nothing is allowed to look at: the ladder's country rung has no source, the
postal rung it gates stays shut, and the most machine-readable documents in the
corpus resolve neither party's territory while a text-read document resolves
both.

That is not a hypothetical here. The bundled Facturae specimen states
``<CountryCode>ESP</CountryCode>`` inside the same ``AddressInSpain`` block whose
``PostCode`` the reader already reads -- the evidence sat one element away from a
value already being parsed.

**The alpha-3 trap is why this suite exists rather than a one-line read.**
Facturae states the country in ISO alpha-3 and every country surface in this
codebase is keyed alpha-2, so the obvious implementation reads ``ESP``, hands it
to a resolver that shape-checks for two letters, gets ``None`` back, and leaves
the postal rung shut -- with the evidence present, parsed, and establishing
nothing. Nothing about that failure is visible: it is indistinguishable from a
document that stated no country. So the cases below assert the TERRITORY that
comes out the far end of the ladder, never that the parser returned ``"ESP"``,
which would prove the parse and not the point.

Every case drives the REAL path: bytes are written through the real encrypted
evidence service and read back through
:func:`~application.ledger.invoice_draft_extraction.extract_invoice_draft_from_evidence`, the function the
CLI calls, and the territory is resolved through
:func:`~application.ledger.establishment_ladder.resolve_draft_counterparty_establishment`, the
function confirm calls. Nothing constructs a draft or calls a parser directly.

See Also:
    :func:`~domain.iva.country_code_for_stated_country_code`
        The lookup the two code systems both resolve through.
    :class:`~domain.iva.IvaTerritorialScope`
        The territory axis this evidence exists to establish.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.inbound.einvoice._parsers import parse_einvoice_document
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ....domain.iva.classification import InvoiceKind, IvaTerritorialScope
from ....domain.iva.establishment import country_code_for_stated_country_code, territorial_scope_for_country
from ..establishment_ladder import EstablishmentRung, resolve_draft_counterparty_establishment
from ..grounding_anchor import ground_structured_value
from ..invoice_draft_extraction import extract_invoice_draft_from_evidence
from ..invoice_draft_records import FieldProvenance, InvoiceDraft
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects"]

_CORPUS = Path(__file__).parent / "_evidence_corpus"

# The Facturae specimen states both parties' countries in full, in the alpha-3
# form the format uses. These are the values the document itself carries, not
# values chosen for the test.
_FACTURAE_WITH_ADDRESSES = "facturae_32_series_and_parties_invoice.xml"
_STATED_ALPHA3 = "ESP"
_PRINTED_SUPPLIER_CODE = "08009"  # <PostCode>08009 -- Barcelona, mainland
_PRINTED_CUSTOMER_CODE = "45007"  # <PostCode>45007 -- Toledo, mainland

# The recargo specimen carries no address block at all, so it is the in-corpus
# case for "the document states no country".
_FACTURAE_WITHOUT_ADDRESSES = "facturae_32_recargo_invoice.xml"

_UBL_INVOICE = "en16931_ubl_two_rate_invoice.xml"

# EN16931 carries the country in cac:PostalAddress/cac:Country/
# cbc:IdentificationCode (BT-40 / BT-55), beside the PostalZone. The corpus UBL
# specimens state no address, so the block is injected into a copy in tmp_path --
# the same technique the sibling postal-code suite uses, and the corpus tree is
# never written to.
_UBL_SUPPLIER_ADDRESS = (
    "<cac:PostalAddress><cbc:PostalZone>35001</cbc:PostalZone>"
    "<cac:Country><cbc:IdentificationCode>ES</cbc:IdentificationCode></cac:Country></cac:PostalAddress>"
)
_UBL_CUSTOMER_ADDRESS = (
    "<cac:PostalAddress><cbc:PostalZone>28001</cbc:PostalZone>"
    "<cac:Country><cbc:IdentificationCode>ES</cbc:IdentificationCode></cac:Country></cac:PostalAddress>"
)

# A Canarian code, deliberately. Reading it as the mainland is the exact failure
# the resolver's asymmetry exists to prevent, and it is also the answer no
# default could produce: a rung that returned a constant would return the
# peninsula here.
_CANARIAS_CODE = "35001"

# The CII specimen states both parties' countries in its own element,
# ram:PostalTradeAddress/ram:CountryID, in alpha-2 as UBL does. Unlike either
# neighbouring format's specimen it needs no injected address block: the
# document prints the whole thing, so these cases read the corpus file
# unmodified.
_CII_INVOICE = "en16931_cii_export_third_country_invoice.xml"

# The two parties are in DIFFERENT countries, and that asymmetry is the test.
# A reader resolving one party's element twice returns ES on both sides, which
# every same-country fixture in this module would accept.
_CII_SUPPLIER_COUNTRY = "ES"  # <ram:CountryID>ES -- Valencia
_CII_CUSTOMER_COUNTRY = "CH"  # <ram:CountryID>CH -- Zuerich, outside the Community
_CII_SUPPLIER_POSTAL = "46015"  # <ram:PostcodeCode>46015 -- Valencia, mainland


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


def _ubl_with_addresses(xml: str) -> str:
    """Return the UBL specimen with a full address block on each party."""
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
    # whose markup drifted fails as a broken fixture rather than as a reader that
    # recovered nothing.
    assert xml.count("<cbc:IdentificationCode>") == 2
    return xml


class TestTheCountryReachesTheDraft:
    """The country each party states arrives in the one code system, from either format."""

    def test_a_facturae_document_carries_both_parties_countries_as_alpha2(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The stated alpha-3 arrives as alpha-2, which is the whole correspondence.

        Asserted as ``ES`` rather than as ``ESP`` deliberately: the document
        states ``ESP`` and a draft carrying that string back would satisfy a test
        named for reading the element while establishing no country at all.
        """
        evidence_id = _stored(
            _corpus(_FACTURAE_WITH_ADDRESSES),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_countries.xml",
        )

        draft = _draft(evidence_id, isolated_settings)

        assert _STATED_ALPHA3 in _corpus(_FACTURAE_WITH_ADDRESSES)
        assert draft.supplier_country_code == "ES"
        assert draft.customer_country_code == "ES"

    def test_a_ubl_document_carries_both_parties_countries(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """UBL states the alpha-2 form already, and it arrives unchanged."""
        evidence_id = _stored(
            _ubl_with_addresses(_corpus(_UBL_INVOICE)),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="ubl_countries.xml",
        )

        draft = _draft(evidence_id, isolated_settings)

        assert draft.supplier_country_code == "ES"
        assert draft.customer_country_code == "ES"

    def test_a_cii_document_carries_each_partys_own_country(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The third syntax reaches the draft, and the two parties do not collapse.

        CII was the format left behind: it read each party's postal code and no
        country at all, so the country rung had no source from a Cross Industry
        Invoice and the postal rung that country gates stayed shut. A syntax
        this codebase classifies, parses field by field and routes to the exact
        reader established neither party's territory.

        The two countries deliberately differ. Every other case in this class
        asserts ``ES`` on both sides, which a reader that resolved the seller's
        element twice would satisfy; here that reader returns ``ES`` for a Swiss
        customer and fails.
        """
        evidence_id = _stored(
            _corpus(_CII_INVOICE),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="cii_countries.xml",
        )

        draft = _draft(evidence_id, isolated_settings)

        assert draft.supplier_country_code == _CII_SUPPLIER_COUNTRY
        assert draft.customer_country_code == _CII_CUSTOMER_COUNTRY

    def test_a_cii_country_comes_from_the_address_and_never_the_tax_registration(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """Where a party is REGISTERED is not where it is ESTABLISHED, and only one is read.

        On the corpus specimen the two agree -- ``CHE116281277`` beside
        ``CountryID`` ``CH`` -- as they do on realistic data generally, so that
        document cannot tell an address read from an IVA-prefix read. Which
        means the claim that the country is scoped to the address block is
        untested exactly where it matters and would stay untested however many
        realistic fixtures were added.

        So the divergence is constructed: the same Swiss-established buyer,
        carrying a German IVA registration. That is an ordinary arrangement --
        a company registers for IVA wherever it must account for tax, which is
        routinely not where it sits -- and it is the case that separates the two
        readers. A prefix reader answers ``DE`` and settles an EU member; the
        address reader answers ``CH`` and settles a third country. The rung
        that follows is the difference between a domestic-Community treatment
        and an export.

        The corpus tree is never written to; the edit lands in a tmp copy.
        """
        xml = _corpus(_CII_INVOICE).replace(
            '<ram:ID schemeID="VA">CHE116281277</ram:ID>',
            '<ram:ID schemeID="VA">DE811569869</ram:ID>',
            1,
        )
        # A replace that matched nothing yields the untouched document, which
        # passes the address assertion for the wrong reason.
        assert "DE811569869" in xml, "the fixture edit did not apply"
        assert "CHE116281277" not in xml

        evidence_id = _stored(
            xml,
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="cii_registered_elsewhere.xml",
        )

        draft = _draft(evidence_id, isolated_settings)

        assert draft.customer_country_code == "CH", "the ADDRESS country, never the IVA prefix"
        assert draft.customer_tax_id == "DE811569869", "the registration is still read, just not as a place"

    def test_a_document_stating_no_country_carries_none(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """Absent stays absent, and above all never becomes Spain.

        The safety asymmetry, at the field this suite adds: a country nothing
        stated must not acquire one on the way to the draft, because the
        peninsula is the majority population and a domestic default would pass
        every case above while placing foreign parties inside the territorio de
        aplicación del impuesto.
        """
        evidence_id = _stored(
            _corpus(_FACTURAE_WITHOUT_ADDRESSES),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_no_address.xml",
        )

        draft = _draft(evidence_id, isolated_settings)

        assert draft.supplier_country_code is None
        assert draft.customer_country_code is None


class TestTheStructuredPathOpensThePostalRung:
    """The load-bearing property: a structured document now resolves a territory.

    These cases run the whole chain -- document bytes, real evidence service,
    real draft extraction, real ladder -- and assert the TERRITORY. That is the
    only assertion that fails when the alpha-3 correspondence is wrong, missing,
    or bypassed, because every intermediate value is plausible without it.
    """

    def test_a_facturae_document_resolves_its_counterparty_territory(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """A Spanish national-format invoice reaches the postal rung end to end.

        Before the country element was read this returned no scope and no rung:
        the identifier is a Spanish one, which contributes nothing by design, and
        with no country evidence the postal rung stayed shut. The postal code it
        consults was already in the draft the whole time.
        """
        evidence_id = _stored(
            _corpus(_FACTURAE_WITH_ADDRESSES),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_ladder.xml",
        )

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=_draft(evidence_id, isolated_settings),
            kind=InvoiceKind.RECEIVED,
            repository=None,
        )

        assert resolved.scope is IvaTerritorialScope.ES_MAINLAND
        assert resolved.rung is EstablishmentRung.SPANISH_POSTAL_CODE

    def test_the_resolved_territory_follows_the_document_rather_than_a_constant(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The same document with a Canarian code resolves Canarias, not the peninsula.

        The mainland is what a rung answering from a default would return, so a
        case that only ever asserts the mainland cannot tell a working postal
        lookup from a constant. This is the same specimen with one printed code
        changed, so nothing but the postal rung's own reading can explain the
        different answer.
        """
        canarian = _corpus(_FACTURAE_WITH_ADDRESSES).replace(
            f"<PostCode>{_PRINTED_SUPPLIER_CODE}</PostCode>",
            f"<PostCode>{_CANARIAS_CODE}</PostCode>",
            1,
        )
        assert _CANARIAS_CODE in canarian

        evidence_id = _stored(
            canarian,
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_canarias.xml",
        )

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=_draft(evidence_id, isolated_settings),
            kind=InvoiceKind.RECEIVED,
            repository=None,
        )

        assert resolved.scope is IvaTerritorialScope.ES_CANARIAS
        assert resolved.rung is EstablishmentRung.SPANISH_POSTAL_CODE

    def test_a_ubl_document_resolves_its_counterparty_territory(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The alpha-2 leg reaches the same rung, so neither format is left behind."""
        evidence_id = _stored(
            _ubl_with_addresses(_corpus(_UBL_INVOICE)),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="ubl_ladder.xml",
        )

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=_draft(evidence_id, isolated_settings),
            kind=InvoiceKind.RECEIVED,
            repository=None,
        )

        assert resolved.scope is IvaTerritorialScope.ES_CANARIAS
        assert resolved.rung is EstablishmentRung.SPANISH_POSTAL_CODE

    def test_the_customer_side_resolves_its_own_country(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """Direction selects which party's country is read, or the rung answers the wrong one.

        The two UBL parties sit in different Spanish territories, so a side
        selection that reached for the supplier's block would return Canarias
        here instead of the peninsula.
        """
        evidence_id = _stored(
            _ubl_with_addresses(_corpus(_UBL_INVOICE)),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="ubl_customer_side.xml",
        )

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=_draft(evidence_id, isolated_settings),
            kind=InvoiceKind.ISSUED,
            repository=None,
        )

        assert resolved.scope is IvaTerritorialScope.ES_MAINLAND
        assert resolved.rung is EstablishmentRung.SPANISH_POSTAL_CODE

    def test_a_cii_document_resolves_a_spanish_counterparty_through_the_postal_rung(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The received side reads the Spanish supplier, so country GATES postal and both fire.

        This is the whole chain the missing country read broke. The postal code
        was always recoverable from a CII document; it establishes nothing until
        the country evidence positively names Spain, so before the country
        element was read this document resolved no territory while carrying
        every value needed to.
        """
        evidence_id = _stored(
            _corpus(_CII_INVOICE),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="cii_ladder_received.xml",
        )

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=_draft(evidence_id, isolated_settings),
            kind=InvoiceKind.RECEIVED,
            repository=None,
        )

        assert resolved.scope is IvaTerritorialScope.ES_MAINLAND
        assert resolved.rung is EstablishmentRung.SPANISH_POSTAL_CODE

    def test_a_cii_document_resolves_a_foreign_counterparty_through_the_country_rung(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The issued side reads the Swiss customer, whose country settles it alone.

        The complementary direction, and the one that proves the side selection
        rather than the read: the same document resolves the mainland one way
        round and a third country the other. A rung reaching for the wrong
        party's block returns Spain here, which is the under-declaration
        direction -- a domestic treatment for an export.
        """
        evidence_id = _stored(
            _corpus(_CII_INVOICE),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="cii_ladder_issued.xml",
        )

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=_draft(evidence_id, isolated_settings),
            kind=InvoiceKind.ISSUED,
            repository=None,
        )

        assert resolved.scope is IvaTerritorialScope.THIRD_COUNTRY
        assert resolved.rung is EstablishmentRung.ADDRESS_COUNTRY

    def test_a_document_stating_no_country_still_exhausts(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The rung opens on stated evidence only, never on the format.

        A Facturae document is a Spanish national format, which is exactly the
        inference that must NOT be made: the country has to be stated. This
        specimen states none, so the ladder exhausts and the operator is asked
        once, which is the honest outcome.
        """
        evidence_id = _stored(
            _corpus(_FACTURAE_WITHOUT_ADDRESSES),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_exhausts.xml",
        )

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=_draft(evidence_id, isolated_settings),
            kind=InvoiceKind.RECEIVED,
            repository=None,
        )

        assert resolved.scope is None
        assert resolved.rung is None


class TestTheOverseasAddressIsNotConsulted:
    """The one Facturae address block this reader deliberately does not read.

    Facturae states a party's address in one of two mutually exclusive blocks:
    ``AddressInSpain`` for a party established here, ``OverseasAddress`` for one
    established abroad. The reader consults only the first, and the reasoning is
    sound -- a party established abroad has no Spanish IVA territory to resolve,
    and the overseas block states its code jointly with the town
    (``PostCodeAndTown``), which is a composite this reader is forbidden to split
    because splitting it would be an inference rather than a read.

    **The reasoning was sound and untested, which is the gap this closes.** It
    lived in a docstring one line from the walk it justifies, and a reader who
    does not open that file sees only a country element the parser ignores. The
    consequence is live rather than theoretical: a foreign-established
    counterparty states its country in that block, so the ladder exhausts on a
    document that plainly names France.

    **These assert a GAP, not a contract.** They are expected to fail the day the
    overseas block is read, and that failure is the notification. Replace them
    with gates asserting the rung now fires; never relax them.
    """

    @staticmethod
    def _overseas(xml: str) -> str:
        """Return the specimen with the seller established in France instead.

        Built by replacing the seller's whole address block, so the document
        stays a well-formed Facturae record stating one address in one place --
        the shape a real foreign-issuer invoice has, rather than a document
        carrying both blocks, which the schema does not permit.
        """
        spanish = (
            "<AddressInSpain>\n"
            "          <Address>Carrer de Girona 88</Address>\n"
            "          <PostCode>08009</PostCode>\n"
            "          <Town>Barcelona</Town>\n"
            "          <Province>Barcelona</Province>\n"
            "          <CountryCode>ESP</CountryCode>\n"
            "        </AddressInSpain>"
        )
        overseas = (
            "<OverseasAddress>\n"
            "          <Address>12 Rue de Rivoli</Address>\n"
            "          <PostCodeAndTown>75001 Paris</PostCodeAndTown>\n"
            "          <Province>Ile-de-France</Province>\n"
            "          <CountryCode>FRA</CountryCode>\n"
            "        </OverseasAddress>"
        )
        assert xml.count(spanish) == 1, "the specimen's seller address block has drifted"
        return xml.replace(spanish, overseas, 1)

    def test_asserted_gap_the_overseas_block_states_a_country_the_reader_skips(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The document states France and the draft carries no country at all."""
        document = self._overseas(_corpus(_FACTURAE_WITH_ADDRESSES))
        assert "<CountryCode>FRA</CountryCode>" in document

        evidence_id = _stored(
            document,
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_overseas.xml",
        )

        draft = _draft(evidence_id, isolated_settings)

        assert draft.supplier_country_code is None
        # The postal side is skipped by the same scoping, asserted together so a
        # future widening of one walk without the other is visible here.
        assert draft.supplier_postal_code is None
        # The customer keeps its Spanish block, so this is a statement about the
        # BLOCK and not about the document having become unreadable.
        assert draft.customer_country_code == "ES"

    def test_asserted_gap_a_foreign_established_counterparty_exhausts_the_ladder(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The live consequence: France is stated, and no territory is resolved.

        The identifier rung cannot rescue it -- the specimen's seller carries a
        Spanish fiscal identifier, which contributes nothing to establishment by
        design -- so the country the document actually states is the only
        evidence available, and it is in the block the reader does not open.
        """
        evidence_id = _stored(
            self._overseas(_corpus(_FACTURAE_WITH_ADDRESSES)),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_overseas_ladder.xml",
        )

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=_draft(evidence_id, isolated_settings),
            kind=InvoiceKind.RECEIVED,
            repository=None,
        )

        assert resolved.scope is None
        assert resolved.rung is None
        # And the answer the ladder WOULD give from that country, so this reads
        # as a statement about unread evidence rather than about France being
        # unresolvable.
        assert territorial_scope_for_country("FR") is IvaTerritorialScope.EU_MEMBER


class TestTheProvenanceTellsTheTwoApart:
    """A stated code and a resolved one both ground, and the ANCHOR is what differs.

    The distinction that matters to an operator is not whether the country was
    checkable -- it was, in both formats, because both state a country element --
    but which string the document actually carries. So the envelope's anchor
    holds the record's own form, ``ESP`` for Facturae and ``ES`` for UBL, while
    the draft carries the resolved alpha-2 in both cases. That is the same
    relation the printed lanes already use, where ``"1.234,56 EUR"`` anchors the
    value ``1234.56``.

    **A grounding-outcome assertion could not carry this, and the reason is worth
    recording.** Grounding the resolved ``ES`` against a Facturae record returns
    ANCHORED rather than UNANCHORED, because the anchor search is boundary-aware
    only at NUMERIC edges: ``ES`` is an ordinary substring of ``ESP`` and matches
    it. So a test asserting UNANCHORED for the derived value would have been
    asserting a distinction the mechanism does not draw, and an implementation
    grounding the resolved form would pass on an accidental substring hit while
    pointing the operator at nothing.
    """

    @staticmethod
    def _envelope(draft: InvoiceDraft, field: str) -> FieldProvenance:
        envelopes = [envelope for envelope in draft.provenance if envelope.field == field]
        assert len(envelopes) == 1, f"expected exactly one envelope for {field}, got {len(envelopes)}"
        return envelopes[0]

    def test_a_facturae_country_anchors_to_the_alpha3_the_document_states(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The anchor is ``ESP`` while the value is ``ES``, which is the lookup made visible."""
        evidence_id = _stored(
            _corpus(_FACTURAE_WITH_ADDRESSES),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_provenance.xml",
        )

        envelope = self._envelope(_draft(evidence_id, isolated_settings), "supplier_country_code")

        assert envelope.anchor == _STATED_ALPHA3
        assert envelope.grounding is FieldGroundingOutcome.ANCHORED
        assert envelope.origin is FieldOrigin.EXACT_STRUCTURED

    def test_a_ubl_country_anchors_to_the_alpha2_the_document_states(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """UBL states the target form itself, so anchor and value coincide honestly."""
        evidence_id = _stored(
            _ubl_with_addresses(_corpus(_UBL_INVOICE)),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="ubl_provenance.xml",
        )

        envelope = self._envelope(_draft(evidence_id, isolated_settings), "supplier_country_code")

        assert envelope.anchor == "ES"
        assert envelope.grounding is FieldGroundingOutcome.ANCHORED

    def test_a_cii_country_anchors_to_the_alpha2_the_document_states(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The customer side, whose anchor no other party's element could supply.

        Taken from the CUSTOMER rather than the supplier on purpose. A supplier
        assertion here would read ``ES``, a string this document states in
        several places including the seller's IVA prefix, so an envelope
        pointing anywhere would anchor. ``CH`` occurs in the buyer's country
        element and in its IVA id and nowhere else, so the anchor has to come
        from that party's own block.
        """
        evidence_id = _stored(
            _corpus(_CII_INVOICE),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="cii_provenance.xml",
        )

        envelope = self._envelope(_draft(evidence_id, isolated_settings), "customer_country_code")

        assert envelope.anchor == _CII_CUSTOMER_COUNTRY
        assert envelope.grounding is FieldGroundingOutcome.ANCHORED
        assert envelope.origin is FieldOrigin.EXACT_STRUCTURED

    def test_a_country_the_record_does_not_state_gets_no_envelope(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """An absent field has nothing to describe, so it must not acquire an origin.

        An envelope here would assert a reading of a value that was never there,
        which is provenance about nothing.
        """
        evidence_id = _stored(
            _corpus(_FACTURAE_WITHOUT_ADDRESSES),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_no_envelope.xml",
        )

        draft = _draft(evidence_id, isolated_settings)

        assert not [envelope for envelope in draft.provenance if envelope.field.endswith("_country_code")]

    def test_a_value_the_anchor_does_not_derive_to_is_contradicted(self) -> None:
        """An explicit anchor checks the value; it does not merely accompany it.

        The anchor occurring in the record is a fact about the ANCHOR. Once the
        value stopped being its own anchor, nothing tied the two together, and
        the envelope would have asserted that a document stating ``ESP``
        evidences a country it never mentions. The derivation is what closes
        that, and it is the textual counterpart of the decimal re-parse the
        printed lanes already run.
        """
        contradicted = ground_structured_value(
            field="supplier_country_code",
            value="ZW",
            anchor=_STATED_ALPHA3,
            derive=country_code_for_stated_country_code,
            element_path="SellerParty/AddressInSpain/CountryCode",
            source_text=_STATED_ALPHA3,
        )

        assert contradicted.grounding is FieldGroundingOutcome.CONTRADICTED

    def test_an_explicit_anchor_without_a_derivation_is_refused(self) -> None:
        """The unverifiable pair cannot be expressed, rather than being caught later.

        A caller contract rather than a document condition, so it raises: an
        envelope says what the document says, and "the caller supplied a pair
        nothing checks" is not one of the things it can say.
        """
        with pytest.raises(ValueError, match="derivation"):
            ground_structured_value(
                field="supplier_country_code",
                value="ES",
                anchor=_STATED_ALPHA3,
                element_path="SellerParty/AddressInSpain/CountryCode",
                source_text=_STATED_ALPHA3,
            )

    def test_markup_cannot_ground_a_country_the_record_does_not_state(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """A tag name is not something the document states.

        The anchor search once ran over the whole decoded file, so a
        two-character value could match markup: ``ID`` is Indonesia and it occurs
        in ``<cbc:ID>``, which meant a record carrying no country element at all
        grounded one. The check claimed to catch a reader pointing at an element
        the document does not have, and for short codes it certified the schema
        instead. Asserted against the real specimen, which genuinely states no
        country.
        """
        assert "IdentificationCode" not in _corpus(_UBL_INVOICE)
        evidence_id = _stored(
            _corpus(_UBL_INVOICE),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="ubl_no_country.xml",
        )

        draft = _draft(evidence_id, isolated_settings)

        assert draft.supplier_country_code is None
        assert not [envelope for envelope in draft.provenance if envelope.field.endswith("_country_code")]

        # The haystack itself, so the property is stated where it is enforced
        # rather than inferred from the absence above.
        parsed = parse_einvoice_document(_corpus(_UBL_INVOICE).encode("utf-8"))
        assert "<" not in parsed.record_text
        grounded = ground_structured_value(
            field="supplier_country_code",
            value="ID",
            element_path="p",
            source_text=parsed.record_text,
        )
        assert grounded.grounding is FieldGroundingOutcome.UNANCHORED

    def test_an_assembled_name_still_does_not_anchor_as_verbatim(self) -> None:
        """Narrowing the haystack must not merge adjacent element values.

        A Facturae party name is composed from three sibling elements, and the
        composed string is not printed anywhere in the record. Joining the text
        nodes on whitespace would make it appear, because the anchor search
        collapses whitespace runs before matching -- so an assembled value would
        anchor as though the document stated it. That refusal was a property of
        the raw-file haystack and is easy to drop silently when narrowing it.
        """
        parsed = parse_einvoice_document(_corpus(_FACTURAE_WITH_ADDRESSES).encode("utf-8"))

        assert parsed.supplier_name == "Marta Iglesias Ferrer"
        assert parsed.supplier_name not in parsed.record_text
        # Each part IS stated, so this is a statement about the join and not
        # about the parts being absent.
        for part in ("Marta", "Iglesias", "Ferrer"):
            assert part in parsed.record_text

    def test_the_envelope_names_the_element_it_was_read_from(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """An operator gets a location they can navigate to, not the shape's name."""
        evidence_id = _stored(
            _corpus(_FACTURAE_WITH_ADDRESSES),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_note.xml",
        )

        envelope = self._envelope(_draft(evidence_id, isolated_settings), "supplier_country_code")

        assert "SellerParty/AddressInSpain/CountryCode" in envelope.note

    def test_the_cii_envelope_names_the_cii_element_rather_than_the_shape(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """A syntax the path table does not cover degrades to naming the shape.

        That fallback is silent and reads as a location -- "the xml_cii record's
        supplier_country_code" is a sentence, not somewhere an operator can
        navigate to -- so a newly-read field whose element path was never added
        looks documented while pointing at nothing. Asserting the element
        outright is what makes the omission fail rather than degrade.
        """
        evidence_id = _stored(
            _corpus(_CII_INVOICE),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="cii_note.xml",
        )

        draft = _draft(evidence_id, isolated_settings)

        assert (
            "ram:SellerTradeParty/ram:PostalTradeAddress/ram:CountryID"
            in self._envelope(
                draft,
                "supplier_country_code",
            ).note
        )
        assert (
            "ram:BuyerTradeParty/ram:PostalTradeAddress/ram:CountryID"
            in self._envelope(
                draft,
                "customer_country_code",
            ).note
        )
