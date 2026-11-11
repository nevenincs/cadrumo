"""The closed wire row carries exactly the operator row's facts; only the instant's type differs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import get_type_hints

import pytest

from ..enums import ReviewSeverity, ReviewState
from ..operator import ReviewQueueRow
from ..read_projections import ReviewQueueRowProjection, snapshot_review_row

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# ``ReviewQueueRow.since`` is a UtcInstant, whose validator is a custom core-schema
# hook that operation models may not carry; the wire row restates it as ``datetime``
# with a plain after-validator, so every other field must stay identical.
_RESTATED_FOR_THE_WIRE = frozenset({"since"})


def test_wire_row_has_the_operator_rows_fields_in_the_same_order() -> None:
    assert tuple(ReviewQueueRowProjection.model_fields) == tuple(ReviewQueueRow.model_fields)


def test_wire_row_field_types_and_defaults_match_except_the_restated_instant() -> None:
    row_hints = get_type_hints(ReviewQueueRow)
    wire_hints = get_type_hints(ReviewQueueRowProjection)
    for name, row_field in ReviewQueueRow.model_fields.items():
        if name in _RESTATED_FOR_THE_WIRE:
            continue
        wire_field = ReviewQueueRowProjection.model_fields[name]
        assert wire_hints[name] == row_hints[name], name
        assert wire_field.is_required() == row_field.is_required(), name
        assert wire_field.get_default(call_default_factory=True) == row_field.get_default(call_default_factory=True), (
            name
        )


def test_snapshot_copies_every_operator_row_fact() -> None:
    row = ReviewQueueRow(
        item_id="item-1",
        kind="transaction",
        affected_object_id="a" * 64,
        bucket_id="b" * 32,
        severity=ReviewSeverity.INFO,
        state=ReviewState.PENDING,
        blocking=False,
        current_owner_surface="ledger",
        canonical_next_command="aeat app ledger view",
        since=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        summary="needs review",
    )

    assert snapshot_review_row(row).model_dump() == row.model_dump()
