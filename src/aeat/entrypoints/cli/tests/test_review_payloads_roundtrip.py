"""Strict roundtrip across the ``aeat review`` CLI JSON envelope.

``review queue`` and ``review view`` used to emit
``model_dump(mode="json")`` on application-side records that were not
``@register_schema``-decorated. The JSON-contract test suite could
therefore not enumerate the surface; tooling parsing the JSON had no
stability contract.

These tests pin the typed payload contract: a populated
``ReviewQueueRowPayload`` survives ``model_dump_json`` /
``model_validate_json`` with strict pydantic equality, and the typed
``ReviewQueueResult`` / ``ReviewViewResult`` envelopes preserve the
row tuple end-to-end.
"""

from __future__ import annotations

import pytest

from ....core import Period
from .._review_payloads import (
    ReviewQueueResult,
    ReviewQueueRowPayload,
    ReviewViewResult,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _populated_row(item_id: str = "review-001") -> ReviewQueueRowPayload:
    """Build a row with every defaultable field set to a non-default value."""

    return ReviewQueueRowPayload(
        item_id=item_id,
        kind="modelo_finding",
        source_kind="ledger_transaction",
        affected_object_id="draft-abc",
        bucket_id="b" * 32,
        modelo="303",
        period=str(Period.from_year_and_code(2025, "1T")),
        severity="HIGH",
        state="PENDING",
        blocking=True,
        reason="missing required casilla",
        current_owner_surface="app modelo",
        canonical_next_command="aeat app modelo work calculate draft-abc",
        since="2025-04-20T12:00:00+00:00",
        summary="modelo 303 draft is missing iva.devengado",
        legal_refs=("liva.art-21", "liva.art-94"),
    )


def test_review_queue_row_payload_roundtrips_strictly() -> None:
    """Every typed field survives ``model_dump_json`` / ``model_validate_json``."""

    original = _populated_row()
    roundtripped = ReviewQueueRowPayload.model_validate_json(original.model_dump_json())

    assert roundtripped == original
    # Per-field witnesses for the legal-grounding tuple (the audit's
    # core ask: every operator-facing JSON surface must carry the
    # regulatory grounding tuple).
    assert roundtripped.legal_refs == ("liva.art-21", "liva.art-94")
    assert roundtripped.blocking is True
    assert roundtripped.severity == "HIGH"


def test_review_queue_result_envelope_roundtrips() -> None:
    """The ``review queue`` JSON envelope preserves the rows tuple."""

    original = ReviewQueueResult(
        rows=(_populated_row("a"), _populated_row("b")),
    )
    roundtripped = ReviewQueueResult.model_validate_json(original.model_dump_json())

    assert roundtripped == original
    assert roundtripped.operation == "review.queue"
    assert len(roundtripped.rows) == 2
    assert roundtripped.rows[0].item_id == "a"
    assert roundtripped.rows[1].item_id == "b"


def test_review_view_envelope_roundtrips() -> None:
    """The ``review view`` JSON envelope preserves a single row."""

    original = ReviewViewResult(row=_populated_row("only"))
    roundtripped = ReviewViewResult.model_validate_json(original.model_dump_json())

    assert roundtripped == original
    assert roundtripped.operation == "review.view"
    assert roundtripped.row.item_id == "only"
    assert roundtripped.row.legal_refs == ("liva.art-21", "liva.art-94")


def test_review_payloads_reject_unknown_outer_keys() -> None:
    """Both envelopes inherit ``extra='forbid'`` from OutputSchema.

    A producer that emits an extra top-level key would silently land
    in caller payloads under permissive schemas. The strict envelope
    rejects them at parse time.
    """

    from pydantic import ValidationError as _PydValidationError

    serialized = ReviewViewResult(row=_populated_row()).model_dump(mode="json")
    serialized["extra_marker"] = "leak"  # not in the typed envelope
    with pytest.raises(_PydValidationError):
        ReviewViewResult.model_validate(serialized)
