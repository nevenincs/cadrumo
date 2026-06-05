"""Tests for the keystore-separation invariant helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from ......core.errors import build_error_envelope
from .._errors import BucketValidationError
from .._keystore_paths import (
    keystore_path,
    keystore_root,
    validate_keystore_separation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_keystore_root_is_sibling_of_buckets(tmp_path: Path) -> None:
    assert keystore_root(tmp_path) == tmp_path / "keystore"
    assert keystore_root(tmp_path).parent == (tmp_path / "buckets").parent


def test_keystore_path_resolves_bucket_subdir(tmp_path: Path) -> None:
    assert keystore_path(tmp_path, "alpha") == tmp_path / "keystore" / "alpha"


def test_keystore_path_rejects_empty_bucket_id(tmp_path: Path) -> None:
    with pytest.raises(BucketValidationError, match="non-empty"):
        keystore_path(tmp_path, "")


def test_keystore_path_rejects_path_separator(tmp_path: Path) -> None:
    with pytest.raises(BucketValidationError, match="path separator"):
        keystore_path(tmp_path, "a/b")
    with pytest.raises(BucketValidationError, match="path separator"):
        keystore_path(tmp_path, "a\\b")


def test_default_separation_validates(tmp_path: Path) -> None:
    validate_keystore_separation(tmp_path, "alpha")


def test_rejects_nesting_under_buckets_parent(tmp_path: Path) -> None:
    bad = tmp_path / "buckets" / "alpha" / "stowaway"
    with pytest.raises(BucketValidationError, match="buckets parent") as excinfo:
        validate_keystore_separation(tmp_path, "alpha", configured_keystore=bad)

    message = str(excinfo.value)
    assert str(bad) not in message
    assert str(tmp_path) not in message
    assert excinfo.value.context == {
        "reason": "under_buckets_parent",
        "surface": "bucket_keystore",
    }
    assert excinfo.value.translated_message == "errors.integrity.integrity_storage_bucket_validation"


def test_rejects_nesting_under_bucket_db_dir(tmp_path: Path) -> None:
    bad = tmp_path / "buckets" / "alpha" / "db" / "stowaway"
    with pytest.raises(BucketValidationError, match=r"buckets parent|db dir") as excinfo:
        validate_keystore_separation(tmp_path, "alpha", configured_keystore=bad)

    message = str(excinfo.value)
    assert str(bad) not in message
    assert str(tmp_path) not in message
    assert excinfo.value.context == {
        "reason": "under_bucket_db_dir",
        "surface": "bucket_keystore",
    }
    assert excinfo.value.translated_message == "errors.integrity.integrity_storage_bucket_validation"


def test_external_path_passes_validation(tmp_path: Path) -> None:
    external = tmp_path / "elsewhere" / "alpha"
    validate_keystore_separation(tmp_path, "alpha", configured_keystore=external)


def test_keystore_validation_error_envelope_is_localized_and_redacted(tmp_path: Path) -> None:
    bad = tmp_path / "buckets" / "alpha" / "stowaway"
    with pytest.raises(BucketValidationError) as excinfo:
        validate_keystore_separation(tmp_path, "alpha", configured_keystore=bad)

    envelope = build_error_envelope(excinfo.value)
    assert envelope.code == "INTEGRITY_STORAGE_BUCKET_VALIDATION"
    assert envelope.message
    assert envelope.context == {
        "reason": "under_buckets_parent",
        "surface": "bucket_keystore",
    }
    assert str(bad) not in envelope.model_dump_json()
    assert str(tmp_path) not in envelope.model_dump_json()
