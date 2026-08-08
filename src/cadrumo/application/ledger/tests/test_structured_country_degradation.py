"""A structured document stating a country we cannot place must not read as silence.

The resolved country field is contracted alpha-2 and is populated only through
the bundled vocabulary, so a token that vocabulary does not carry leaves it
empty -- and empty is exactly what a document with no address block leaves. Two
different documents, one indistinguishable draft: no value, no provenance
envelope, and the country advisory reading the empty field and returning nothing.
Every channel silent, on the reading path that handles the most reliable country
evidence in the system.

**Thailand is why this is not a curiosity.** ``TH`` is not a third country this
codebase declines to place for a stated reason -- the vocabulary simply omits it.
So a genuine Thai export arrives with no country at all, its territory
unresolved, and nothing anywhere tells the operator that the document did state
one. "Unresolved" is not the complement of "third country", and here a real third
country was being erased quietly.

**Both spellings, because only one route reaches both.** Facturae -- the Spanish
national format, and so the format most of this corpus arrives in -- states the
country in alpha-3, and :func:`~domain.iva.stated_country_code_status` answers
only about alpha-2. A fix carried solely by that authority closes ``XX`` and
leaves ``THA`` exactly as silent as before, which is why the cases below run the
two separately rather than parametrising them into one.

**And the opposite direction, or the fix only moves the confusion.** A document
that genuinely states no country must still produce no stated value, no country
envelope and no advisory. A change that made everything speak would satisfy every
positive case here while destroying the distinction they exist to establish.

Every case drives the REAL path: bytes through the real encrypted evidence
service, read back through
:func:`~application.ledger.extract_invoice_draft_from_evidence` -- the function
the CLI calls -- and reported through
:func:`~application.ledger.country_vocabulary_advisory`, the authority the review
surface projects its notices from. Nothing constructs a draft by hand, because a
hand-set country field proves the selector and not that any document can reach
it.

See Also:
    :func:`~application.ledger.country_vocabulary_advisory`
        The non-blocking channel an unplaceable code reaches the operator on.
    :class:`~application.ledger.FieldProvenance`
        The envelope that records what the record stated, value or none.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import FieldGroundingOutcome, FieldOrigin
from ....core.config import Settings
from ....domain.iva import InvoiceKind, IvaTerritorialScope, StatedCountryCodeStatus
from .._country_vocabulary_advisory import country_vocabulary_advisory
from .._establishment_ladder import resolve_draft_counterparty_establishment
from .._evidence_draft import InvoiceDraft, extract_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import isolated_settings as isolated_settings
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import secure_objects as secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects"]

_CORPUS = Path(__file__).parent / "_evidence_corpus"

#: The specimen carrying a full address block on each party, both stating ``ESP``.
_WITH_ADDRESSES: Final = "facturae_32_series_and_parties_invoice.xml"

#: The specimen carrying no address block at all -- the in-corpus case for "the
#: document states no country", and the control every positive case needs.
_WITHOUT_ADDRESSES: Final = "facturae_32_recargo_invoice.xml"

_CATALOGUED_ALPHA3: Final = "ESP"

#: Thailand in the spelling Facturae uses. Alpha-3, uncatalogued, and the case
#: the alpha-2 status authority structurally cannot classify.
_UNCATALOGUED_ALPHA3: Final = "THA"

#: An ISO user-assigned alpha-2 pair: reserved to name no country at all, so the
#: document is wrong and the operator fixes it off the page.
_UNASSIGNED_ALPHA2: Final = "XX"

#: Thailand in alpha-2. Well-formed, assigned by ISO, and absent from the bundled
#: vocabulary -- our catalogue gap rather than the issuer's mistake.
_UNCATALOGUED_ALPHA2: Final = "TH"


def _corpus(name: str) -> str:
    return (_CORPUS / name).read_text(encoding="utf-8")


def _stating(code: str) -> str:
    """Return the addressed specimen with the SELLER's country replaced by *code*.

    Only the seller's element is rewritten, so the buyer keeps ``ESP`` on every
    case below. That asymmetry is load-bearing: a reader that resolved one
    party's element twice, or an advisory that reported the document rather than
    the party, would be satisfied by a specimen whose two sides agree.
    """
    seller = f"<CountryCode>{_CATALOGUED_ALPHA3}</CountryCode>"
    assert _corpus(_WITH_ADDRESSES).count(seller) == 2, "the specimen's address blocks have drifted"
    replaced = _corpus(_WITH_ADDRESSES).replace(seller, f"<CountryCode>{code}</CountryCode>", 1)
    # A replace that matched nothing yields the untouched document, which passes
    # a "the buyer still resolves" assertion for entirely the wrong reason.
    assert f"<CountryCode>{code}</CountryCode>" in replaced
    return replaced


def _draft(
    xml: str,
    *,
    settings: Settings,
    objects: SecureObjectRepository,
    tmp_path: Path,
    name: str,
) -> InvoiceDraft:
    staged = tmp_path / name
    staged.write_text(xml, encoding="utf-8")
    evidence_id = _make_svc(settings, objects).add(bucket_id=_BUCKET_ID, source_path=staged).record.evidence_id
    return extract_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        evidence_id=evidence_id,
        settings=settings,
    )


def _country_envelopes(draft: InvoiceDraft, field: str) -> list[str]:
    return [envelope.field for envelope in draft.provenance if envelope.field == field]


class TestTheRecordsOwnTokenSurvivesTheLookup:
    """What the document stated is carried, whether or not it could be placed."""

    def test_an_uncatalogued_alpha3_reaches_the_draft_verbatim(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """``THA`` arrives as ``THA``, beside a resolved field that stays empty.

        Both halves asserted together. The empty resolved field is the contract
        the alpha-2 typing owes -- putting ``THA`` there would trade a silent
        absence for a silent lie -- and the populated stated field is the whole
        distinction, so a change that satisfied either alone would be wrong.
        """
        draft = _draft(
            _stating(_UNCATALOGUED_ALPHA3),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_tha.xml",
        )

        assert draft.supplier_stated_country_code == _UNCATALOGUED_ALPHA3
        assert draft.supplier_country_code is None
        # The buyer is untouched, so this reads as a statement about the seller's
        # element and not about the document having become unreadable.
        assert draft.customer_stated_country_code == _CATALOGUED_ALPHA3
        assert draft.customer_country_code == "ES"

    def test_an_unassigned_alpha2_reaches_the_draft_verbatim(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The other spelling, on the other kind of failure."""
        draft = _draft(
            _stating(_UNASSIGNED_ALPHA2),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_xx.xml",
        )

        assert draft.supplier_stated_country_code == _UNASSIGNED_ALPHA2
        assert draft.supplier_country_code is None

    def test_a_catalogued_code_carries_both_the_stated_and_the_resolved_form(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The control. A document we CAN place must still say what it said.

        Without this the stated field could be populated only on the failure
        path, which would make its presence itself the signal and put the
        distinction back into an absence.
        """
        draft = _draft(
            _corpus(_WITH_ADDRESSES),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_esp.xml",
        )

        assert draft.supplier_stated_country_code == _CATALOGUED_ALPHA3
        assert draft.supplier_country_code == "ES"

    def test_a_document_stating_no_country_carries_no_stated_token(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The opposite direction: absent stays absent on the new field too.

        A fix that made every document carry something would satisfy every case
        above while destroying the distinction they exist to establish.
        """
        draft = _draft(
            _corpus(_WITHOUT_ADDRESSES),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_silent.xml",
        )

        assert draft.supplier_stated_country_code is None
        assert draft.customer_stated_country_code is None
        assert draft.supplier_country_code is None


class TestTheProvenanceRecordsTheUnplaceableToken:
    """An unplaceable country produces an envelope; an absent one produces none."""

    def test_the_unplaceable_token_earns_an_envelope_naming_its_element(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The record stated it, so it is grounded exactly like any copied value.

        ANCHORED rather than degraded, and that is honest: the token really does
        occur in the record's own text. What did not happen is the LOOKUP, and
        the empty resolved field beside it is what says so.
        """
        draft = _draft(
            _stating(_UNCATALOGUED_ALPHA3),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_tha_envelope.xml",
        )

        envelopes = [e for e in draft.provenance if e.field == "supplier_stated_country_code"]

        assert len(envelopes) == 1
        assert envelopes[0].anchor == _UNCATALOGUED_ALPHA3
        assert envelopes[0].grounding is FieldGroundingOutcome.ANCHORED
        assert envelopes[0].origin is FieldOrigin.EXACT_STRUCTURED
        assert "SellerParty/AddressInSpain/CountryCode" in envelopes[0].note
        # And the resolved field has nothing to describe, so it gets nothing.
        assert _country_envelopes(draft, "supplier_country_code") == []

    def test_a_document_stating_no_country_earns_no_country_envelope(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """Provenance about nothing is what the envelope rule forbids.

        The negative half of the case above, and the one that makes the pair a
        distinction rather than a pair of independent facts.
        """
        draft = _draft(
            _corpus(_WITHOUT_ADDRESSES),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_silent_envelope.xml",
        )

        assert [e for e in draft.provenance if e.field.endswith("_country_code")] == []


class TestTheOperatorIsTold:
    """The advisory fires from a real document, in both spellings, and stays quiet otherwise."""

    def test_an_uncatalogued_alpha3_raises_the_catalogue_gap_advisory(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The urgent case, end to end from document bytes.

        The kind matters as much as the firing: reported as a typo, the operator
        re-reads a Thai invoice that reads perfectly. It is our vocabulary that
        is short, and the sentence has to say so.
        """
        draft = _draft(
            _stating(_UNCATALOGUED_ALPHA3),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_tha_advisory.xml",
        )

        advisory = country_vocabulary_advisory(draft)

        assert advisory is not None
        assert advisory.fields == ("supplier_stated_country_code",)
        warning = advisory.parties[0]
        assert warning.status is StatedCountryCodeStatus.UNCATALOGUED
        assert warning.stated_code == _UNCATALOGUED_ALPHA3
        assert repr(_UNCATALOGUED_ALPHA3) in warning.detail
        assert warning.role == "issuing"

    def test_an_uncatalogued_alpha2_raises_the_same_kind(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """Thailand in the other spelling reaches the same sentence.

        A document may state either form and the operator's fix is identical, so
        a route that reached only one of them would leave the population it
        missed exactly as silent as before.
        """
        draft = _draft(
            _stating(_UNCATALOGUED_ALPHA2),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_th_advisory.xml",
        )

        advisory = country_vocabulary_advisory(draft)

        assert advisory is not None
        assert advisory.parties[0].status is StatedCountryCodeStatus.UNCATALOGUED
        assert advisory.parties[0].stated_code == _UNCATALOGUED_ALPHA2

    def test_an_unassigned_alpha2_raises_the_typo_advisory_instead(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The two kinds stay apart on the real path, not only on hand-built drafts."""
        draft = _draft(
            _stating(_UNASSIGNED_ALPHA2),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_xx_advisory.xml",
        )

        advisory = country_vocabulary_advisory(draft)

        assert advisory is not None
        assert advisory.parties[0].status is StatedCountryCodeStatus.UNASSIGNED
        assert advisory.by_status(StatedCountryCodeStatus.UNCATALOGUED) == ()

    def test_a_document_stating_no_country_raises_no_advisory(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """An honest absence must stay an absence, or the fix only moves the confusion.

        This is the assertion that makes the file a distinction. Every case above
        would pass against an advisory that fired on every document, and the
        operator would be no better off than with one that fired on none.
        """
        draft = _draft(
            _corpus(_WITHOUT_ADDRESSES),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_silent_advisory.xml",
        )

        assert country_vocabulary_advisory(draft) is None

    def test_a_catalogued_country_raises_no_advisory(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The negative control on the firing itself.

        The corpus specimen states ``ESP`` on both sides, which the vocabulary
        places. An advisory here would be noise on the majority population and
        would train the operator to clear the channel unread.
        """
        draft = _draft(
            _corpus(_WITH_ADDRESSES),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_esp_advisory.xml",
        )

        assert country_vocabulary_advisory(draft) is None


class TestTheTwoDocumentsAreNoLongerIdentical:
    """The row's whole claim, asserted as the comparison it is about."""

    def test_a_document_stating_an_unplaceable_country_differs_from_one_stating_none(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """Stated-something and stated-nothing must not project the same country surface.

        Asserted as a comparison rather than as two separate expectations,
        because the defect was never about either document on its own: each was
        individually plausible, and it was their EQUALITY that hid a Thai export.
        The seller's projection is compared field by field so the difference has
        to be in the country surface rather than anywhere else in the draft.
        """
        unplaceable = _draft(
            _stating(_UNCATALOGUED_ALPHA3),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_compare_tha.xml",
        )
        silent = _draft(
            _corpus(_WITHOUT_ADDRESSES),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_compare_silent.xml",
        )

        # The resolved field agrees on both, which is exactly the collapse: the
        # surface everything downstream is keyed by cannot tell them apart.
        assert unplaceable.supplier_country_code == silent.supplier_country_code is None
        # And every channel that now can.
        assert unplaceable.supplier_stated_country_code != silent.supplier_stated_country_code
        assert _country_envelopes(unplaceable, "supplier_stated_country_code") != _country_envelopes(
            silent,
            "supplier_stated_country_code",
        )
        assert (country_vocabulary_advisory(unplaceable) is None) != (country_vocabulary_advisory(silent) is None)

    def test_the_unplaceable_country_still_resolves_no_territory(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """Visibility is not placement, and must not have become it.

        Naming the token to the operator says nothing about where the party is,
        and a stated field that leaked into the ladder would settle a territory
        from a string the vocabulary has no referent for -- the exact
        shape-is-not-reference failure the country rung was narrowed to close.
        On the issued side a wrongly-settled third country is zero-rated export
        treatment, so the direction this guards is the one that costs money.
        """
        draft = _draft(
            _stating(_UNCATALOGUED_ALPHA3),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_tha_ladder.xml",
        )

        resolved = resolve_draft_counterparty_establishment(
            bucket_id=_BUCKET_ID,
            draft=draft,
            kind=InvoiceKind.RECEIVED,
            repository=None,
        )

        assert resolved.scope is None
        assert resolved.rung is None
        # The buyer's side still resolves from the same document, so this reads
        # as a refusal about the unplaceable token rather than a ladder that
        # stopped answering.
        assert (
            resolve_draft_counterparty_establishment(
                bucket_id=_BUCKET_ID,
                draft=draft,
                kind=InvoiceKind.ISSUED,
                repository=None,
            ).scope
            is IvaTerritorialScope.ES_MAINLAND
        )
