"""Direction read off the document, in both directions, through the real wire.

Which side of an invoice the filer is on decides which informativa the
counterparty total reaches. Until this derivation the only answer was the one the
operator typed on the confirm verb, unchecked, and the draft's ``suggested_kind``
slot -- declared, documented and printed by the review command -- had no producer
at all.

Every case here drives :func:`~application.ledger.grounded_reading.ground_draft_against_transcription`,
the entry point the reading router actually calls, rather than the leaf alone.
That is deliberate: a leaf asserted in isolation proves the function computes
something, never that the value reaches the draft the operator reviews, and
computed evidence nothing consumes is a recurring failure shape in this codebase.

The pages are hand-built rather than drawn from the corpus because the property
under test is the PARTITION, and a fixture is only useful here if the two party
headings and the two identifiers are placed deliberately. Both identifiers carry
valid control characters, so nothing passes for a reason unrelated to the axis.

See Also:
    :func:`~application.ledger.document_direction.derive_invoice_kind_from_filer_role`
        The leaf under test.
    :func:`~application.ledger.party_colocation.party_regions`
        The heading partition the containment check is read from.
"""

from __future__ import annotations

from typing import Final

import pytest

from ....core import DraftDiscrepancyKind
from ....core.field_grounding import FieldGroundingOutcome
from ....core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from ....core.field_origin import FieldOrigin
from ....domain.iva.classification import InvoiceKind
from ..confirmation_gate import BLOCKING_REASON_BY_DISCREPANCY_KIND
from ..document_direction import (
    DIRECTION_BY_FILER_ROLE,
    DirectionDerivationOutcome,
    derive_invoice_kind_from_filer_role,
)
from ..document_transcription import DocumentTranscription, TranscriberIdentity
from ..evidence_draft import FieldProvenance, InvoiceDraft
from ..grounded_reading import ground_draft_against_transcription

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILER: Final = "B12345674"
_OTHER: Final = "B63104517"

_ISSUED_PAGE: Final = (
    "FACTURA 2026-0001\n"
    "EMISOR\n"
    "Mi Empresa SL\n"
    f"NIF {_FILER}\n"
    "FACTURAR A\n"
    "Cliente Ejemplo SL\n"
    f"NIF {_OTHER}\n"
    "Base imponible 100,00\n"
)

_RECEIVED_PAGE: Final = (
    "FACTURA 2026-0002\n"
    "EMISOR\n"
    "Proveedor Ejemplo SL\n"
    f"NIF {_OTHER}\n"
    "FACTURAR A\n"
    "Mi Empresa SL\n"
    f"NIF {_FILER}\n"
    "Base imponible 100,00\n"
)


def _transcription(text: str) -> DocumentTranscription:
    return DocumentTranscription(
        text=text,
        page_count=1,
        source_content_sha256="c" * 64,
        transcriber=TranscriberIdentity(
            origin=FieldOrigin.TEXT_LAYER,
            name="pdf-text-layer-extractor",
            transport=LOCAL_TRANSPORT_LABEL,
            revision="1",
        ),
    )


def _identity_envelope(field: str, value: str, heading: str) -> FieldProvenance:
    """Return the envelope a reader records for one identity field.

    ``role_evidence`` carries the printed heading that assigns the identifier to
    a party, which is what the partition is anchored on. Without it there is no
    partition and every case here would collapse to the same unresolved outcome
    -- passing a test that asserted only "no direction" and proving nothing.
    """
    return FieldProvenance(
        field=field,
        origin=FieldOrigin.TEXT_LAYER,
        grounding=FieldGroundingOutcome.UNANCHORED,
        anchor=value,
        role_evidence=heading,
    )


def _read(*, supplier: str | None, customer: str | None) -> InvoiceDraft:
    envelopes = []
    if supplier is not None:
        envelopes.append(_identity_envelope("supplier_tax_id", supplier, "EMISOR"))
    if customer is not None:
        envelopes.append(_identity_envelope("customer_tax_id", customer, "FACTURAR A"))
    return InvoiceDraft(supplier_tax_id=supplier, customer_tax_id=customer, provenance=tuple(envelopes))


def _grounded(*, page: str, supplier: str | None, customer: str | None, filer: str | None = _FILER) -> InvoiceDraft:
    """Return the draft as the reading router hands it on."""
    return ground_draft_against_transcription(
        draft=_read(supplier=supplier, customer=customer),
        transcription=_transcription(page),
        taxpayer_tax_id=filer,
    )


def test_an_issued_document_derives_the_issued_direction() -> None:
    """The filer printed in the issuing party's block issued the invoice."""
    draft = _grounded(page=_ISSUED_PAGE, supplier=_FILER, customer=_OTHER)

    assert draft.suggested_kind is InvoiceKind.ISSUED


def test_a_received_document_derives_the_received_direction() -> None:
    """The other direction, which is the half a one-sided fixture would miss.

    A derivation hardcoded to ``ISSUED`` passes the case above and fails here,
    which is the whole reason both are asserted rather than one plus a negative.
    """
    draft = _grounded(page=_RECEIVED_PAGE, supplier=_OTHER, customer=_FILER)

    assert draft.suggested_kind is InvoiceKind.RECEIVED


