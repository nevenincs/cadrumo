"""Extraction drafts roundtrip through real encrypted storage, or refuse.

A draft carries derived financial data -- supplier tax id, taxable base,
per-rate cuota -- so it crosses a persistence boundary and needs what every
persistence boundary here needs: a strict save-load-equality roundtrip against
the REAL adapter, plus an anti-tautology proof that a corrupted stored payload
makes the load fail rather than silently re-defaulting.

The line-carrying fields are populated NON-default throughout, and that is the
point rather than thoroughness. Those fields are exactly what this campaign
added to the draft; a fixture that left them empty would roundtrip a shape
indistinguishable from the pre-campaign one and prove nothing about the part
that is new.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._evidence_draft import InvoiceDraft, InvoiceDraftLine, InvoiceDraftRateBreakdown
from .._extraction_draft_store import (
    ExtractionDraftDocument,
    discard_extraction_draft,
    load_extraction_drafts,
    read_extraction_draft,
    write_extraction_draft,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"
_REFERENCE = "ev-structured-001"


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """A real isolated runtime profile: real key provider, real SQLite engine."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as resolved:
        yield resolved


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
    collapsed single-rate shape this campaign exists to remove, and would do it
    silently.
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

    from .._extraction_draft_store import StoredExtractionDraft

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

    from .._extraction_draft_store import StoredExtractionDraft

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
