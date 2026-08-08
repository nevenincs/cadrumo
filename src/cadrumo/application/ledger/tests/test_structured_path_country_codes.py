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
:func:`~application.ledger.extract_invoice_draft_from_evidence`, the function the
CLI calls, and the territory is resolved through
:func:`~application.ledger.resolve_draft_counterparty_establishment`, the
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

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import FieldGroundingOutcome, FieldOrigin
from ....core.config import Settings
from ....domain.iva import InvoiceKind, IvaTerritorialScope
from .._establishment_ladder import EstablishmentRung, resolve_draft_counterparty_establishment
from .._evidence_draft import FieldProvenance, InvoiceDraft, extract_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import isolated_settings as isolated_settings
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import secure_objects as secure_objects

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
