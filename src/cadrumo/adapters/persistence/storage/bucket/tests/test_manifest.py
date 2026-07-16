"""Strict-validation tests for :class:`BucketManifest` and :class:`ManifestKdfParams`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any, TypedDict

import pytest
from pydantic import ValidationError

from ......domain.user_profile import UserProfileStatus
from .._manifest import BucketManifest, ManifestKdfParams

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class _KdfParamsArgs(TypedDict, total=False):
    """TypedDict for ManifestKdfParams constructor arguments with optional overrides."""

    algorithm: str
    version: int
    memory_cost: int
    time_cost: int
    parallelism: int
    salt: bytes
    output_length: int


class _ManifestPayloadArgs(TypedDict, total=False):
    """TypedDict for BucketManifest constructor arguments with optional overrides."""

    bucket_id: str
    label: str
    created_at: datetime
    last_unlocked_at: datetime | None
    kdf_params: ManifestKdfParams
    recovery_enrolled: bool
    schema_version: int
    status: UserProfileStatus
    idle_lock_minutes: int | None
    key_schedule: Any


_VALID_SALT = bytes(range(16))
_SHORT_SALT = bytes(range(15))
_PLUS_ONE = timezone(timedelta(hours=1))
_CREATED_AT = datetime(2026, 5, 28, 12, 10, 0, tzinfo=UTC)


def _kdf_params(**overrides: object) -> ManifestKdfParams:
    # Build defaults with proper types
    params: _KdfParamsArgs = {
        "algorithm": "argon2id",
        "version": 19,
        "memory_cost": 19 * 1024,
        "time_cost": 2,
        "parallelism": 1,
        "salt": _VALID_SALT,
        "output_length": 32,
    }

    # Apply overrides by checking each known key
    if overrides:
        if "algorithm" in overrides and isinstance(overrides["algorithm"], str):
            params["algorithm"] = overrides["algorithm"]
        if "version" in overrides and isinstance(overrides["version"], int):
            params["version"] = overrides["version"]
        if "memory_cost" in overrides and isinstance(overrides["memory_cost"], int):
            params["memory_cost"] = overrides["memory_cost"]
        if "time_cost" in overrides and isinstance(overrides["time_cost"], int):
            params["time_cost"] = overrides["time_cost"]
        if "parallelism" in overrides and isinstance(overrides["parallelism"], int):
            params["parallelism"] = overrides["parallelism"]
        if "salt" in overrides and isinstance(overrides["salt"], bytes):
            params["salt"] = overrides["salt"]
        if "output_length" in overrides and isinstance(overrides["output_length"], int):
            params["output_length"] = overrides["output_length"]

    return ManifestKdfParams(**params)


def _kdf() -> ManifestKdfParams:
    return _kdf_params()


def _manifest_payload(**overrides: object) -> dict[str, object]:
    # Build payload with proper types
    payload: _ManifestPayloadArgs = {
        "bucket_id": "bucket-001",
        "label": "Primary",
        "created_at": _CREATED_AT,
        "last_unlocked_at": None,
        "kdf_params": _kdf(),
        "recovery_enrolled": False,
        "schema_version": 1,
        "status": UserProfileStatus.ACTIVE,
    }

    # Apply overrides by checking each known key
    if overrides:
        if "bucket_id" in overrides and isinstance(overrides["bucket_id"], str):
            payload["bucket_id"] = overrides["bucket_id"]
        if "label" in overrides and isinstance(overrides["label"], str):
            payload["label"] = overrides["label"]
        if "created_at" in overrides and isinstance(overrides["created_at"], datetime):
            payload["created_at"] = overrides["created_at"]
        if "last_unlocked_at" in overrides and (
            isinstance(overrides["last_unlocked_at"], datetime) or overrides["last_unlocked_at"] is None
        ):
            payload["last_unlocked_at"] = overrides["last_unlocked_at"]
        if "kdf_params" in overrides and isinstance(overrides["kdf_params"], ManifestKdfParams):
            payload["kdf_params"] = overrides["kdf_params"]
        if "recovery_enrolled" in overrides and isinstance(overrides["recovery_enrolled"], bool):
            payload["recovery_enrolled"] = overrides["recovery_enrolled"]
        if "schema_version" in overrides and isinstance(overrides["schema_version"], int):
            payload["schema_version"] = overrides["schema_version"]
        if "status" in overrides and isinstance(overrides["status"], UserProfileStatus):
            payload["status"] = overrides["status"]
        if "idle_lock_minutes" in overrides and (
            isinstance(overrides["idle_lock_minutes"], int) or overrides["idle_lock_minutes"] is None
        ):
            payload["idle_lock_minutes"] = overrides["idle_lock_minutes"]
        if "key_schedule" in overrides:
            payload["key_schedule"] = overrides["key_schedule"]

    # Convert to dict[str, object] and add any unknown keys from overrides
    result: dict[str, object] = dict(payload)
    if overrides:
        for key, value in overrides.items():
            if key not in payload:
                result[key] = value

    return result


def _manifest(**overrides: object) -> BucketManifest:
    # Build payload with proper types (same logic as _manifest_payload)
    payload: _ManifestPayloadArgs = {
        "bucket_id": "bucket-001",
        "label": "Primary",
        "created_at": _CREATED_AT,
        "last_unlocked_at": None,
        "kdf_params": _kdf(),
        "recovery_enrolled": False,
        "schema_version": 1,
        "status": UserProfileStatus.ACTIVE,
    }

    # Apply overrides by checking each known key
    if overrides:
        if "bucket_id" in overrides and isinstance(overrides["bucket_id"], str):
            payload["bucket_id"] = overrides["bucket_id"]
        if "label" in overrides and isinstance(overrides["label"], str):
            payload["label"] = overrides["label"]
        if "created_at" in overrides and isinstance(overrides["created_at"], datetime):
            payload["created_at"] = overrides["created_at"]
        if "last_unlocked_at" in overrides and (
            isinstance(overrides["last_unlocked_at"], datetime) or overrides["last_unlocked_at"] is None
        ):
            payload["last_unlocked_at"] = overrides["last_unlocked_at"]
        if "kdf_params" in overrides and isinstance(overrides["kdf_params"], ManifestKdfParams):
            payload["kdf_params"] = overrides["kdf_params"]
        if "recovery_enrolled" in overrides and isinstance(overrides["recovery_enrolled"], bool):
            payload["recovery_enrolled"] = overrides["recovery_enrolled"]
        if "schema_version" in overrides and isinstance(overrides["schema_version"], int):
            payload["schema_version"] = overrides["schema_version"]
        if "status" in overrides and isinstance(overrides["status"], UserProfileStatus):
            payload["status"] = overrides["status"]
        if "idle_lock_minutes" in overrides and (
            isinstance(overrides["idle_lock_minutes"], int) or overrides["idle_lock_minutes"] is None
        ):
            payload["idle_lock_minutes"] = overrides["idle_lock_minutes"]
        if "key_schedule" in overrides:
            payload["key_schedule"] = overrides["key_schedule"]

    return BucketManifest(**payload)


def test_round_trip_preserves_salt_bytes() -> None:
    manifest = _manifest(kdf_params=_kdf_params(salt=_VALID_SALT))
    blob = manifest.model_dump_json()
    revived = BucketManifest.model_validate_json(blob)
    assert revived.kdf_params.salt == _VALID_SALT


def test_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError) as excinfo:
        BucketManifest.model_validate(_manifest_payload(unexpected="nope"))

    assert "unexpected" in str(excinfo.value)


def test_rejects_missing_required_manifest_fields() -> None:
    for missing_field in ("bucket_id", "status"):
        payload = _manifest_payload()
        del payload[missing_field]

        with pytest.raises(ValidationError) as excinfo:
            BucketManifest.model_validate(payload)

        assert missing_field in str(excinfo.value)


def test_rejects_empty_bucket_id() -> None:
    with pytest.raises(ValidationError):
        _manifest(bucket_id="")


def test_rejects_non_utc_manifest_timestamps() -> None:
    cases = (
        ("created_at", datetime(2026, 1, 1, 0, 0, 0)),
        (
            "created_at",
            datetime(2026, 1, 1, 0, 0, 0, tzinfo=_PLUS_ONE),
        ),
        ("last_unlocked_at", datetime(2026, 1, 1, 0, 0, 0)),
        (
            "last_unlocked_at",
            datetime(2026, 1, 1, 0, 0, 0, tzinfo=_PLUS_ONE),
        ),
    )

    for field_name, value in cases:
        with pytest.raises(ValidationError):
            _manifest(**{field_name: value})


def test_rejects_non_positive_schema_version() -> None:
    with pytest.raises(ValidationError):
        _manifest(schema_version=0)


def test_rejects_invalid_kdf_parameters() -> None:
    for field_name, value in (("salt", _SHORT_SALT), ("algorithm", "")):
        with pytest.raises(ValidationError):
            _kdf_params(**{field_name: value})


# ── UTC helper migration: validate_utc_aware semantics ─────────────────────


def test_created_at_utc_aware_accepted() -> None:
    """A UTC-aware created_at passes the boundary intact."""
    ts = datetime(2026, 3, 15, 10, 30, 0, tzinfo=UTC)
    m = _manifest(created_at=ts)
    assert m.created_at == ts


def test_last_unlocked_at_utc_aware_accepted() -> None:
    """A UTC-aware last_unlocked_at passes through unchanged."""
    ts = datetime(2026, 3, 15, 11, 0, 0, tzinfo=UTC)
    m = _manifest(last_unlocked_at=ts)
    assert m.last_unlocked_at == ts
