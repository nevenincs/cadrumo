"""The timeline says whether a record added, changed or removed each field, so a first value is never "changed"."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    ActivityAssetTimelineChange,
    ActivityAssetTimelineChangeKind,
    timeline_change_kind,
)
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetEventKind

from .test_baja_correction import ASSET, baja_correction_without_baja, disposed
from .test_register import FIRST_YEAR, NAME, full_year, register_operations, register_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_KIND = ActivityAssetTimelineChangeKind


def test_every_field_a_created_element_first_states_is_added() -> None:
    operations, _ = register_operations()
    operations.create(register_revision(), NAME)

    created = next(event for event in operations.timeline(ASSET) if event.kind is ActivityAssetEventKind.REVISION)

    assert created.changes
    assert {change.kind for change in created.changes} == {_KIND.ADDED}


def test_a_field_whose_value_is_replaced_is_changed() -> None:
    operations, _ = register_operations()
    first = register_revision()
    operations.create(first, NAME)
    operations.correct(register_revision(number=2, supersedes=first.revision_id, in_service=date(FIRST_YEAR, 2, 1)))

    corrected = [e for e in operations.timeline(ASSET) if e.kind is ActivityAssetEventKind.REVISION][-1]

    assert {change.field: change.kind for change in corrected.changes}["in_service_date"] is _KIND.CHANGED


def test_a_claim_recorded_adds_its_amount() -> None:
    operations, _ = register_operations()
    operations.create(register_revision(), NAME)
    operations.record_claim(full_year(operations, FIRST_YEAR), creating_operation="test.year")

    claim = next(event for event in operations.timeline(ASSET) if event.kind is ActivityAssetEventKind.CLAIM)

    assert [change.kind for change in claim.changes] == [_KIND.ADDED]


def test_removing_a_baja_removes_the_values_it_stated() -> None:
    operations, _, baja = disposed()
    operations.correct(baja_correction_without_baja(baja))

    removed = [e for e in operations.timeline(ASSET) if e.kind is ActivityAssetEventKind.REVISION][-1]

    by_field = {change.field: change.kind for change in removed.changes}
    assert by_field["disposal.disposal_date"] is _KIND.REMOVED
    assert _KIND.ADDED not in by_field.values()


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        (None, "x", _KIND.ADDED),
        ("", "x", _KIND.ADDED),
        ("  ", "x", _KIND.ADDED),
        ("x", None, _KIND.REMOVED),
        ("x", "", _KIND.REMOVED),
        ("x", "y", _KIND.CHANGED),
    ],
)
def test_the_kind_is_read_from_the_two_sides_a_blank_counting_as_no_value(
    before: str | None, after: str | None, expected: ActivityAssetTimelineChangeKind
) -> None:
    assert timeline_change_kind(before, after) is expected
    assert ActivityAssetTimelineChange(field="x", before=before, after=after, kind=expected).kind is expected
    wrong = next(kind for kind in ActivityAssetTimelineChangeKind if kind is not expected)
    with pytest.raises(ValidationError):
        ActivityAssetTimelineChange(field="x", before=before, after=after, kind=wrong)
