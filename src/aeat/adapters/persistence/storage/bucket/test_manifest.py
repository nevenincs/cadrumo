"""Strict-validation tests for :class:`BucketManifest` and :class:`ManifestKdfParams`."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from ._manifest import BucketManifest, ManifestKdfParams

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _kdf() -> ManifestKdfParams:
    return ManifestKdfParams(
        algorithm="argon2id",
        version=19,
        memory_cost=19 * 1024,
        time_cost=2,
        parallelism=1,
        salt=secrets.token_bytes(16),
        output_length=32,
    )


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _manifest(**overrides: object) -> BucketManifest:
    defaults: dict[str, Any] = {
        "bucket_id": "bucket-001",
        "label": "Primary",
        "created_at": _now(),
        "last_unlocked_at": None,
        "kdf_params": _kdf(),
        "recovery_enrolled": False,
        "schema_version": 1,
    }
    defaults.update(overrides)
    return BucketManifest(**defaults)


def test_round_trip_preserves_salt_bytes() -> None:
    salt = secrets.token_bytes(16)
    manifest = _manifest(
        kdf_params=ManifestKdfParams(
            algorithm="argon2id",
            version=19,
            memory_cost=19 * 1024,
            time_cost=2,
            parallelism=1,
            salt=salt,
            output_length=32,
        )
    )
    blob = manifest.model_dump_json()
    revived = BucketManifest.model_validate_json(blob)
    assert revived.kdf_params.salt == salt


def test_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        BucketManifest.model_validate(
            {
                "bucket_id": "bucket-001",
                "label": "Primary",
                "created_at": _now(),
                "last_unlocked_at": None,
                "kdf_params": _kdf(),
                "recovery_enrolled": False,
                "schema_version": 1,
                "unexpected": "nope",
            }
        )


def test_rejects_missing_bucket_id() -> None:
    with pytest.raises(ValidationError):
        BucketManifest.model_validate(
            {
                "label": "Primary",
                "created_at": _now(),
                "last_unlocked_at": None,
                "kdf_params": _kdf(),
                "recovery_enrolled": False,
                "schema_version": 1,
            }
        )


def test_rejects_empty_bucket_id() -> None:
    with pytest.raises(ValidationError):
        _manifest(bucket_id="")


def test_rejects_naive_created_at() -> None:
    with pytest.raises(ValidationError):
        _manifest(created_at=datetime(2026, 1, 1, 0, 0, 0))


def test_rejects_non_utc_offset_created_at() -> None:
    from datetime import timedelta

    plus_one = timezone(timedelta(hours=1))
    with pytest.raises(ValidationError):
        _manifest(created_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=plus_one))


def test_rejects_non_positive_schema_version() -> None:
    with pytest.raises(ValidationError):
        _manifest(schema_version=0)


def test_rejects_wrong_salt_length() -> None:
    with pytest.raises(ValidationError):
        ManifestKdfParams(
            algorithm="argon2id",
            version=19,
            memory_cost=19 * 1024,
            time_cost=2,
            parallelism=1,
            salt=secrets.token_bytes(15),
            output_length=32,
        )


def test_rejects_unknown_kdf_algorithm_length_zero() -> None:
    with pytest.raises(ValidationError):
        ManifestKdfParams(
            algorithm="",
            version=19,
            memory_cost=19 * 1024,
            time_cost=2,
            parallelism=1,
            salt=secrets.token_bytes(16),
            output_length=32,
        )


def test_last_unlocked_at_naive_rejected() -> None:
    with pytest.raises(ValidationError):
        _manifest(last_unlocked_at=datetime(2026, 1, 1, 0, 0, 0))
