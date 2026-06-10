"""Tests for ``compute_manifest_digest``.

Verifies the digest is deterministic for identical manifests, varies
when any field changes, and matches the :class:`ExportArchiveHeader`
field constraint (64-char lowercase hex). The digest is the
sealed-archive header's integrity anchor; deterministic output is
the contract the importer relies on.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....adapters.persistence.storage.bucket._manifest import (
    BucketKeySchedule,
    BucketLifecycleStatus,
    BucketManifest,
    ManifestKdfParams,
)
from .. import compute_manifest_digest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_INSTANT = datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC)


def _manifest(*, bucket_id: str = "test-bucket", label: str = "Test label") -> BucketManifest:
    return BucketManifest(
        bucket_id=bucket_id,
        label=label,
        created_at=_INSTANT,
        last_unlocked_at=_INSTANT,
        kdf_params=ManifestKdfParams(
            algorithm="argon2id",
            version=19,
            memory_cost=65536,
            time_cost=3,
            parallelism=1,
            salt=b"a" * 16,
            output_length=32,
        ),
        recovery_enrolled=False,
        schema_version=1,
        status=BucketLifecycleStatus.ACTIVE,
        key_schedule=BucketKeySchedule.BUCKET_DEK_V1,
    )


def test_digest_is_64_char_lowercase_hex() -> None:
    """Output matches the ExportArchiveHeader.manifest_digest field constraint."""
    digest = compute_manifest_digest(_manifest())

    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_digest_is_deterministic_for_identical_manifests() -> None:
    """Two same-content manifests produce the same digest."""
    digest_a = compute_manifest_digest(_manifest())
    digest_b = compute_manifest_digest(_manifest())

    assert digest_a == digest_b


def test_digest_changes_when_label_changes() -> None:
    """A label edit must shift the digest — the importer cross-checks for it."""
    digest_original = compute_manifest_digest(_manifest(label="Original"))
    digest_relabelled = compute_manifest_digest(_manifest(label="Renamed"))

    assert digest_original != digest_relabelled


def test_digest_changes_when_bucket_id_changes() -> None:
    """A bucket_id edit shifts the digest — the importer's identity-collision guard relies on this."""
    digest_a = compute_manifest_digest(_manifest(bucket_id="bucket-a"))
    digest_b = compute_manifest_digest(_manifest(bucket_id="bucket-b"))

    assert digest_a != digest_b
