"""Bucket-manifest version gate: ceiling with a durability floor.

Completes the tier set beside the secure-object, bundle and archive lineage
gates. Until this landed the manifest was the only persisted format carrying a
``schema_version`` field and NO version gate of any kind: the value was
hardcoded at create, passed through unchanged by five lifecycle writers, and
read back with no check, so a manifest written by a newer application was
accepted silently.

That silence was not inert. The manifest is the registration record a bucket is
recognised by, its ``key_schedule`` field selects how the bucket's data key is
handled, and its plaintext ``status`` is the tombstone mirror every operator
surface reads without unlocking the bucket. The format's one historical bump
encoded exactly a key-schedule change, and it rode an unrelated routing commit —
the axis has already moved once unobserved.

The manifest tier carries NO upgrade dispatch, so like the archive tier this is a
range gate only and the floor-equals-current pin is what keeps that honest: a
version bump that holds the floor without landing a version-aware reader would
pass green while the reader misinterprets the older layout.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......core import COMPATIBILITY_REGIME, RELEASED_FORMAT_FLOORS, expected_floor
from ......core.external_constants import UTF_8_ENCODING
from ......domain.user_profile import UserProfileStatus
from ...errors import StorageValidationError
from .._layout import provision_bucket_directory
from .._manifest import (
    BUCKET_MANIFEST_DURABILITY_FLOOR,
    BUCKET_MANIFEST_SCHEMA_VERSION,
    BucketManifest,
    ManifestKdfParams,
)
from .._manifest_io import ensure_manifest_schema_readable, manifest_path, read_manifest, write_manifest

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_FORMAT_KEY = "bucket_manifest"


def _manifest() -> BucketManifest:
    return BucketManifest(
        bucket_id=_BUCKET_ID,
        label="Lineage Operator",
        created_at=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
        last_unlocked_at=None,
        kdf_params=ManifestKdfParams(
            algorithm="argon2id",
            version=19,
            memory_cost=19_456,
            time_cost=2,
            parallelism=1,
            salt=b"0123456789abcdef",
            output_length=32,
        ),
        recovery_enrolled=False,
        schema_version=BUCKET_MANIFEST_SCHEMA_VERSION,
        status=UserProfileStatus.ACTIVE,
    )


def test_floor_does_not_exceed_current_version() -> None:
    assert BUCKET_MANIFEST_DURABILITY_FLOOR <= BUCKET_MANIFEST_SCHEMA_VERSION


def test_floor_matches_the_regime_expected_floor() -> None:
    """The manifest floor tracks the regime-switched compatibility policy.

    While ``PRE_RELEASE`` the expected floor IS the current version. Post-flip it
    becomes the frozen released value and this assertion demands the floor stay
    pinned there. Enrolling this format is what lets the checkpoint freeze a
    floor for it at all — the two enrollment gates previously contradicted each
    other because this format was declared durable while being absent from the
    reference set they validated against.
    """
    assert (
        expected_floor(
            COMPATIBILITY_REGIME,
            _FORMAT_KEY,
            BUCKET_MANIFEST_SCHEMA_VERSION,
            RELEASED_FORMAT_FLOORS,
        )
        == BUCKET_MANIFEST_DURABILITY_FLOOR
    ), (
        "bucket-manifest durability floor diverges from the regime-expected floor: while pre-release "
        "it must equal the current manifest version, because this tier has no upgrade dispatch and a "
        "lower floor would have no mechanism behind it; either raise the floor in the same change "
        "(dropping older manifests) or land a version-aware reader with an old-manifest restorability test"
    )


def test_every_version_from_floor_to_current_is_readable() -> None:
    for version in range(BUCKET_MANIFEST_DURABILITY_FLOOR, BUCKET_MANIFEST_SCHEMA_VERSION + 1):
        ensure_manifest_schema_readable(version)


def test_a_future_manifest_version_is_refused_as_a_newer_application() -> None:
    """Above the ceiling is recoverable: the operator updates the application."""
    with pytest.raises(StorageValidationError) as excinfo:
        ensure_manifest_schema_readable(BUCKET_MANIFEST_SCHEMA_VERSION + 1)
    assert excinfo.value.translated_message == "errors.integrity.integrity_storage_bucket_manifest_version_from_future"
    assert excinfo.value.context == {
        "schema_version": str(BUCKET_MANIFEST_SCHEMA_VERSION + 1),
        "max_supported": str(BUCKET_MANIFEST_SCHEMA_VERSION),
    }


def test_a_below_floor_manifest_version_is_refused_as_predating_the_guarantee() -> None:
    """Below the floor is a different fact and carries a different message.

    Distinguished deliberately rather than collapsed: telling an operator whose
    bucket is NEWER that their data is too old would be both wrong and alarming,
    and the two cases have opposite remedies.
    """
    with pytest.raises(StorageValidationError) as excinfo:
        ensure_manifest_schema_readable(BUCKET_MANIFEST_DURABILITY_FLOOR - 1)
    assert excinfo.value.translated_message == "errors.integrity.integrity_storage_bucket_manifest_version_below_floor"
    assert excinfo.value.context == {
        "schema_version": str(BUCKET_MANIFEST_DURABILITY_FLOOR - 1),
        "durability_floor": str(BUCKET_MANIFEST_DURABILITY_FLOOR),
    }


def test_the_read_path_applies_the_gate_to_a_real_on_disk_manifest(tmp_path: Path) -> None:
    """The gate is wired into ``read_manifest``, not merely available beside it.

    Written through the real writer and then edited on disk to carry a future
    version — the shape a newer application would actually leave behind. Without
    this the range gate could be correct and simply never called, which is how
    this format spent its whole life with a version field and no check.
    """
    paths = provision_bucket_directory(tmp_path, _BUCKET_ID)
    write_manifest(paths, _manifest())
    target = manifest_path(paths)
    skewed = target.read_text(encoding=UTF_8_ENCODING).replace(
        f"schema_version = {BUCKET_MANIFEST_SCHEMA_VERSION}",
        f"schema_version = {BUCKET_MANIFEST_SCHEMA_VERSION + 1}",
    )
    assert f"schema_version = {BUCKET_MANIFEST_SCHEMA_VERSION + 1}" in skewed, "the version mutation did not apply"
    target.write_text(skewed, encoding=UTF_8_ENCODING)

    with pytest.raises(StorageValidationError) as excinfo:
        read_manifest(paths)
    assert excinfo.value.translated_message == "errors.integrity.integrity_storage_bucket_manifest_version_from_future"


def test_a_current_version_manifest_still_reads(tmp_path: Path) -> None:
    """Anti-tautology: the refusals above discriminate rather than always-refuse."""
    paths = provision_bucket_directory(tmp_path, _BUCKET_ID)
    write_manifest(paths, _manifest())
    assert read_manifest(paths).schema_version == BUCKET_MANIFEST_SCHEMA_VERSION
