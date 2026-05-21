"""Tests for the manifest atomic-write and strict-read surface."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aeat.adapters.persistence.storage.bucket._layout import provision_bucket_directory
from aeat.adapters.persistence.storage.bucket._manifest import (
    BucketLifecycleStatus,
    BucketManifest,
    ManifestKdfParams,
)
from aeat.adapters.persistence.storage.bucket._manifest_io import (
    manifest_path,
    read_manifest,
    write_manifest,
)
from aeat.adapters.persistence.storage.errors import StorageValidationError

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _fixture_manifest(*, last_unlocked: bool = True) -> BucketManifest:
    kdf = ManifestKdfParams(
        algorithm="argon2id",
        version=19,
        memory_cost=19_456,
        time_cost=2,
        parallelism=1,
        salt=b"0123456789abcdef",
        output_length=32,
    )
    return BucketManifest(
        bucket_id="alpha",
        label="Alpha bucket",
        created_at=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
        last_unlocked_at=datetime(2026, 5, 14, 13, 30, 0, tzinfo=UTC) if last_unlocked else None,
        kdf_params=kdf,
        recovery_enrolled=True,
        schema_version=1,
        status=BucketLifecycleStatus.ACTIVE,
    )


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    manifest = _fixture_manifest()

    write_manifest(paths, manifest)
    loaded = read_manifest(paths)

    assert loaded == manifest
    assert loaded.kdf_params.salt == manifest.kdf_params.salt


def test_round_trip_preserves_absent_last_unlocked(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    manifest = _fixture_manifest(last_unlocked=False)

    write_manifest(paths, manifest)
    loaded = read_manifest(paths)

    assert loaded.last_unlocked_at is None
    assert loaded == manifest


def test_write_is_atomic_no_tmp_file_lingers(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    manifest = _fixture_manifest()

    write_manifest(paths, manifest)

    target = manifest_path(paths)
    assert target.is_file()
    assert not target.with_suffix(target.suffix + ".tmp").exists()


def test_overwrite_replaces_previous_manifest(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    first = _fixture_manifest()
    second = first.model_copy(update={"label": "Renamed"})

    write_manifest(paths, first)
    write_manifest(paths, second)
    loaded = read_manifest(paths)

    assert loaded.label == "Renamed"


def test_read_rejects_unknown_key(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    write_manifest(paths, _fixture_manifest())

    target = manifest_path(paths)
    text = target.read_text(encoding="utf-8")
    target.write_text(text + 'stowaway = "x"\n', encoding="utf-8")

    with pytest.raises(ValidationError):
        read_manifest(paths)


def test_read_rejects_missing_status_key(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    write_manifest(paths, _fixture_manifest())

    target = manifest_path(paths)
    text = target.read_text(encoding="utf-8")
    target.write_text(
        "\n".join(line for line in text.splitlines() if not line.startswith("status = ")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(StorageValidationError, match="lifecycle status"):
        read_manifest(paths)


def test_read_raises_when_manifest_absent(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")

    with pytest.raises(FileNotFoundError):
        read_manifest(paths)


def test_torn_write_does_not_corrupt_existing_manifest(tmp_path: Path) -> None:
    """A crash before os.replace leaves the previous good manifest intact.

    Simulated by writing a good manifest, then dropping a partial payload at
    the ``.tmp`` sibling (as if the process crashed before the rename), and
    finally re-reading; the canonical manifest must still validate.
    """

    paths = provision_bucket_directory(tmp_path, "alpha")
    good = _fixture_manifest()
    write_manifest(paths, good)

    target = manifest_path(paths)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text('bucket_id = "partial', encoding="utf-8")

    loaded = read_manifest(paths)
    assert loaded == good
