"""Strict current-only tests for the active-profile pointer record."""

from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError

from ..bucket_pointer import POINTER_SCHEMA_VERSION, BucketPointer, pointer_path, read_pointer, write_pointer

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_selected_and_absent_records_round_trip_through_the_real_file(tmp_path) -> None:
    selected = BucketPointer.selected(bucket_id="bucket-001", transition_revision=7)
    absent = BucketPointer.absent(transition_revision=8)

    write_pointer(tmp_path, selected)
    assert read_pointer(tmp_path) == selected
    write_pointer(tmp_path, absent)
    assert read_pointer(tmp_path) == absent
    assert pointer_path(tmp_path).is_file(), "clear-state lineage must be a persisted tombstone"


def test_absent_file_observes_as_initial_absent_coordinate(tmp_path) -> None:
    assert read_pointer(tmp_path) == BucketPointer.absent(transition_revision=0)


def test_record_requires_current_schema_selection_and_transition_revision() -> None:
    current_schema = get_args(BucketPointer.model_fields["schema_version"].annotation)
    assert current_schema == (POINTER_SCHEMA_VERSION,)

    for payload in (
        {"bucket_id": "bucket-001", "schema_version": 1},
        {"selection": "selected", "bucket_id": "bucket-001", "schema_version": 2},
        {"selection": "absent", "bucket_id": "bucket-001", "transition_revision": 1, "schema_version": 2},
        {"selection": "selected", "bucket_id": None, "transition_revision": 1, "schema_version": 2},
    ):
        with pytest.raises(ValidationError):
            BucketPointer.model_validate(payload)


def test_deleted_transition_revision_refuses_at_the_real_read_boundary(tmp_path) -> None:
    pointer = BucketPointer.selected(bucket_id="bucket-001", transition_revision=1)
    write_pointer(tmp_path, pointer)
    target = pointer_path(tmp_path)
    stripped = "".join(
        line
        for line in target.read_text(encoding="utf-8").splitlines(keepends=True)
        if not line.startswith("transition_revision")
    )
    target.write_text(stripped, encoding="utf-8")

    with pytest.raises(ValidationError):
        read_pointer(tmp_path)


def test_old_byte_capture_restore_and_unlink_clear_api_is_not_public() -> None:
    from ... import core

    for retired_name in ("capture_pointer", "restore_pointer", "clear_pointer"):
        assert retired_name not in core.__all__
        assert not hasattr(core, retired_name)
