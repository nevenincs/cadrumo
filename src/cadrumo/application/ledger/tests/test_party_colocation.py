"""The transposition gate: swapped address blocks never yield swapped territories.

The gate that decides deterministic co-location. A fully transposed pair of
address blocks must produce either correct attribution or a refusal, and never a
draft that is clean on its face while both parties sit in a territory neither is
established in.

Every fixture here is shaped like the real evidence corpus was measured to be:
reading-order lines with NO blank lines between blocks, because that is what a
PDF text extractor emits. A fixture with blank-line-delimited blocks would have
let a blank-line implementation pass while never firing on a real document.

The retiring assertion lives here too. The interim stamp must be ABSENT on a
value co-location attributes -- otherwise the interim and the fix ship side by
side indefinitely, which is the cleanup that never gets done.

See Also:
    :func:`~application.ledger.party_colocation.resolve_party_attribution_by_colocation`
        The resolver under test.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

import pytest

from ....core import (
    LOCAL_TRANSPORT_LABEL,
    ConfirmationBlockReason,
    DraftDiscrepancyKind,
    FieldGroundingOutcome,
    FieldOrigin,
)
from ..document_transcription import DocumentTranscription, TranscriberIdentity
from ..evidence_draft import FieldProvenance, InvoiceDraft
from ..grounded_reading import ground_draft_against_transcription
from ..party_attribution import party_attribution_advisory
from ..party_colocation import (
    PartyAttributionOutcome,
    party_regions,
    resolve_party_attribution_by_colocation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SUPPLIER_HEADING: Final = "Reformas Delta SL"
_CUSTOMER_HEADING: Final = "FACTURAR A"

# Shaped after `com_2026_0005_layout_minimal.pdf` as the extractor actually
# emits it: one line per printed row, no blank line anywhere.
_PAGE: Final = "\n".join(
    (
        "FACTURA",
        _SUPPLIER_HEADING,
        "Calle Sin Nombre 0",
        "28901 Getafe",
        "NIF B12345674",
        "Emitida 2026-06-11",
        _CUSTOMER_HEADING,
        "Nordeste Estudio Creativo, S.L.",
        "Poligono Industrial Asipo, Nave 27",
        "35001 Las Palmas",
        "NIF/CIF B44444444",
        "Base imponible 766,30",
        "TOTAL 890,00 EUR",
    ),
)


def _transcription(text: str = _PAGE) -> DocumentTranscription:
    return DocumentTranscription(
        text=text,
        page_count=1,
        source_content_sha256="d" * 64,
        transcriber=TranscriberIdentity(
            origin=FieldOrigin.TEXT_LAYER,
            name="pdf-text-layer-extractor",
            transport=LOCAL_TRANSPORT_LABEL,
            revision="1",
        ),
    )


def _envelope(field: str, anchor: str, *, role_evidence: str | None = None) -> FieldProvenance:
    return FieldProvenance(
        field=field,
        origin=FieldOrigin.TEXT_LAYER,
        grounding=FieldGroundingOutcome.UNANCHORED,
        anchor=anchor,
        role_evidence=role_evidence,
    )


def _draft(*, supplier_postal: str, customer_postal: str) -> InvoiceDraft:
    """Return the draft a reader proposes, role evidence quoted for identities only."""
    return InvoiceDraft(
        supplier_tax_id="B12345674",
        supplier_name=_SUPPLIER_HEADING,
        supplier_postal_code=supplier_postal,
        customer_tax_id="B44444444",
        customer_name="Nordeste Estudio Creativo, S.L.",
        customer_postal_code=customer_postal,
        taxable_base=Decimal("766.30"),
        provenance=(
            _envelope("supplier_tax_id", "B12345674", role_evidence=_SUPPLIER_HEADING),
            _envelope("customer_tax_id", "B44444444", role_evidence=_CUSTOMER_HEADING),
            _envelope("supplier_postal_code", supplier_postal),
            _envelope("customer_postal_code", customer_postal),
        ),
    )


def _straight() -> InvoiceDraft:
    return _draft(supplier_postal="28901", customer_postal="35001")


def _transposed() -> InvoiceDraft:
    return _draft(supplier_postal="35001", customer_postal="28901")


def _resolve(draft: InvoiceDraft):
    return resolve_party_attribution_by_colocation(draft=draft, transcription=_transcription())


def test_the_document_partitions_into_one_region_per_party() -> None:
    """The partition itself is asserted, not only its consequences.

    An outcome-only assertion cannot tell a correct partition from a collapsed
    one: both leave the transposition case non-silent, but only one is the
    mechanism this row delivers.
    """
    regions = party_regions(draft=_straight(), transcription=_transcription())

    assert set(regions) == {"supplier", "customer"}
    assert "28901 Getafe" in regions["supplier"]
    assert "35001 Las Palmas" in regions["customer"]
    assert "35001" not in regions["supplier"]
    assert "28901" not in regions["customer"]


def test_correctly_filed_address_values_are_attributed_by_containment() -> None:
    """The ordinary document resolves silently, which is what keeps the fix usable."""
    outcomes = _resolve(_straight()).outcomes

    assert outcomes["supplier_postal_code"] is PartyAttributionOutcome.ATTRIBUTED
    assert outcomes["customer_postal_code"] is PartyAttributionOutcome.ATTRIBUTED


def test_a_transposition_is_contradicted_and_never_silently_swapped() -> None:
    """THE gate. Swapped blocks yield a refusal, never two confident wrong territories."""
    resolution = _resolve(_transposed())

    assert resolution.outcomes["supplier_postal_code"] is PartyAttributionOutcome.CONTRADICTED
    assert resolution.outcomes["customer_postal_code"] is PartyAttributionOutcome.CONTRADICTED
    assert set(resolution.contradicted_fields) == {"supplier_postal_code", "customer_postal_code"}


def test_the_interim_stamp_is_absent_on_a_co_located_value() -> None:
    """The retiring assertion the amendment mandates.

    Without this the interim stamp and its structural replacement ship side by
    side: the resolver attributes the value while the envelope still says nothing
    verified it, and every reader downstream sees the weaker claim.
    """
    grounded = ground_draft_against_transcription(draft=_straight(), transcription=_transcription())

    stamps = {envelope.field: envelope.attribution_unverified for envelope in grounded.provenance}
    assert stamps["supplier_postal_code"] is False
    assert stamps["customer_postal_code"] is False


def test_a_transposed_value_keeps_the_stamp_rather_than_reading_as_attributed() -> None:
    """A contradiction must never clear the stamp -- it is the opposite of a clean bill."""
    grounded = ground_draft_against_transcription(draft=_transposed(), transcription=_transcription())

    stamps = {envelope.field: envelope.attribution_unverified for envelope in grounded.provenance}
    assert stamps["supplier_postal_code"] is True
    assert stamps["customer_postal_code"] is True


def test_a_value_printed_in_both_regions_stays_unresolved() -> None:
    """Repetition cannot launder a value into an attributed one.

    Real documents do this: the corpus zugferd specimen reprints the supplier's
    postal code in a remarks block below the customer heading. Reading presence
    in its own region as sufficient would attribute it on a document that cannot
    separate the two.
    """
    page = _PAGE + "\nRemitir correspondencia a 28901 Getafe"
    draft = _straight()

    resolution = resolve_party_attribution_by_colocation(draft=draft, transcription=_transcription(page))

    assert resolution.outcomes["supplier_postal_code"] is PartyAttributionOutcome.UNRESOLVED


def test_a_document_with_one_usable_heading_resolves_nothing() -> None:
    """One anchor partitions nothing, so it must not attribute everything to that party."""
    draft = _straight()
    single = draft.model_copy(
        update={
            "provenance": tuple(
                _envelope("customer_tax_id", "B44444444") if envelope.field == "customer_tax_id" else envelope
                for envelope in draft.provenance
            ),
        },
    )

    assert resolve_party_attribution_by_colocation(draft=single, transcription=_transcription()).outcomes == {}


def test_role_evidence_the_document_does_not_print_anchors_nothing() -> None:
    """A fabricated heading fails safe rather than partitioning on a phantom."""
    draft = _draft(supplier_postal="28901", customer_postal="35001")
    invented = draft.model_copy(
        update={
            "provenance": tuple(
                _envelope("customer_tax_id", "B44444444", role_evidence="BILL TO THE FOLLOWING PARTY")
                if envelope.field == "customer_tax_id"
                else envelope
                for envelope in draft.provenance
            ),
        },
    )

    assert resolve_party_attribution_by_colocation(draft=invented, transcription=_transcription()).outcomes == {}


def test_an_unconsidered_field_defaults_to_unresolved_not_attributed() -> None:
    """The default direction keeps the stamp, so a field falling out fails safe."""
    resolution = _resolve(_straight())

    assert resolution.outcome_for("supplier_country_code") is PartyAttributionOutcome.UNRESOLVED


def test_a_transposition_reaches_the_operator_as_a_blocking_refusal() -> None:
    """The consuming half. A detected transposition must refuse, not be dropped.

    Detecting a swap and discarding it is the same shape as evidence no resolver
    consumes: the check runs, nothing acts, and the draft confirms clean.
    """
    from ..confirmation_gate import confirmation_blockers

    grounded = ground_draft_against_transcription(draft=_transposed(), transcription=_transcription())

    kinds = [finding.kind for finding in grounded.discrepancies]
    assert DraftDiscrepancyKind.PARTY_ATTRIBUTION_CONTRADICTED in kinds
    blocked_fields = {
        blocker.field
        for blocker in confirmation_blockers(grounded)
        if blocker.reason is ConfirmationBlockReason.UNDETERMINED_ESTABLISHMENT
    }
    assert {"supplier_postal_code", "customer_postal_code"} <= blocked_fields


def test_a_correctly_filed_document_raises_no_attribution_blocker() -> None:
    """The ordinary case must not be refused, or the blocker trains operators to ignore it."""
    from ..confirmation_gate import confirmation_blockers

    grounded = ground_draft_against_transcription(draft=_straight(), transcription=_transcription())

    assert DraftDiscrepancyKind.PARTY_ATTRIBUTION_CONTRADICTED not in [f.kind for f in grounded.discrepancies]
    assert confirmation_blockers(grounded) == ()


def test_an_unresolvable_document_advises_rather_than_refuses() -> None:
    """A layout that cannot be separated stays on the advisory, never the blocker."""

    draft = _straight()
    unanchorable = draft.model_copy(
        update={
            "provenance": tuple(
                _envelope("customer_tax_id", "B44444444") if envelope.field == "customer_tax_id" else envelope
                for envelope in draft.provenance
            ),
        },
    )

    grounded = ground_draft_against_transcription(draft=unanchorable, transcription=_transcription())

    assert DraftDiscrepancyKind.PARTY_ATTRIBUTION_CONTRADICTED not in [f.kind for f in grounded.discrepancies]
    stamps = {e.field: e.attribution_unverified for e in grounded.provenance}
    assert stamps["supplier_postal_code"] is True


# The layout every real document measured actually has: a two-column header,
# which a reading-order extractor emits as one line carrying BOTH parties. The
# fixtures above use a stacked header, which is the layout the resolver was
# designed against and which the scored corpus does not contain.
_TWO_COLUMN_PAGE: Final = "\n".join(
    (
        "FACTURA",
        f"{_SUPPLIER_HEADING}  {_CUSTOMER_HEADING}",
        "Calle Sin Nombre 0  Poligono Industrial Asipo, Nave 27",
        "28901 Getafe  35001 Las Palmas",
        "NIF B12345674  NIF/CIF B44444444",
        "Base imponible 766,30",
        "TOTAL 890,00 EUR",
    ),
)


def test_asserted_gap_a_two_column_header_resolves_nothing() -> None:
    """The measured real-document case, pinned where a reader meets the resolver.

    Scored against authored anchors over the reference corpus, NO document could
    be partitioned, and every one failed here: both role headings arrive on one
    line, the earlier span is zero-width, and the region builder drops it. That
    is the correct behaviour -- keeping the span would attribute one party's
    values to the other -- but it means this resolver does not fire on the
    layout real invoices use, and a suite testing only a stacked header would
    never say so.

    Asserted on the partition rather than on the outcomes, because an empty
    outcome map is also what a resolver that was never called produces.

    **This asserts a GAP, not a contract.** It is expected to fail the day the
    region builder learns to split a line carrying both role labels, or the
    pipeline preserves the geometry to segment a column -- and that failure is
    the notification. A lane finding it red should replace it with a gate
    asserting the two-column layout now partitions, and update the module
    docstrings that state the ceiling, never relax it to match the code. The
    ``test_asserted_gap_`` prefix carries that at the only place a triager
    reliably looks, because a name read at speed is taken for a contract and
    then "fixed" -- which cancels the gate at the moment it fires.
    """
    assert party_regions(draft=_straight(), transcription=_transcription(_TWO_COLUMN_PAGE)) == {}


def test_the_stacked_header_still_partitions_so_the_zero_is_about_layout() -> None:
    """The positive control, and the reason the zero is not a broken resolver.

    Without it "resolves nothing" is indistinguishable from "resolver is
    unwired", and the two call for opposite responses: one is a pipeline
    question about preserving geometry, the other is a bug here. Same parties,
    same values, same draft -- only the line structure differs -- so the
    difference in outcome can only be the layout.
    """
    regions = party_regions(draft=_straight(), transcription=_transcription())

    assert len(regions) == 2
    assert set(regions) == {"supplier", "customer"}


def test_a_two_column_document_keeps_the_stamp_and_the_operator_keeps_the_advisory() -> None:
    """On the real layout the unverified-attribution stamp IS the mechanism.

    The honest state made executable. On a document the resolver cannot
    partition every address value stays stamped and the operator is still
    warned, so nothing reads as verified that was not, and the failure direction
    stays safe.

    Measured rather than claimed: a mutation giving an unsegmentable document a
    clean bill reds this and two neighbours, so the stamp is not resting on this
    test alone. What it adds over those two is the LAYOUT -- they reach an empty
    resolution by removing role evidence or by transposing values, both
    constructed shapes, while this reaches it through the header real invoices
    actually print. The stamp surviving on the real layout is the claim, and a
    fixture-shaped route to the same resolution does not make it.
    """
    grounded = ground_draft_against_transcription(
        draft=_straight(),
        transcription=_transcription(_TWO_COLUMN_PAGE),
    )

    stamps = {envelope.field: envelope.attribution_unverified for envelope in grounded.provenance}
    assert stamps["supplier_postal_code"] is True
    assert stamps["customer_postal_code"] is True
    # Advisory, never blocker: an unpartitionable layout is not a contradiction.
    assert DraftDiscrepancyKind.PARTY_ATTRIBUTION_CONTRADICTED not in [f.kind for f in grounded.discrepancies]
    assert party_attribution_advisory(grounded) is not None
