"""Atomic IO tests for the sole current active-profile pointer record."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ..directory_scan import scan_directory
from ..bucket_pointer import BucketPointer, pointer_path, read_pointer, write_pointer

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


def test_write_retries_a_windows_sharing_refusal_during_atomic_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient open/replace refusal does not make a live reader reject publication."""
    from .. import atomic_write, bucket_pointer

    calls = 0
    original = atomic_write.atomic_write_hardened_bytes

    def temporarily_contended(path: Path, data: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError(13, "transient Windows sharing refusal")
        original(path, data)

    monkeypatch.setattr(bucket_pointer.sys, "platform", "win32")
    monkeypatch.setattr(atomic_write, "atomic_write_hardened_bytes", temporarily_contended)
    write_pointer(tmp_path, _selected("alpha", 1))

    assert calls == 2
    assert read_pointer(tmp_path) == _selected("alpha", 1)


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
