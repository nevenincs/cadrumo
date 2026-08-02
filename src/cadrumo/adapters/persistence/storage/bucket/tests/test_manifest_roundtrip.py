"""Strict roundtrip across the bucket-manifest TOML boundary.

:func:`write_manifest` serialises a :class:`BucketManifest` to TOML and
writes it to disk; :func:`read_manifest` parses the TOML through
``tomllib.loads`` and re-validates it under the strict pydantic schema.
This test asserts the cycle preserves every field of the manifest with
byte-identical fidelity.

Real filesystem IO, no mocks. A regression that drops the
``last_unlocked_at`` None hydration, encodes the salt incorrectly, or
ships an extra key past ``extra="forbid"`` surfaces as a strict pydantic
inequality or a load-time ValidationError.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......core.external_constants import UTF_8_ENCODING
from ......domain.user_profile import UserProfileStatus
from .._layout import BucketPaths, bucket_paths
from .._manifest import BUCKET_MANIFEST_SCHEMA_VERSION, BucketManifest, ManifestKdfParams
from .._manifest_io import manifest_path, read_manifest, write_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_POPULATED_TIMESTAMP = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


def _populated_manifest(bucket_id: str) -> BucketManifest:
    """Build a BucketManifest with every field set to a non-default value.

    The salt is a deterministic 16-byte sequence so a base64 mis-encoding
    surfaces as a salt-byte inequality. ``last_unlocked_at`` is set
    to a real UTC timestamp so the None-vs-absent code path on the
    read side does NOT mask its presence on the write side. ``status``
    is set to the non-default ``TOMBSTONED`` so a save-drops /
    load-re-defaults regression on the lifecycle marker surfaces.
    """

    return BucketManifest(
        bucket_id=bucket_id,
        label="Test Operator Bucket",
        created_at=_POPULATED_TIMESTAMP,
        last_unlocked_at=_POPULATED_TIMESTAMP,
        kdf_params=ManifestKdfParams(
            algorithm="argon2id",
            # 19 is Argon2 v1.3, the only version the substrate derives under.
            # The non-default population discipline this fixture follows still
            # holds on every cost axis below; the version axis has exactly one
            # legal value, and the 2 that used to sit here was a schema version
            # in an Argon2 version's slot.
            version=19,
            memory_cost=65536,
            time_cost=3,
            parallelism=4,
            salt=bytes(range(16)),
            output_length=32,
        ),
        recovery_enrolled=True,
        schema_version=BUCKET_MANIFEST_SCHEMA_VERSION,
        status=UserProfileStatus.TOMBSTONED,
    )


def _prepared_paths(tmp_path: Path, bucket_id: str) -> BucketPaths:
    paths = bucket_paths(tmp_path, bucket_id)
    paths.bucket_dir.mkdir(parents=True, exist_ok=True)
    return paths


def test_bucket_manifest_round_trips_strictly_via_toml(tmp_path: Path) -> None:
    """write_manifest -> disk -> read_manifest yields the original manifest unchanged.

    Every field of the manifest, including the nested ManifestKdfParams salt
    bytes, the UTC-tagged datetimes, and the boolean
    ``recovery_enrolled`` flag, must come back identical. The
    assertion uses strict pydantic equality so a single dropped
    field is a one-line failure that names the offender.
    """

    paths = _prepared_paths(tmp_path, "test-bucket-roundtrip")
    original = _populated_manifest(paths.bucket_id)
    write_manifest(paths, original)
    loaded = read_manifest(paths)

    assert loaded == original
    # Per-field witnesses: salt bytes are the most fragile (base64
    # encoding round-trip); pin them explicitly so a regression on
    # the encoder is obvious.
    assert loaded.kdf_params.salt == original.kdf_params.salt
    assert loaded.kdf_params.algorithm == "argon2id"
    assert loaded.kdf_params.memory_cost == 65536
    assert loaded.last_unlocked_at == original.last_unlocked_at
    assert loaded.recovery_enrolled is True
    # The lifecycle marker is the plaintext mirror the manifest scan
    # filters on; a save-drops / load-re-defaults regression would
    # silently flip a tombstoned profile back onto the live surface.
    assert loaded.status is UserProfileStatus.TOMBSTONED


def test_bucket_manifest_round_trips_with_last_unlocked_at_unset(
    tmp_path: Path,
) -> None:
    """A manifest with ``last_unlocked_at=None`` survives the TOML roundtrip.

    TOML has no native null. The read side hydrates an absent
    ``last_unlocked_at`` key to ``None`` before strict pydantic
    validation. This test asserts the write/read cycle preserves
    the unset state — both as ``None`` after load AND as an absent
    key in the on-disk TOML.
    """

    paths = _prepared_paths(tmp_path, "test-bucket-never-unlocked")
    original = _populated_manifest(paths.bucket_id).model_copy(
        update={"last_unlocked_at": None},
    )
    write_manifest(paths, original)

    # The on-disk TOML must NOT carry a literal null for
    # last_unlocked_at (TOML cannot represent null); the field
    # should be absent. This guards against a future write
    # implementation that emits ``last_unlocked_at = ""`` or a
    # quoted "None" string.
    on_disk = manifest_path(paths).read_text(encoding=UTF_8_ENCODING)
    assert "last_unlocked_at" not in on_disk

    loaded = read_manifest(paths)
    assert loaded == original
    assert loaded.last_unlocked_at is None


def test_manifest_status_mutation_surfaces_as_strict_inequality(
    tmp_path: Path,
) -> None:
    """Anti-tautology: rewriting the on-disk ``status`` is caught by reload.

    The fixture manifest is tombstoned. Mutating the persisted TOML to
    flip ``status`` back to ``active`` and reloading must yield a
    manifest that is strictly unequal to the original. If this test
    ever passes with the field flattened, the lifecycle-marker
    roundtrip is tautological and the tombstone leak could recur.
    """

    paths = _prepared_paths(tmp_path, "test-bucket-status-antitautology")
    original = _populated_manifest(paths.bucket_id)
    assert original.status is UserProfileStatus.TOMBSTONED
    write_manifest(paths, original)

    target = manifest_path(paths)
    on_disk = target.read_text(encoding=UTF_8_ENCODING)
    assert 'status = "tombstoned"' in on_disk
    target.write_text(
        on_disk.replace('status = "tombstoned"', 'status = "active"'),
        encoding=UTF_8_ENCODING,
    )

    reloaded = read_manifest(paths)
    assert reloaded != original
    assert reloaded.status is UserProfileStatus.ACTIVE
