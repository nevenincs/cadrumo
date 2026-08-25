"""Atomic IO tests for the sole current active-profile pointer record."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from .. import BucketPointer, pointer_path, read_pointer, scan_directory, write_pointer

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _selected(bucket_id: str, revision: int) -> BucketPointer:
    return BucketPointer.selected(bucket_id=bucket_id, transition_revision=revision)


def test_round_trip_preserves_selection_and_coordinate(tmp_path: Path) -> None:
    pointer = _selected("alpha", 1)
    write_pointer(tmp_path, pointer)
    assert read_pointer(tmp_path) == pointer


def test_pointer_path_resolves_to_the_canonical_literal_shape(tmp_path: Path) -> None:
    assert pointer_path(tmp_path) == tmp_path / "active-profile"
    assert pointer_path(tmp_path / "nested" / "root") == tmp_path / "nested" / "root" / "active-profile"


def test_atomic_replacement_leaves_no_temporary_file(tmp_path: Path) -> None:
    write_pointer(tmp_path, _selected("alpha", 1))
    write_pointer(tmp_path, _selected("beta", 2))
    assert read_pointer(tmp_path) == _selected("beta", 2)
    assert scan_directory(tmp_path, pattern="*.tmp") == ()


def test_old_v1_document_is_refused_without_a_compatibility_reader(tmp_path: Path) -> None:
    pointer_path(tmp_path).write_text('bucket_id = "alpha"\nschema_version = 1\n', encoding="utf-8")
    with pytest.raises(ValidationError):
        read_pointer(tmp_path)


def test_link_like_pointer_is_refused_not_followed(tmp_path: Path) -> None:
    target = tmp_path / "outside-pointer"
    target.write_text('selection = "selected"\nbucket_id = "alpha"\ntransition_revision = 1\nschema_version = 2\n')
    pointer_path(tmp_path).symlink_to(target)
    with pytest.raises(OSError):
        read_pointer(tmp_path)
