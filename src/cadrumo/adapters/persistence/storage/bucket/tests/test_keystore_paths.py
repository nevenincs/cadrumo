"""Tests for the keystore-separation invariant helpers.

The on-disk names below are written as literals **on purpose**, and must stay
that way. ``keystore_root`` and ``keystore_path`` resolve through
``storage_location(StorageCategory.BUCKET_KEYSTORE)``, so re-expressing the
expected side through the same accessor would move both sides of every
assertion together: the test would assert the accessor equals itself, pass
unconditionally, and stop defending anything.

What these assertions defend is the *on-disk contract* -- that a keystore
lands at ``<root>/keystore/<bucket-id>/``, a sibling of ``buckets/`` and never
nested beneath it. That is the separation a later unlock depends on, and it is
a fact about the filesystem rather than about the taxonomy. A change to the
declared subpath **should** red these tests; that is the signal, not a defect.

The literal is the independent oracle. Do not migrate it to the accessor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from ......core.errors import build_error_envelope
from .._keystore_paths import (
    keystore_path,
    keystore_root,
    keystore_sidecar_path,
    validate_keystore_separation,
)
from ..errors import BucketValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"keystore", "buckets", "db"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring.

``"db"`` is the bucket-relative on-disk segment
``test_rejects_keystore_paths_nested_under_bucket_storage`` asserts a
configured keystore must never sit beneath (``("buckets", "alpha", "db",
"stowaway")``), the same independent-oracle discipline as ``"keystore"`` and
``"buckets"``.
"""


def test_keystore_root_is_sibling_of_buckets(tmp_path: Path) -> None:
    assert keystore_root(tmp_path) == tmp_path / "keystore"
    assert keystore_root(tmp_path).parent == (tmp_path / "buckets").parent


def test_keystore_path_resolves_bucket_subdir(tmp_path: Path) -> None:
    assert keystore_path(tmp_path, "alpha") == tmp_path / "keystore" / "alpha"


def test_keystore_path_rejects_empty_bucket_id(tmp_path: Path) -> None:
    with pytest.raises(BucketValidationError, match="non-empty"):
        keystore_path(tmp_path, "")


def test_keystore_path_rejects_path_separator(tmp_path: Path) -> None:
    for bucket_id in ("a/b", "a\\b"):
        with pytest.raises(BucketValidationError, match="path separator"):
            keystore_path(tmp_path, bucket_id)


def test_default_separation_validates(tmp_path: Path) -> None:
    validate_keystore_separation(tmp_path, "alpha")


def test_rejects_keystore_paths_nested_under_bucket_storage(tmp_path: Path) -> None:
    cases = (
        (
            ("buckets", "alpha", "stowaway"),
            "buckets parent",
            {
                "reason": "under_buckets_parent",
                "surface": "bucket_keystore",
            },
        ),
        (
            ("buckets", "alpha", "db", "stowaway"),
            r"buckets parent|db dir",
            {
                "reason": "under_bucket_db_dir",
                "surface": "bucket_keystore",
            },
        ),
    )

    for relative_parts, error_match, expected_context in cases:
        bad = tmp_path.joinpath(*relative_parts)
        with pytest.raises(BucketValidationError, match=error_match) as excinfo:
            validate_keystore_separation(tmp_path, "alpha", configured_keystore=bad)

        message = str(excinfo.value)
        assert str(bad) not in message, relative_parts
        assert str(tmp_path) not in message, relative_parts
        assert excinfo.value.context == expected_context, relative_parts
        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_bucket_validation"


def test_external_path_passes_validation(tmp_path: Path) -> None:
    external = tmp_path / "elsewhere" / "alpha"
    validate_keystore_separation(tmp_path, "alpha", configured_keystore=external)


def test_sidecar_path_joins_filename_onto_keystore_directory(tmp_path: Path) -> None:
    result = keystore_sidecar_path(storage_root=tmp_path, bucket_id="alpha", filename="sidecar.json")
    assert result == tmp_path / "keystore" / "alpha" / "sidecar.json"


def test_sidecar_path_refuses_before_returning_when_separation_invalid(tmp_path: Path) -> None:
    # An empty bucket_id fails the separation check's own path derivation
    # (via keystore_path) before any sidecar path can be joined and
    # returned: the refusal happens inside validate-then-join, never after.
    with pytest.raises(BucketValidationError, match="non-empty"):
        keystore_sidecar_path(storage_root=tmp_path, bucket_id="", filename="sidecar.json")


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
