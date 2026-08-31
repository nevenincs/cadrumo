"""Extraction drafts roundtrip through real encrypted storage, or refuse.

A draft carries derived financial data -- supplier tax id, taxable base,
per-rate cuota -- so it crosses a persistence boundary and needs what every
persistence boundary here needs: a strict save-load-equality roundtrip against
the REAL adapter, plus an anti-tautology proof that a corrupted stored payload
makes the load fail rather than silently re-defaulting.

The line-carrying fields are populated NON-default throughout, and that is the
point rather than thoroughness. Those fields are exactly what was added to
the draft; a fixture that left them empty would roundtrip a shape
indistinguishable from the earlier shape and prove nothing about the part
that is new.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....tests.consent_profile_fixture import consent_profile

__all__ = ["consent_profile"]

from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ....tests.secure_sql import TestRuntimeProfile
from ..extraction_draft_store import (
    ExtractionDraftDocument,
    StoredExtractionDraft,
    discard_extraction_draft,
    load_extraction_drafts,
    read_extraction_draft,
    write_extraction_draft,
)
from ..invoice_draft_records import (
    FieldAmbiguityCandidate,
    FieldProvenance,
    InvoiceDraft,
    InvoiceDraftLine,
    InvoiceDraftRateBreakdown,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"
_REFERENCE = "ev-structured-001"


def _two_rate_draft() -> InvoiceDraft:
    """A draft with every campaign-added field populated non-default."""
    return InvoiceDraft(
        supplier_tax_id="ESB12345674",
        invoice_number="UBL-2024-0042",
        invoice_date="2024-11-15",
        taxable_base=Decimal("150.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("26.00"),
        grand_total=Decimal("176.00"),
        currency="EUR",
        recargo_amount=Decimal("5.20"),
        iva_category="domestic_reverse_charge",
        lines=(
            InvoiceDraftLine(
                description="Servicio de consultoria",
                quantity=Decimal("2"),
                unit_price=Decimal("50.00"),
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("21"),
                iva_amount=Decimal("21.00"),
            ),
            InvoiceDraftLine(
                description="Material de oficina",
                quantity=Decimal("5"),
                unit_price=Decimal("10.00"),
                taxable_base=Decimal("50.00"),
                iva_rate=Decimal("10"),
                iva_amount=Decimal("5.00"),
            ),
        ),
        iva_breakdown=(
            InvoiceDraftRateBreakdown(
                iva_rate=Decimal("21"),
                taxable_base=Decimal("100.00"),
                iva_amount=Decimal("21.00"),
            ),
            InvoiceDraftRateBreakdown(
                iva_rate=Decimal("10"),
                taxable_base=Decimal("50.00"),
                iva_amount=Decimal("5.00"),
            ),
        ),
        raw_text_length=2048,
    )


def test_a_line_carrying_draft_roundtrips_with_both_rates_intact(profile: TestRuntimeProfile) -> None:
    """Strict equality across the real boundary, lines and per-rate breakdown included.

    The multi-rate breakdown is what makes this worth storing at all: a draft
    that lost its second rate on the way to disk would reconstruct as the
    collapsed single-rate shape this test exists to guard against, and would
    do it silently.
    """
    written = write_extraction_draft(
        bucket_id=profile.bucket_id,
        evidence_reference=_REFERENCE,
        draft=_two_rate_draft(),
        extractor="en16931-ubl",
        settings=profile.settings,
    )

    reloaded = load_extraction_drafts(profile.bucket_id, profile.settings)

    assert reloaded == written, "the boundary must return exactly what crossed it"
    stored = reloaded.drafts[0]
    assert len(stored.draft.lines) == 2
    assert len(stored.draft.iva_breakdown) == 2
    rates = [b.iva_rate for b in stored.draft.iva_breakdown]
    # A missing rate is a real roundtrip failure, so it is asserted before the
    # sort rather than being allowed to surface as an ordering TypeError.
    assert all(rate is not None for rate in rates), f"a stored breakdown row lost its rate: {rates}"
    assert sorted(rate for rate in rates if rate is not None) == [Decimal("10"), Decimal("21")]
    assert stored.draft.recargo_amount == Decimal("5.20")
    assert stored.extractor == "en16931-ubl"


def test_a_correction_replaces_the_pending_draft_rather_than_forking_a_second(
    profile: TestRuntimeProfile,
) -> None:
    """One evidence reference, one pending review.

    Two drafts for one document are a re-read or a correction, not two
    proposals. Leaving both would give the confirm boundary two answers with
    nothing recording which the operator meant.
    """
    write_extraction_draft(
        bucket_id=profile.bucket_id,
        evidence_reference=_REFERENCE,
        draft=_two_rate_draft(),
        extractor="en16931-ubl",
        settings=profile.settings,
    )
    corrected = _two_rate_draft().model_copy(update={"supplier_tax_id": "ESX1234567L"})
    write_extraction_draft(
        bucket_id=profile.bucket_id,
        evidence_reference=_REFERENCE,
        draft=corrected,
        extractor="operator-correction",
        settings=profile.settings,
    )
    write_extraction_draft(
        bucket_id=profile.bucket_id,
        evidence_reference="ev-other",
        draft=_two_rate_draft(),
        extractor="en16931-cii",
        settings=profile.settings,
    )

    document = load_extraction_drafts(profile.bucket_id, profile.settings)

    assert len(document.drafts) == 2, "one pending draft per evidence reference"
    pending = read_extraction_draft(
        bucket_id=profile.bucket_id,
        evidence_reference=_REFERENCE,
        settings=profile.settings,
    )
    assert pending is not None
    assert pending.draft.supplier_tax_id == "ESX1234567L"
    assert pending.extractor == "operator-correction"


def test_discarding_a_draft_leaves_its_siblings_untouched(profile: TestRuntimeProfile) -> None:
    """A confirmed draft is dropped; a pending one for another document survives.

    A confirmed document that still shows a pending review invites a second
    confirm of the same evidence, so the discard must happen -- but it must not
    take unrelated reviews with it.
    """
    for reference in (_REFERENCE, "ev-other"):
        write_extraction_draft(
            bucket_id=profile.bucket_id,
            evidence_reference=reference,
            draft=_two_rate_draft(),
            extractor="en16931-ubl",
            settings=profile.settings,
        )

    remaining = discard_extraction_draft(
        bucket_id=profile.bucket_id,
        evidence_reference=_REFERENCE,
        settings=profile.settings,
    )

    assert [row.evidence_reference for row in remaining.drafts] == ["ev-other"]
    assert (
        read_extraction_draft(
            bucket_id=profile.bucket_id,
            evidence_reference=_REFERENCE,
            settings=profile.settings,
        )
        is None
    )


def test_deleting_a_persisted_field_makes_the_load_refuse() -> None:
    """Anti-tautology: corrupt the stored payload, prove the load notices.

    If this passed while the boundary was broken, every roundtrip above would be
    tautological. The strict model must REFUSE a payload missing a field rather
    than re-defaulting it, because a silent re-default is exactly how a dropped
    field escapes a roundtrip test.
    """
    import json
    from datetime import UTC, datetime

    from pydantic import ValidationError

    from ..extraction_draft_store import StoredExtractionDraft

    payload = ExtractionDraftDocument(
        bucket_id=_BUCKET_ID,
        drafts=(
            StoredExtractionDraft(
                evidence_reference=_REFERENCE,
                draft=_two_rate_draft(),
                extractor="en16931-ubl",
                drafted_at=datetime(2024, 11, 15, 9, 0, tzinfo=UTC),
            ),
        ),
    )
    # A JSON round-trip, not `model_validate` on a dumped dict. The model is
    # strict, so a dumped dict presents lists where tuples are declared and is
    # refused for THAT reason -- which would make this assertion pass with
    # nothing deleted at all. The refusal has to be attributable to the missing
    # field or it proves nothing.
    intact = json.loads(payload.model_dump_json())
    assert ExtractionDraftDocument.model_validate_json(json.dumps(intact)) == payload, (
        "positive control: the intact payload must survive the round-trip"
    )

    corrupted = json.loads(payload.model_dump_json())
    del corrupted["drafts"][0]["extractor"]

    with pytest.raises(ValidationError, match="extractor"):
        ExtractionDraftDocument.model_validate_json(json.dumps(corrupted))


def test_a_dropped_line_set_is_not_silently_re_defaulted_to_empty() -> None:
    """The campaign-added fields specifically must survive or fail loudly.

    ``lines`` and ``iva_breakdown`` both default to an empty tuple, which makes
    them the fields most able to vanish unnoticed: a boundary that dropped them
    would reload a structurally valid draft carrying no rates at all. Round-trip
    the serialized form and assert they came back, rather than trusting that a
    defaulted field and a persisted one look the same.
    """
    from datetime import UTC, datetime

    from ..extraction_draft_store import StoredExtractionDraft

    payload = ExtractionDraftDocument(
        bucket_id=_BUCKET_ID,
        drafts=(
            StoredExtractionDraft(
                evidence_reference=_REFERENCE,
                draft=_two_rate_draft(),
                extractor="en16931-ubl",
                drafted_at=datetime(2024, 11, 15, 9, 0, tzinfo=UTC),
            ),
        ),
    )

    revived = ExtractionDraftDocument.model_validate_json(payload.model_dump_json())

    assert revived == payload
    assert len(revived.drafts[0].draft.lines) == 2
    assert len(revived.drafts[0].draft.iva_breakdown) == 2


def _provenance_bearing_draft() -> InvoiceDraft:
    """A draft whose per-field provenance is populated OFF its defaults.

    Every provenance axis is set to a non-default value, and the three envelopes
    deliberately cover different outcomes: one reconciled and anchored, one
    ambiguous carrying competing candidates, one contradicted carrying the note
    that explains what disagreed. A fixture that used the same outcome three
    times could not tell a boundary that persists one envelope shape from one
    that persists all of them.
    """
    return InvoiceDraft(
        supplier_tax_id="ESB12345674",
        supplier_name="Proveedor Ejemplo SL",
        invoice_number="PROV-2024-0001",
        invoice_date="2024-11-15",
        taxable_base=Decimal("150.00"),
        iva_amount=Decimal("26.00"),
        grand_total=Decimal("176.00"),
        currency="EUR",
        provenance=(
            FieldProvenance(
                field="taxable_base",
                origin=FieldOrigin.EXACT_STRUCTURED,
                grounding=FieldGroundingOutcome.RECONCILED,
                anchor="150,00",
                note="reconciles against the per-rate breakdown",
            ),
            FieldProvenance(
                field="supplier_tax_id",
                origin=FieldOrigin.TEXT_LAYER,
                grounding=FieldGroundingOutcome.AMBIGUOUS,
                anchor="ESB12345674",
                candidates=(
                    FieldAmbiguityCandidate(value="ESB12345674", anchor="NIF: ESB12345674", note="header block"),
                    FieldAmbiguityCandidate(value="ESB87654321", anchor="ESB87654321", note="footer block"),
                ),
                note="two tax ids printed on the same document",
            ),
            FieldProvenance(
                field="grand_total",
                origin=FieldOrigin.VISION,
                grounding=FieldGroundingOutcome.CONTRADICTED,
                anchor="176,00",
                note="printed total disagrees with base plus cuota",
            ),
        ),
    )


def test_field_provenance_survives_the_real_encrypted_boundary(profile: TestRuntimeProfile) -> None:
    """Provenance crosses the encrypted store intact, by strict equality.

    Provenance is the part a reader cannot reconstruct. A value that survives
    persistence while its origin and grounding do not looks identical to a value
    that was read exactly -- so an ambiguous or contradicted reading silently
    becomes a confident one, and the operator loses the reason to check it.

    Asserted against the real encrypted namespace rather than a JSON round trip:
    the serializer is not the boundary that matters, the store is, and a field
    the repository declines to persist would round-trip through JSON perfectly.
    """
    written = write_extraction_draft(
        bucket_id=profile.bucket_id,
        evidence_reference=_REFERENCE,
        draft=_provenance_bearing_draft(),
        extractor="en16931-ubl",
        settings=profile.settings,
    )

    reloaded = load_extraction_drafts(profile.bucket_id, profile.settings)

    assert reloaded == written, "the boundary must return exactly what crossed it"
    stored = reloaded.drafts[0].draft
    assert len(stored.provenance) == 3, f"an envelope was dropped in transit: {stored.provenance}"

    by_field = {entry.field: entry for entry in stored.provenance}
    assert by_field["taxable_base"].grounding is FieldGroundingOutcome.RECONCILED
    assert by_field["taxable_base"].origin is FieldOrigin.EXACT_STRUCTURED

    # The ambiguous envelope is the one worth checking in detail: its competing
    # candidates are what an operator adjudicates, and they are nested a level
    # deeper than every other provenance field, so a boundary that flattens
    # nested records loses exactly this and nothing else.
    ambiguous = by_field["supplier_tax_id"]
    assert ambiguous.grounding is FieldGroundingOutcome.AMBIGUOUS
    assert len(ambiguous.candidates) == 2
    assert {candidate.value for candidate in ambiguous.candidates} == {"ESB12345674", "ESB87654321"}
    assert all(candidate.note for candidate in ambiguous.candidates), "a candidate lost the note that distinguishes it"

    contradicted = by_field["grand_total"]
    assert contradicted.grounding is FieldGroundingOutcome.CONTRADICTED
    assert contradicted.origin is FieldOrigin.VISION
    assert contradicted.note


def test_deleting_a_persisted_provenance_field_makes_the_load_refuse() -> None:
    """Anti-tautology: the roundtrip above must be capable of failing.

    Every assertion in this module compares what came out against what went in,
    which stays green if the boundary is a pass-through that never validates.
    Removing a required field from the serialized payload must redden the load;
    if it does not, the roundtrip proves only that two objects are equal, not
    that the store enforces the shape it claims to.

    ``grounding`` is chosen because it is the field an absent value would be
    most quietly wrong about: a provenance envelope that loads with a defaulted
    outcome reads as a verified value rather than an unverified one.
    """
    import json

    from pydantic import ValidationError

    payload = ExtractionDraftDocument(
        bucket_id=_BUCKET_ID,
        drafts=(
            StoredExtractionDraft(
                evidence_reference=_REFERENCE,
                draft=_provenance_bearing_draft(),
                extractor="en16931-ubl",
                drafted_at=datetime(2024, 11, 15, 9, 0, tzinfo=UTC),
            ),
        ),
    )
    corrupted = json.loads(payload.model_dump_json())
    del corrupted["drafts"][0]["draft"]["provenance"][0]["grounding"]

    # Re-validated as JSON TEXT, not as a Python dict. The models are strict, so
    # a dict round trip refuses the dumped Decimal as a string long before it
    # reaches the deleted field -- the test would go green on an unrelated
    # refusal and prove nothing about provenance. Only the genuine JSON parse
    # path reaches the field this test is about.
    with pytest.raises(ValidationError, match="grounding"):
        ExtractionDraftDocument.model_validate_json(json.dumps(corrupted))