@pytest.mark.parametrize(
    ("page", "supplier", "customer", "expected"),
    [
        (_ISSUED_PAGE, _FILER, _OTHER, InvoiceKind.ISSUED),
        (_RECEIVED_PAGE, _OTHER, _FILER, InvoiceKind.RECEIVED),
    ],
)
def test_the_basis_reaches_the_draft_beside_the_suggestion(
    page: str,
    supplier: str,
    customer: str,
    expected: InvoiceKind,
) -> None:
    """The operator is shown what the suggestion was read from, not only the answer.

    The review surface prints a basis off this envelope's note. A suggestion
    arriving with an empty basis is one the operator cannot contest, which is the
    state the field shipped in before it had a producer.
    """
    draft = _grounded(page=page, supplier=supplier, customer=customer)

    envelope = next(item for item in draft.provenance if item.field == "suggested_kind")
    assert draft.suggested_kind is expected
    assert envelope.origin is FieldOrigin.DERIVED
    assert envelope.grounding is FieldGroundingOutcome.RECONCILED
    assert envelope.derived_from == ("supplier_tax_id", "customer_tax_id")
    assert envelope.note.strip()


def test_a_document_naming_the_filer_as_both_parties_settles_nothing() -> None:
    """The autoconsumo-shaped document, and the reason containment was chosen.

    Comparing the two identity slots in table order would answer ``ISSUED`` here
    on slot order alone. Ley 37/1992 art. 9 is the one family where a taxpayer
    documents an operation directed at themselves, and it has no representation
    in this codebase -- so the honest answer is no direction and no claim, not a
    guess that happens to read as a verdict.
    """
    page = _ISSUED_PAGE.replace(f"NIF {_OTHER}", f"NIF {_FILER}")
    draft = _grounded(page=page, supplier=_FILER, customer=_FILER)

    derivation = derive_invoice_kind_from_filer_role(
        draft=_read(supplier=_FILER, customer=_FILER),
        transcription=_transcription(page),
        taxpayer_tax_id=_FILER,
    )

    assert draft.suggested_kind is None
    assert derivation.outcome is DirectionDerivationOutcome.FILER_ON_BOTH_SIDES
    assert not derivation.settled


def test_a_document_naming_neither_party_as_the_filer_settles_nothing() -> None:
    """The negative control. A derivation that answered here would answer anything."""
    page = _ISSUED_PAGE.replace(f"NIF {_FILER}", "NIF A58818501")
    draft = _grounded(page=page, supplier="A58818501", customer=_OTHER)

    assert draft.suggested_kind is None


def test_an_unsupplied_filer_identifier_is_reported_apart_from_an_absent_one() -> None:
    """Two different facts with two different owners, kept distinguishable.

    "We never asked" is ours to fix; "the document does not say" is the
    document's. Collapsing them would send an operator to re-read a page that
    was never the problem.
    """
    derivation = derive_invoice_kind_from_filer_role(
        draft=_read(supplier=_FILER, customer=_OTHER),
        transcription=_transcription(_ISSUED_PAGE),
        taxpayer_tax_id=None,
    )

    assert derivation.outcome is DirectionDerivationOutcome.NO_FILER_IDENTIFIER
    assert derivation.kind is None


def test_a_document_with_no_party_headings_settles_nothing() -> None:
    """Containment cannot be asked where the document states no partition.

    The fail-safe direction, and the case that separates this from a slot
    comparison: the slots still name the filer, and the answer is still withheld.
    """
    draft = ground_draft_against_transcription(
        draft=InvoiceDraft(supplier_tax_id=_FILER, customer_tax_id=_OTHER),
        transcription=_transcription(_ISSUED_PAGE),
        taxpayer_tax_id=_FILER,
    )

    assert draft.suggested_kind is None


def test_the_filers_identifier_printed_in_the_other_block_withholds_the_answer() -> None:
    """A repeated identifier must not launder itself into an attribution.

    The reader files the filer's id as the supplier's while the document prints
    it only under the customer heading -- a payment-details footer is the real
    shape of this. Reading the slot alone would answer ``ISSUED``; containment
    withholds, because the reader's assignment is precisely what is unverified.
    """
    derivation = derive_invoice_kind_from_filer_role(
        draft=_read(supplier=_FILER, customer=_OTHER),
        transcription=_transcription(_RECEIVED_PAGE),
        taxpayer_tax_id=_FILER,
    )

    assert derivation.outcome is DirectionDerivationOutcome.CONTAINMENT_UNCONFIRMED
    assert derivation.kind is None


def test_the_derivation_raises_no_finding_of_its_own() -> None:
    """A suggestion is not a defect. The comparison happens where the kind is known.

    Raising here would refuse every document the operator has not yet stated a
    direction for, which is every document at reading time.
    """
    draft = _grounded(page=_ISSUED_PAGE, supplier=_FILER, customer=_OTHER)

    assert DraftDiscrepancyKind.DIRECTION_CONTRADICTED not in [finding.kind for finding in draft.discrepancies]
    assert draft.suggested_kind is InvoiceKind.ISSUED


def test_the_role_table_covers_every_party_the_document_model_declares() -> None:
    """Derived from the party table rather than restated, so a third side cannot default.

    A hand-written mapping would keep answering for the two roles it knows while
    a newly declared party silently resolved to nothing.
    """
    from ..party_attribution import party_addresses

    assert set(DIRECTION_BY_FILER_ROLE) == {party.role for party in party_addresses()}
    assert set(DIRECTION_BY_FILER_ROLE.values()) == set(InvoiceKind)


def test_the_divergence_kind_is_enrolled_as_blocking() -> None:
    """The consuming half's axis membership, which is what makes it refuse.

    Asserted against the gate's own table rather than a copy: membership of that
    table IS the blocking property, so a member added and left unmapped fails the
    gate's import rather than passing here.
    """
    assert BLOCKING_REASON_BY_DISCREPANCY_KIND[DraftDiscrepancyKind.DIRECTION_CONTRADICTED] is not None
    assert set(BLOCKING_REASON_BY_DISCREPANCY_KIND) == set(DraftDiscrepancyKind)
