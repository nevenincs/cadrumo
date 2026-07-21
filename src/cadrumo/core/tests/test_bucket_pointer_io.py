"""Tests for the active-bucket pointer-file IO surface."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from .. import (
    BucketPointer,
    pointer_path,
    read_pointer,
    write_pointer,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _pointer(bucket_id: str) -> BucketPointer:
    return BucketPointer(bucket_id=bucket_id, schema_version=1)


def test_round_trip_preserves_pointer(tmp_path: Path) -> None:
    for root_parts, pointer in (
        ((), _pointer("alpha")),
        (("nested", "root"), _pointer("alpha")),
    ):
        root = tmp_path.joinpath(*root_parts)

        write_pointer(root, pointer)

        assert read_pointer(root) == pointer


def test_absent_pointer_returns_none(tmp_path: Path) -> None:
    assert read_pointer(tmp_path) is None


def test_write_is_atomic_no_tmp_lingers(tmp_path: Path) -> None:
    pointer = _pointer("alpha")

    write_pointer(tmp_path, pointer)

    target = pointer_path(tmp_path)
    assert target.is_file()
    assert list(target.parent.glob("*.tmp")) == []


def test_overwrite_replaces_previous_pointer(tmp_path: Path) -> None:
    first = _pointer("alpha")
    second = _pointer("beta")

    write_pointer(tmp_path, first)
    write_pointer(tmp_path, second)
    loaded = read_pointer(tmp_path)

    assert loaded == second


def test_torn_write_does_not_corrupt_existing_pointer(tmp_path: Path) -> None:
    """A partial payload at the .tmp sibling leaves the previous pointer intact."""

    good = _pointer("alpha")
    write_pointer(tmp_path, good)

    target = pointer_path(tmp_path)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text('bucket_id = "partial', encoding="utf-8")

    loaded = read_pointer(tmp_path)
    assert loaded == good


def test_read_rejects_unknown_key(tmp_path: Path) -> None:
    target = pointer_path(tmp_path)
    target.write_text(
        'bucket_id = "alpha"\nschema_version = 1\nstowaway = "x"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        read_pointer(tmp_path)
