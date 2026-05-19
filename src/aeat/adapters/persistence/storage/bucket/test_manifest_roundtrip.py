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

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ._layout import bucket_paths
from ._manifest import BucketManifest, ManifestKdfParams
from ._manifest_io import read_manifest, write_manifest

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _populated_manifest(bucket_id: str) -> BucketManifest:
    """Build a BucketManifest with every field set to a non-default value.

    The salt is a 32-byte random sequence so a base64 mis-encoding
    surfaces as a salt-byte inequality. ``last_unlocked_at`` is set
    to a real UTC timestamp so the None-vs-absent code path on the
    read side does NOT mask its presence on the write side.
    """

    now = datetime.now(UTC).replace(microsecond=0)
    return BucketManifest(
        bucket_id=bucket_id,
        label="Test Operator Bucket",
        created_at=now,
        last_unlocked_at=now,
        kdf_params=ManifestKdfParams(
            algorithm="argon2id",
            version=2,
            memory_cost=65536,
            time_cost=3,
            parallelism=4,
            salt=os.urandom(16),
            output_length=32,
        ),
        recovery_enrolled=True,
        schema_version=1,
    )


def test_bucket_manifest_round_trips_strictly_via_toml(tmp_path: Path) -> None:
    """write_manifest -> disk -> read_manifest yields the original manifest unchanged.

    Every field of the manifest, including the nested ManifestKdfParams salt
    bytes, the UTC-tagged datetimes, and the boolean
    ``recovery_enrolled`` flag, must come back identical. The
    assertion uses strict pydantic equality so a single dropped
    field is a one-line failure that names the offender.
    """

    paths = bucket_paths(tmp_path, "test-bucket-roundtrip")
    paths.bucket_dir.mkdir(parents=True, exist_ok=True)

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

    paths = bucket_paths(tmp_path, "test-bucket-never-unlocked")
    paths.bucket_dir.mkdir(parents=True, exist_ok=True)

    original = _populated_manifest(paths.bucket_id).model_copy(
        update={"last_unlocked_at": None},
    )
    write_manifest(paths, original)

    # The on-disk TOML must NOT carry a literal null for
    # last_unlocked_at (TOML cannot represent null); the field
    # should be absent. This guards against a future write
    # implementation that emits ``last_unlocked_at = ""`` or a
    # quoted "None" string.
    from ._manifest_io import manifest_path

    on_disk = manifest_path(paths).read_text(encoding="utf-8")
    assert "last_unlocked_at" not in on_disk

    loaded = read_manifest(paths)
    assert loaded == original
    assert loaded.last_unlocked_at is None
