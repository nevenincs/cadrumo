"""Tests for the keystore-separation invariant helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.bucket._keystore_paths import (
    keystore_path,
    keystore_root,
    validate_keystore_separation,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def test_keystore_root_is_sibling_of_buckets(tmp_path: Path) -> None:
    assert keystore_root(tmp_path) == tmp_path / "keystore"
    assert keystore_root(tmp_path).parent == (tmp_path / "buckets").parent


def test_keystore_path_resolves_bucket_subdir(tmp_path: Path) -> None:
    assert keystore_path(tmp_path, "alpha") == tmp_path / "keystore" / "alpha"


def test_keystore_path_rejects_empty_bucket_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        keystore_path(tmp_path, "")


def test_keystore_path_rejects_path_separator(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="path separator"):
        keystore_path(tmp_path, "a/b")
    with pytest.raises(ValueError, match="path separator"):
        keystore_path(tmp_path, "a\\b")


def test_default_separation_validates(tmp_path: Path) -> None:
    validate_keystore_separation(tmp_path, "alpha")


def test_rejects_nesting_under_buckets_parent(tmp_path: Path) -> None:
    bad = tmp_path / "buckets" / "alpha" / "stowaway"
    with pytest.raises(ValueError, match="buckets parent"):
        validate_keystore_separation(tmp_path, "alpha", configured_keystore=bad)


def test_rejects_nesting_under_bucket_db_dir(tmp_path: Path) -> None:
    bad = tmp_path / "buckets" / "alpha" / "db" / "stowaway"
    with pytest.raises(ValueError, match=r"buckets parent|db dir"):
        validate_keystore_separation(tmp_path, "alpha", configured_keystore=bad)


def test_external_path_passes_validation(tmp_path: Path) -> None:
    external = tmp_path / "elsewhere" / "alpha"
    validate_keystore_separation(tmp_path, "alpha", configured_keystore=external)
