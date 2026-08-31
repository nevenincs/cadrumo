"""A structured document stating a country we cannot place must not read as silence.

The resolved country field is contracted alpha-2 and is populated only through
the bundled vocabulary, so a token that vocabulary does not carry leaves it
empty -- and empty is exactly what a document with no address block leaves. Two
different documents, one indistinguishable draft: no value, no provenance
envelope, and the country advisory reading the empty field and returning nothing.
Every channel silent, on the reading path that handles the most reliable country
evidence in the system.

**A real third country is being erased quietly, and that is not a curiosity.**
A code the vocabulary does not carry is not a country this codebase declined to
place for a stated reason -- it is one nobody has enrolled yet. So a genuine
export to such a jurisdiction arrives with no country at all, its territory
unresolved, and nothing anywhere tells the operator the document stated one.
"Unresolved" is not the complement of "third country".

**Which country that is today is an accident, and the file no longer names one.**
The vocabulary is a bounded subset of the world's jurisdictions and it grows: any
particular omission is a row somebody has not written, and enrolling it fixes
that one document and none of the defect, because the next omission behaves
identically. The property under test is therefore "the vocabulary cannot place
this token", never the identity of whichever country satisfies that today -- so
the specimens are selected from the
vocabulary itself, and the anchor cases below assert the selection still carries
the property it was chosen for. A derived specimen with no anchor can quietly
come to name a country the vocabulary has since admitted, at which point these
cases would still pass and would be testing nothing.

**The reserved codes are the exception and ARE named.** The ISO 3166-1
user-assigned ranges are fixed by the standard, so no enrolment can turn one into
a country and pinning them costs nothing -- which is the whole difference between
a code that names no country by construction and one our data has not reached.

**Both spellings, because only one route reaches both.** Facturae -- the Spanish
national format, and so the format most of this corpus arrives in -- states the
country in alpha-3, and :func:`~domain.iva.stated_country_code_status` answers
only about alpha-2. A fix carried solely by that authority closes the alpha-2
half and leaves the alpha-3 half exactly as silent as before, which is why the
cases below run the two separately rather than parametrising them into one. The
same split runs through the reserved ranges, where the alpha-3 half was the one
left ungated.

**And the opposite direction, or the fix only moves the confusion.** A document
that genuinely states no country must still produce no stated value, no country
envelope and no advisory. A change that made everything speak would satisfy every
positive case here while destroying the distinction they exist to establish.

Every case drives the REAL path: bytes through the real encrypted evidence
service, read back through
:func:`~application.ledger.evidence_draft.extract_invoice_draft_from_evidence` -- the function
the CLI calls -- and reported through
:func:`~application.ledger.country_vocabulary_advisory`, the authority the review
surface projects its notices from. Nothing constructs a draft by hand, because a
hand-set country field proves the selector and not that any document can reach
it.

See Also:
    :func:`~application.ledger.country_vocabulary_advisory`
        The non-blocking channel an unplaceable code reaches the operator on.
    :class:`~application.ledger.evidence_draft.FieldProvenance`
        The envelope that records what the record stated, value or none.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import IvaCategoryOutcome
from ....core.classifier_input_source import ClassifierInputSource
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ....core.config import Settings
from ....domain.iva.classification import CustomerTaxStatus, InvoiceKind, IvaTerritorialScope
from ....domain.iva.establishment import StatedCountryCodeStatus, record_country_code_status
from ....domain.iva.schema import IvaCategory
from ....domain.iva.supply_nature import SupplyNature
from ....tests.country_vocabulary_specimens import an_uncatalogued_alpha2, an_uncatalogued_alpha3
from ..classification_assembly import (
    DeclaredFact,
    DeclaredFacts,
    assemble_classification_criteria,
    resolve_ingestion_iva_category,
)
from ..classifier_inputs import collect_classifier_inputs
from ..confirm_establishment import ConfirmedEstablishment, resolve_confirmed_establishment
from ..country_vocabulary_advisory import country_vocabulary_advisory
from ..establishment_ladder import resolve_draft_counterparty_establishment
from ..evidence_draft import InvoiceDraft, extract_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

_CORPUS = Path(__file__).parent / "_evidence_corpus"

#: The specimen carrying a full address block on each party, both stating ``ESP``.
_WITH_ADDRESSES: Final = "facturae_32_series_and_parties_invoice.xml"

#: The specimen carrying no address block at all -- the in-corpus case for "the
#: document states no country", and the control every positive case needs.
_WITHOUT_ADDRESSES: Final = "facturae_32_recargo_invoice.xml"

_CATALOGUED_ALPHA3: Final = "ESP"

#: ISO 3166-1 user-assigned codes, one per spelling: reserved to name no country
#: at all, so the document is wrong and the operator fixes it off the page.
#:
#: **Pinned, unlike the specimens below, and the asymmetry is the point.** The
#: reserved ranges are fixed by the standard, so no enrolment can turn one into a
#: country and a literal here can never go stale. That is exactly what
#: distinguishes the two kinds this file keeps apart: a code that names nothing
#: by construction, against one our data has simply not reached.
#:
#: Both spellings are carried because both are reachable. The alpha-3 ranges were
#: the half nothing gated, and on the relief path that is the direction that
#: costs: a reserved alpha-3 misread as a catalogue gap is FORGIVEN, honouring a
#: declared export relief on a code with no referent.
_UNASSIGNED_ALPHA2: Final = "XX"
_UNASSIGNED_ALPHA3: Final = "ZZZ"

#: One jurisdiction the bundled vocabulary carries in NEITHER spelling, drawn at
#: import time from the shared specimen helper.
#:
#: **Derived rather than pinned, because a pinned country is a hostage.** This
#: suite was first written against a country measured uncatalogued, and the
#: vocabulary moved under it mid-session: every case failed for a reason that had
#: nothing to do with the behaviour under test. The property is "the vocabulary
#: cannot place this token", never the identity of the country that happens to
#: satisfy it today.
#:
#: The helper is shared rather than local for the same reason: it draws the
#: candidates from AEAT's own SII enumeration and from Facturae's, so a specimen
#: is a code a real submitted document can actually state, and every suite with
#: this problem follows one boundary instead of each keeping its own list. The
#: two spellings are derived independently and need not name one country --
#: deriving either from the other would need a correspondence that, for a code
#: outside the vocabulary, is precisely what this tree does not have.
_UNCATALOGUED_ALPHA2: Final = an_uncatalogued_alpha2()
_UNCATALOGUED_ALPHA3: Final = an_uncatalogued_alpha3()


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


class TestTheProbeStillMeansWhatItSays:
    """The anchor. Without it every case below could pass vacuously.

    The probe is chosen for a property -- the bundled vocabulary carries this
    jurisdiction in neither spelling -- and a registry commit can take that
    property away silently. When it does, the cases here would stop exercising
    an unplaceable country while still reading as though they did, which is the
    failure mode of every gate that pins registry data. This states the property
    outright so the loss is a named red rather than a quiet change of subject.
    """

    def test_the_selected_probe_is_uncatalogued_in_both_spellings(self) -> None:
        """The specimen still carries the property it was selected for.

        **What this adds, stated precisely, because it is narrower than it
        looks.** The helper selects on the resolver returning nothing, and the
        status axis asks that same resolver as its first branch -- so this cannot
        claim to be an independent second opinion, and the first half of the
        assertion is close to guaranteed by the selection. What it genuinely
        discriminates is the rest of the ladder: that the specimen is not in the
        reserved ranges, and that the alpha-3 branch fires rather than falling
        through to ``None``. Both are real ways the selection could stop meaning
        what the cases below read it as, and neither follows from the resolver.
        """
        assert record_country_code_status(_UNCATALOGUED_ALPHA2) is StatedCountryCodeStatus.UNCATALOGUED
        assert record_country_code_status(_UNCATALOGUED_ALPHA3) is StatedCountryCodeStatus.UNCATALOGUED

    def test_the_probe_is_a_real_jurisdiction_and_not_a_reserved_range(self) -> None:
        """UNCATALOGUED must be earned by absence, never by ISO reservation.

        A probe drawn from the user-assigned ranges would classify as
        ``UNASSIGNED``, so this would fail loudly -- but the reverse mistake is
        the quiet one: were the alpha-3 reserved ranges ever to stop being
        recognised, a reserved code would report as our catalogue gap and this
        suite would happily use it as a stand-in for a real country.
        """
        assert record_country_code_status(_UNASSIGNED_ALPHA2) is StatedCountryCodeStatus.UNASSIGNED
        assert record_country_code_status(_UNASSIGNED_ALPHA3) is StatedCountryCodeStatus.UNASSIGNED
        # Range interiors as well as the pinned probes, so a set that had lost
        # its ranges and kept only the two literals this file names would fail.
        assert record_country_code_status("QMA") is StatedCountryCodeStatus.UNASSIGNED
        assert record_country_code_status("XZZ") is StatedCountryCodeStatus.UNASSIGNED

    def test_the_catalogued_control_is_still_catalogued(self) -> None:
        """The other side of the same hostage problem, on the negative control.

        Every "raises no advisory" case rests on ``ESP`` being placeable. If the
        correspondence ever lost it those cases would pass for the wrong reason
        -- an advisory suppressed because nothing was stated rather than because
        the country resolved.
        """
        assert record_country_code_status(_CATALOGUED_ALPHA3) is StatedCountryCodeStatus.CATALOGUED


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
        re-reads an invoice that reads perfectly. It is our vocabulary that is
        short, and the sentence has to say so.
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
        """The same jurisdiction in the other spelling reaches the same sentence.

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

    def test_an_unassigned_alpha3_raises_the_typo_advisory_too(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The reserved ranges reach the operator in BOTH spellings, as one kind.

        The empty cell in the spelling-by-kind matrix until now: uncatalogued
        alpha-2, uncatalogued alpha-3 and unassigned alpha-2 each had a case, and
        this one did not. It is the cell that was the defect -- a reserved
        alpha-3 was classified as a catalogue gap, so the operator was told the
        country may be real and our vocabulary incomplete, about a code ISO
        reserved so that no country will ever be allocated to it. That sentence
        is an instruction to enrol a code no registry may honestly carry.

        Facturae states the country in alpha-3 and is the format most of this
        corpus arrives in, so this is not the rare spelling.
        """
        draft = _draft(
            _stating(_UNASSIGNED_ALPHA3),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="facturae_unassigned_alpha3_advisory.xml",
        )

        advisory = country_vocabulary_advisory(draft)

        assert advisory is not None
        assert advisory.parties[0].status is StatedCountryCodeStatus.UNASSIGNED
        assert advisory.parties[0].stated_code == _UNASSIGNED_ALPHA3
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
        individually plausible, and it was their EQUALITY that hid a real export.
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


#: The authored UBL export specimen. It declares UNTDID ``G`` -- free export
#: item, IVA not charged -- and prints NO country for either party, so as
#: authored it exercises the guard's refusal path and never its sparing. That is
#: consistent with the sparing having gone unnoticed: nothing in the corpus
#: reached it.
_UBL_EXPORT: Final = "en16931_ubl_export_third_country_invoice.xml"

#: Where a customer address block is injected. The corpus tree is never written
#: to; every edit lands in a tmp copy, the way the sibling country suite does it.
_UBL_CUSTOMER_ANCHOR: Final = "<cac:AccountingCustomerParty>\n    <cac:Party>\n"


def _export_billed_to(code: str | None) -> str:
    """Return the UBL export specimen with the CUSTOMER established in *code*.

    The customer side deliberately: on an invoice the filer ISSUED, the customer
    is the counterparty whose territory decides whether the operation is an
    export, and it is that party's establishment the declared relief rests on.
    """
    base = _corpus(_UBL_EXPORT)
    if code is None:
        return base
    assert base.count(_UBL_CUSTOMER_ANCHOR) == 1, "the specimen's customer block has drifted"
    block = (
        "      <cac:PostalAddress><cac:Country>"
        f"<cbc:IdentificationCode>{code}</cbc:IdentificationCode>"
        "</cac:Country></cac:PostalAddress>\n"
    )
    injected = base.replace(_UBL_CUSTOMER_ANCHOR, _UBL_CUSTOMER_ANCHOR + block, 1)
    assert f"<cbc:IdentificationCode>{code}</cbc:IdentificationCode>" in injected
    return injected


class TestTheDeclaredReliefGuardSparesACatalogueGap:
    """The guard's sparing rung, driven from a document rather than from a literal.

    A guard sits on the declared-category branch: an export or intra-community
    claim whose counterparty residency was not established has its category
    WITHHELD, because absence of establishment is not disproof of the claim but
    is not evidence for it either. It carries one exemption -- a well-formed code
    naming a jurisdiction our own vocabulary merely lacks is OUR gap, and
    refusing there rejects a legitimate export over a row nobody has written.

    **The exemption could not fire, and the reason is exactly this row's
    defect.** Production classifies the counterparty's code off the draft, and
    the resolved field is empty for precisely the codes the exemption is for --
    an uncatalogued token arrived as ``None`` in either spelling, which is what a
    document with no address block gives. So a legitimate export was refused
    while the guard's own cases, which supply the status directly, stayed green:
    the logic was proven and the wiring was not.

    These cases supply nothing. They put a country in a document, drive the real
    reader, and read the category the real resolver produced.
    """

    def _confirmed(
        self,
        code: str | None,
        *,
        settings: Settings,
        objects: SecureObjectRepository,
        tmp_path: Path,
        name: str,
    ) -> ConfirmedEstablishment:
        draft = _draft(
            _export_billed_to(code),
            settings=settings,
            objects=objects,
            tmp_path=tmp_path,
            name=name,
        )
        # The document's own declared relief, asserted rather than assumed: if
        # the specimen stopped declaring `G` every case below would pass by
        # never reaching the guard at all.
        assert draft.iva_category == IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED.value
        return resolve_confirmed_establishment(
            bucket_id=_BUCKET_ID,
            draft=draft,
            kind=InvoiceKind.ISSUED,
        )

    @staticmethod
    def _counterparty_unestablished(confirmed: ConfirmedEstablishment) -> bool:
        """Return whether the assembly is short the COUNTERPARTY's own residency."""
        return "customer_residency" in {gap.field for gap in confirmed.assembly.missing}

    def test_an_uncatalogued_export_declaring_the_relief_has_its_slot_forgiven(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The exemption reaches the guard from a document, and forgives ONE slot.

        This is the wiring assertion. The counterparty's residency is
        unresolved -- our vocabulary does not carry the jurisdiction -- and the
        refusal that comes back no longer names it, which it can only do if the
        record's own token travelled from the document through the reader into
        the guard's exemption. Before this row the token never arrived and the
        refusal named both slots.

        The claim is still withheld here, and correctly: this fixture carries no
        taxpayer profile, so the FILER's territory is unestablished too, and
        that gap is an unfinished setup rather than a hole in our data. The
        exemption has no warrant for it. That the reason narrowed to exactly the
        filer's slot is the whole measurement.
        """
        confirmed = self._confirmed(
            _UNCATALOGUED_ALPHA2,
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="ubl_export_uncatalogued.xml",
        )

        assert self._counterparty_unestablished(confirmed)
        assert confirmed.category.outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF
        assert "issuer_residency" in confirmed.category.note
        assert "customer_residency" not in confirmed.category.note

    def test_the_alpha3_spelling_of_the_same_country_is_forgiven_too(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The alpha-3 form reaches the exemption, which the alpha-2 status axis cannot answer.

        Separate from the case above rather than parametrised with it, because
        only one route reaches both: a fix carried by the alpha-2 status
        authority alone closes the two-letter form and leaves the three-letter
        one refused, and a single parametrised case would hide which half had
        landed.
        """
        confirmed = self._confirmed(
            _UNCATALOGUED_ALPHA3,
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="ubl_export_uncatalogued_alpha3.xml",
        )

        assert confirmed.category.outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF
        assert "issuer_residency" in confirmed.category.note
        assert "customer_residency" not in confirmed.category.note

    def test_a_document_stating_no_country_has_both_slots_named(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The positive control, and it is the specimen exactly as authored.

        The DOCUMENT states no country for either party, so nothing is our
        vocabulary's gap and nothing is forgiven. The refusal therefore names
        the counterparty's residency. Without this the cases above would pass
        against a guard that had simply stopped naming the counterparty at all,
        which is the shape of a green run measuring the harness rather than the
        code.

        It names ONE slot, not two, and that is the correct reading: the filer's
        own territory is a PROFILE fact this document cannot supply, and the
        profile supplies it -- the issuer scope resolves from the asserted fact
        rather than from the specimen. A refusal naming a residency the profile
        already established would send the operator to fix something that is not
        broken. The both-slots case is covered where it genuinely arises, by
        ``test_the_exemption_does_not_forgive_the_filers_own_slot``.
        """
        confirmed = self._confirmed(
            None,
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="ubl_export_silent.xml",
        )

        assert confirmed.category.outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF
        assert "customer_residency" in confirmed.category.note
        # The filer's slot is absent from the refusal because it is ESTABLISHED,
        # not because the guard stopped naming slots -- assert that directly, or
        # this control would pass against a guard that had gone silent.
        assert "issuer_residency" not in {gap.field for gap in confirmed.assembly.missing}

    def test_an_iso_unassigned_code_is_not_forgiven(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The other control, on the direction that costs money.

        The user-assigned ranges are reserved to name no country at all, so they
        are not a gap in our data and forgiving one would move a zero-rated
        export claim closer to being honoured on a string with no referent. The
        exemption has to distinguish the two kinds: a fix that forgave every
        unresolved code would pass the cases above while opening exactly the
        hole the country rung was narrowed to close.
        """
        confirmed = self._confirmed(
            _UNASSIGNED_ALPHA2,
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="ubl_export_unassigned.xml",
        )

        assert confirmed.category.outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF
        assert "customer_residency" in confirmed.category.note

    def test_an_unassigned_alpha3_is_not_forgiven_either(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The reserved-code refusal in the spelling that had no case, on the path that pays.

        The alpha-2 sibling above gated one half of this and the other half was
        open, which mattered here more than on the advisory: misclassifying a
        reserved alpha-3 as a catalogue gap does not merely word a notice wrongly,
        it FORGIVES the counterparty's slot -- moving a declared zero-rated export
        claimed on a code with no referent towards being honoured. Facturae states
        alpha-3, so that is reachable from the commonest structured document in
        this corpus.

        Asserted through the same real reader as its sibling, so it measures the
        classification a document actually receives rather than one handed to the
        guard directly.
        """
        confirmed = self._confirmed(
            _UNASSIGNED_ALPHA3,
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="ubl_export_unassigned_alpha3.xml",
        )

        assert confirmed.category.outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF
        assert "customer_residency" in confirmed.category.note

    def test_the_relief_stands_once_the_filer_is_the_only_thing_established(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """And with no other residency outstanding, the claim is honoured.

        The cases above prove the exemption forgives the right slot; this proves
        forgiving it is sufficient, which no assertion about a narrowed refusal
        can show. The country still comes from the document through the real
        reader -- that is the half this row is about. The filer's own territory
        is supplied, because it is a PROFILE fact by design: the confirm path
        reads it from the profile and never from the paper, so a document can
        never carry it and a fixture that withheld it would be testing an
        unfinished setup rather than the country axis.
        """
        draft = _draft(
            _export_billed_to(_UNCATALOGUED_ALPHA2),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="ubl_export_established_filer.xml",
        )
        declared = DeclaredFacts(
            stated_category=DeclaredFact(
                value=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
                source=ClassifierInputSource.DOCUMENT_EVIDENCE,
            ),
            issuer_scope=DeclaredFact(
                value=IvaTerritorialScope.ES_MAINLAND,
                source=ClassifierInputSource.PROFILE_AUTHORITY,
            ),
            customer_tax_status=DeclaredFact(
                value=CustomerTaxStatus.B2B_IVA_REGISTERED,
                source=ClassifierInputSource.OPERATOR_ASSERTION,
            ),
            supply_nature=DeclaredFact(
                value=SupplyNature.GOODS,
                source=ClassifierInputSource.OPERATOR_ASSERTION,
            ),
        )
        assembly = assemble_classification_criteria(
            transaction_date=date(2026, 4, 2),
            direction=InvoiceKind.ISSUED,
            inputs=collect_classifier_inputs(draft),
            declared=declared,
        )
        # The counterparty's residency is the ONE thing still open, which is the
        # precondition the exemption exists for. Asserted rather than assumed:
        # were another input to go missing, the case below would be measuring
        # that instead.
        assert {gap.field for gap in assembly.missing} == {"customer_residency"}

        resolution = resolve_ingestion_iva_category(
            assembly,
            declared=declared,
            direction=InvoiceKind.ISSUED,
            counterparty_country_status=record_country_code_status(draft.customer_stated_country_code),
        )

        assert resolution.outcome is not IvaCategoryOutcome.UNSUPPORTED_RELIEF
        assert resolution.category is IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED

    def test_the_filers_own_gap_is_never_forgiven_by_the_counterpartys_excuse(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The under-declaration direction this scoping closes, stated on its own.

        An unscoped exemption suppressed the refusal for EVERY outstanding
        residency once the counterparty's code happened to be uncatalogued, so a
        zero-rated export was honoured with neither party established. That was
        unreachable until the counterparty's stated token started arriving here
        at all, which is to say this row opened it -- so it is gated beside the
        row rather than left for a later reader to find.
        """
        draft = _draft(
            _export_billed_to(_UNCATALOGUED_ALPHA2),
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="ubl_export_no_filer.xml",
        )
        declared = DeclaredFacts(
            stated_category=DeclaredFact(
                value=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
                source=ClassifierInputSource.DOCUMENT_EVIDENCE,
            ),
            customer_tax_status=DeclaredFact(
                value=CustomerTaxStatus.B2B_IVA_REGISTERED,
                source=ClassifierInputSource.OPERATOR_ASSERTION,
            ),
            supply_nature=DeclaredFact(
                value=SupplyNature.GOODS,
                source=ClassifierInputSource.OPERATOR_ASSERTION,
            ),
        )
        assembly = assemble_classification_criteria(
            transaction_date=date(2026, 4, 2),
            direction=InvoiceKind.ISSUED,
            inputs=collect_classifier_inputs(draft),
            declared=declared,
        )
        assert {gap.field for gap in assembly.missing} == {"customer_residency", "issuer_residency"}

        resolution = resolve_ingestion_iva_category(
            assembly,
            declared=declared,
            direction=InvoiceKind.ISSUED,
            counterparty_country_status=record_country_code_status(draft.customer_stated_country_code),
        )

        assert resolution.outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF
        assert "issuer_residency" in resolution.note
        assert "customer_residency" not in resolution.note

    def test_a_catalogued_third_country_needs_no_exemption_at_all(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        """The population the vocabulary does carry, which is most of it.

        ``US`` RESOLVES a third country, so the counterparty residency is
        established and the exemption is never consulted for this document.
        Asserted so the cases above read as a bounded hole in our data rather
        than as the normal path -- US, GB, CH, JP, CN and the rest all resolve.
        """
        confirmed = self._confirmed(
            "US",
            settings=isolated_settings,
            objects=secure_objects,
            tmp_path=tmp_path,
            name="ubl_export_us.xml",
        )

        assert not self._counterparty_unestablished(confirmed)
        assert confirmed.counterparty.scope is IvaTerritorialScope.THIRD_COUNTRY
