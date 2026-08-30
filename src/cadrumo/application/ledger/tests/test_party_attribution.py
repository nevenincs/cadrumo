"""Real-path regression for the unverified-party-attribution stamp.

Every stamp asserted here is produced by
:func:`~application.ledger.grounded_reading.ground_draft_against_transcription` -- the one entry
point the reading router uses -- over a real
:class:`~application.ledger.document_transcription.DocumentTranscription`. Constructing a stamped
envelope by hand would prove the field exists and nothing else; what has to be
true is that a draft coming off a reader carries it.

The transposition case is the reason the whole apparatus exists: two address
blocks read the wrong way round produce a draft with no discrepancy, no blocker
and every anchor verified, so the stamp is the only thing that says anything is
wrong.

See Also:
    :func:`~application.ledger.party_attribution.stamp_unverified_party_attribution`
        The pass under test.
    :func:`~application.ledger.party_attribution.party_attribution_advisory`
        What the operator is told in consequence.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

import pytest

from ....core import LOCAL_TRANSPORT_LABEL, FieldGroundingOutcome, FieldOrigin
from ....domain.iva.classification import IvaTerritorialScope
from ..document_transcription import DocumentTranscription, TranscriberIdentity
from ..evidence_draft import FieldProvenance, InvoiceDraft
from ..grounded_reading import ground_draft_against_transcription
from ..party_attribution import (
    ATTRIBUTION_ESTABLISHING_ORIGINS,
    PARTY_ATTRIBUTED_ADDRESS_FIELDS,
    party_addresses,
    party_attribution_advisory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE_SHA: Final = "b" * 64

_PAGE: Final = (
    "FACTURA 2026-0142\n"
    "Emisor: Acme Suministros SL\n"
    "NIF B12345674\n"
    "Calle Mayor 3, 28001 Madrid\n"
    "España\n"
    "Cliente: Islas Comercial SL\n"
    "NIF B44444444\n"
    "Avenida del Puerto 9, 35001 Las Palmas de Gran Canaria\n"
    "España\n"
    "Base imponible 100,00\n"
)


def _transcription() -> DocumentTranscription:
    return DocumentTranscription(
        text=_PAGE,
        page_count=1,
        source_content_sha256=_SOURCE_SHA,
        transcriber=TranscriberIdentity(
            origin=FieldOrigin.TEXT_LAYER,
            name="pdf-text-layer-extractor",
            transport=LOCAL_TRANSPORT_LABEL,
            revision="1",
        ),
    )


def _address_envelope(field: str, anchor: str, *, origin: FieldOrigin = FieldOrigin.TEXT_LAYER) -> FieldProvenance:
    """Return an envelope exactly as a reader leaves one: anchor claimed, unchecked."""
    return FieldProvenance(
        field=field,
        origin=origin,
        grounding=FieldGroundingOutcome.UNANCHORED,
        anchor=anchor,
    )


def _read_draft(*, supplier_postal: str, customer_postal: str) -> InvoiceDraft:
    """Return the draft a text-layer reader proposes for the page above."""
    return InvoiceDraft(
        supplier_tax_id="B12345674",
        supplier_name="Acme Suministros SL",
        supplier_postal_code=supplier_postal,
        supplier_country="España",
        customer_tax_id="B44444444",
        customer_name="Islas Comercial SL",
        customer_postal_code=customer_postal,
        customer_country="España",
        taxable_base=Decimal("100.00"),
        provenance=(
            _address_envelope("supplier_postal_code", supplier_postal),
            _address_envelope("supplier_country", "España"),
            _address_envelope("customer_postal_code", customer_postal),
            _address_envelope("customer_country", "España"),
            _address_envelope("taxable_base", "100,00"),
        ),
    )


def _grounded(draft: InvoiceDraft) -> InvoiceDraft:
    return ground_draft_against_transcription(draft=draft, transcription=_transcription())


def _stamp(draft: InvoiceDraft, field: str) -> bool:
    envelope = next(item for item in draft.provenance if item.field == field)
    return envelope.attribution_unverified


def test_the_canonical_party_table_owns_fields_and_operator_roles_for_both_advisories() -> None:
    """Country and postal checks cannot re-declare a different pair of parties."""
    assert [
        (
            party.role,
            party.postal_field,
            party.country_field,
            party.country_code_field,
            party.stated_country_code_field,
            party.operator_role,
        )
        for party in party_addresses()
    ] == [
        (
            "supplier",
            "supplier_postal_code",
            "supplier_country",
            "supplier_country_code",
            "supplier_stated_country_code",
            "issuing",
        ),
        (
            "customer",
            "customer_postal_code",
            "customer_country",
            "customer_country_code",
            "customer_stated_country_code",
            "billed",
        ),
    ]


def test_the_reading_path_stamps_every_model_read_party_address_value() -> None:
    """A read draft arrives with each per-party address field stamped unverified."""
    grounded = _grounded(_read_draft(supplier_postal="28001", customer_postal="35001"))

    stamped = {envelope.field for envelope in grounded.provenance if envelope.attribution_unverified}
    assert stamped == {
        "supplier_postal_code",
        "supplier_country",
        "customer_postal_code",
        "customer_country",
    }


def test_a_value_that_is_not_a_party_address_is_never_stamped() -> None:
    """The stamp does not spread to fields naming no party."""
    grounded = _grounded(_read_draft(supplier_postal="28001", customer_postal="35001"))

    assert _stamp(grounded, "taxable_base") is False


def test_the_stamp_is_per_field_so_one_party_value_can_be_attributed_and_another_not() -> None:
    """Two fields of ONE party disagree, which a coarser flag could not express.

    The retiring gate for deterministic co-location has to assert the stamp is
    ABSENT on the values that resolver attributes, while its co-located siblings
    may still carry it. That assertion is only possible if the stamp can differ
    within a single party, so it is proven here rather than assumed.
    """
    draft = _read_draft(supplier_postal="28001", customer_postal="35001")
    attributed = draft.model_copy(
        update={
            "provenance": tuple(
                # The structured record's element path names the party, which is
                # exactly the answer deterministic co-location will supply.
                _address_envelope("supplier_country", "España", origin=FieldOrigin.EXACT_STRUCTURED)
                if envelope.field == "supplier_country"
                else envelope
                for envelope in draft.provenance
            ),
        },
    )

    grounded = _grounded(attributed)

    assert _stamp(grounded, "supplier_postal_code") is True
    assert _stamp(grounded, "supplier_country") is False


def test_an_attribution_establishing_origin_clears_a_stale_stamp() -> None:
    """The pass is not a latch: it restamps both ways on every run."""
    draft = _read_draft(supplier_postal="28001", customer_postal="35001")
    stale = draft.model_copy(
        update={
            "provenance": tuple(
                FieldProvenance(
                    field="supplier_postal_code",
                    origin=FieldOrigin.EXACT_STRUCTURED,
                    grounding=FieldGroundingOutcome.UNANCHORED,
                    anchor="28001",
                    attribution_unverified=True,
                )
                if envelope.field == "supplier_postal_code"
                else envelope
                for envelope in draft.provenance
            ),
        },
    )

    assert _stamp(_grounded(stale), "supplier_postal_code") is False


def test_every_establishing_origin_is_a_real_field_origin_member() -> None:
    """The establishing set names origins that exist, so a rename cannot mute it."""
    assert set(FieldOrigin) >= ATTRIBUTION_ESTABLISHING_ORIGINS
    assert set(FieldOrigin) > ATTRIBUTION_ESTABLISHING_ORIGINS


def test_the_attributed_field_set_covers_both_parties_address_axes() -> None:
    """Every per-party address field the establishment ladder consumes is enrolled."""
    assert {
        "supplier_postal_code",
        "supplier_country",
        "supplier_country_code",
        "customer_postal_code",
        "customer_country",
        "customer_country_code",
    } == PARTY_ATTRIBUTED_ADDRESS_FIELDS
    assert set(InvoiceDraft.model_fields) >= PARTY_ATTRIBUTED_ADDRESS_FIELDS


def test_the_advisory_names_the_territory_each_party_s_values_would_establish() -> None:
    """The operator is given a concrete claim to contest, not an abstraction."""
    grounded = _grounded(_read_draft(supplier_postal="28001", customer_postal="35001"))

    advisory = party_attribution_advisory(grounded)

    assert advisory is not None
    by_role = {party.role: party for party in advisory.parties}
    assert by_role["supplier"].scope_if_attributed is IvaTerritorialScope.ES_MAINLAND
    assert by_role["customer"].scope_if_attributed is IvaTerritorialScope.ES_CANARIAS


def test_a_transposition_produces_no_finding_and_only_the_stamp_says_so() -> None:
    """The failure class the stamp exists for, driven end to end.

    The two postal codes are swapped: each is printed on the page, so every
    anchor verifies, and no deterministic check disagrees. The draft is clean.
    What changes is the territory each party would be placed in -- and the only
    signal that the placement rests on an unchecked assignment is the stamp.
    """
    straight = _grounded(_read_draft(supplier_postal="28001", customer_postal="35001"))
    swapped = _grounded(_read_draft(supplier_postal="35001", customer_postal="28001"))

    assert [finding.kind for finding in swapped.discrepancies] == [finding.kind for finding in straight.discrepancies]
    for field in ("supplier_postal_code", "customer_postal_code"):
        envelope = next(item for item in swapped.provenance if item.field == field)
        assert envelope.grounding is FieldGroundingOutcome.ANCHORED
        assert envelope.attribution_unverified is True

    straight_advisory = party_attribution_advisory(straight)
    swapped_advisory = party_attribution_advisory(swapped)
    assert straight_advisory is not None
    assert swapped_advisory is not None
    straight_scopes = {party.role: party.scope_if_attributed for party in straight_advisory.parties}
    swapped_scopes = {party.role: party.scope_if_attributed for party in swapped_advisory.parties}
    assert straight_scopes != swapped_scopes


def test_a_stamped_field_with_no_printed_value_raises_no_advisory() -> None:
    """An attribution nobody made is not reported as an unverified one."""
    draft = InvoiceDraft(
        supplier_tax_id="B12345674",
        taxable_base=Decimal("100.00"),
        provenance=(
            FieldProvenance(
                field="supplier_postal_code",
                origin=FieldOrigin.TEXT_LAYER,
                grounding=FieldGroundingOutcome.UNANCHORED,
                attribution_unverified=True,
            ),
        ),
    )

    assert party_attribution_advisory(draft) is None
