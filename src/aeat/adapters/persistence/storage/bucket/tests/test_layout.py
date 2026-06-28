"""Tests for the per-bucket directory provisioning surface."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ......core.errors import build_error_envelope
from .._errors import BucketAlreadyPresentError, BucketValidationError
from .._layout import (
    BucketPaths,
    bucket_paths,
    provision_bucket_directory,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_provision_creates_three_subdirectories(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")

    assert paths.bucket_dir == tmp_path / "buckets" / "alpha"
    assert paths.db_dir.is_dir()
    assert paths.blobs_dir.is_dir()
    assert paths.audit_dir.is_dir()
    assert paths.db_dir == paths.bucket_dir / "db"
    assert paths.blobs_dir == paths.bucket_dir / "blobs"
    assert paths.audit_dir == paths.bucket_dir / "audit"


def test_provision_is_fail_closed_on_existing_bucket(tmp_path: Path) -> None:
    provision_bucket_directory(tmp_path, "alpha")

    with pytest.raises(BucketAlreadyPresentError) as excinfo:
        provision_bucket_directory(tmp_path, "alpha")

    assert excinfo.value.bucket_id == "alpha"
    assert excinfo.value.context == {"bucket_id": "alpha"}
    assert str(tmp_path) not in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, FileExistsError)


def test_existing_bucket_error_envelope_is_localized_and_redacted(tmp_path: Path) -> None:
    provision_bucket_directory(tmp_path, "alpha")

    with pytest.raises(BucketAlreadyPresentError) as excinfo:
        provision_bucket_directory(tmp_path, "alpha")

    envelope = build_error_envelope(excinfo.value)
    assert envelope.code == "REFUSED_STORAGE_BUCKET_ALREADY_PRESENT"
    assert envelope.message
    assert envelope.context == {"bucket_id": "alpha"}
    assert str(tmp_path) not in envelope.model_dump_json()


def test_buckets_parent_file_collision_is_typed_and_redacted(tmp_path: Path) -> None:
    (tmp_path / "buckets").write_text("not a directory")

    with pytest.raises(BucketAlreadyPresentError) as excinfo:
        provision_bucket_directory(tmp_path, "alpha")

    assert excinfo.value.bucket_id == "alpha"
    assert str(tmp_path) not in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, FileExistsError)
    envelope = build_error_envelope(excinfo.value)
    assert envelope.code == "REFUSED_STORAGE_BUCKET_ALREADY_PRESENT"
    assert str(tmp_path) not in envelope.model_dump_json()


def test_provision_rejects_empty_bucket_id(tmp_path: Path) -> None:
    with pytest.raises(BucketValidationError, match="non-empty"):
        provision_bucket_directory(tmp_path, "")


def test_provision_rejects_path_separator_in_bucket_id(tmp_path: Path) -> None:
    with pytest.raises(BucketValidationError, match="path separator"):
        provision_bucket_directory(tmp_path, "a/b")
    with pytest.raises(BucketValidationError, match="path separator"):
        provision_bucket_directory(tmp_path, "a\\b")


def test_bucket_paths_is_pure_no_filesystem_side_effects(tmp_path: Path) -> None:
    paths = bucket_paths(tmp_path, "alpha")

    assert not paths.bucket_dir.exists()
    assert not paths.db_dir.exists()
    assert not paths.blobs_dir.exists()
    assert not paths.audit_dir.exists()
    assert isinstance(paths, BucketPaths)


def test_bucket_paths_record_is_strict_frozen(tmp_path: Path) -> None:
    paths = bucket_paths(tmp_path, "alpha")

    with pytest.raises(ValidationError):
        paths.__class__.model_validate({**paths.model_dump(), "stowaway": True})


def test_bucket_paths_record_is_immutable(tmp_path: Path) -> None:
    paths = bucket_paths(tmp_path, "alpha")

    with pytest.raises(ValidationError):
        paths.bucket_id = "other"


def test_two_buckets_share_buckets_parent(tmp_path: Path) -> None:
    alpha = provision_bucket_directory(tmp_path, "alpha")
    beta = provision_bucket_directory(tmp_path, "beta")

    assert alpha.bucket_dir.parent == beta.bucket_dir.parent
    assert alpha.bucket_dir.parent == tmp_path / "buckets"
