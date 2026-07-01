"""Strict-validation tests for :class:`BucketManifest` and :class:`ManifestKdfParams`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from .._manifest import BucketLifecycleStatus, BucketManifest, ManifestKdfParams

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_VALID_SALT = bytes(range(16))
_SHORT_SALT = bytes(range(15))
_PLUS_ONE = timezone(timedelta(hours=1))


def _kdf_params(**overrides: object) -> ManifestKdfParams:
    defaults: dict[str, object] = {
        "algorithm": "argon2id",
        "version": 19,
        "memory_cost": 19 * 1024,
        "time_cost": 2,
        "parallelism": 1,
        "salt": _VALID_SALT,
        "output_length": 32,
    }
    defaults.update(overrides)
    return ManifestKdfParams(**defaults)


def _kdf() -> ManifestKdfParams:
    return _kdf_params()


def now() -> datetime:
    return datetime.now(tz=UTC)


def _manifest_payload(**overrides: object) -> dict[str, object]:
    defaults: dict[str, Any] = {
        "bucket_id": "bucket-001",
        "label": "Primary",
        "created_at": now(),
        "last_unlocked_at": None,
        "kdf_params": _kdf(),
        "recovery_enrolled": False,
        "schema_version": 1,
        "status": BucketLifecycleStatus.ACTIVE,
    }
    defaults.update(overrides)
    return defaults


def _manifest(**overrides: object) -> BucketManifest:
    return BucketManifest(**_manifest_payload(**overrides))


def test_round_trip_preserves_salt_bytes() -> None:
    manifest = _manifest(kdf_params=_kdf_params(salt=_VALID_SALT))
    blob = manifest.model_dump_json()
    revived = BucketManifest.model_validate_json(blob)
    assert revived.kdf_params.salt == _VALID_SALT


def test_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError) as excinfo:
        BucketManifest.model_validate(_manifest_payload(unexpected="nope"))

    assert "unexpected" in str(excinfo.value)


@pytest.mark.parametrize(
    "missing_field",
    (
        pytest.param("bucket_id", id="bucket-id"),
        pytest.param("status", id="lifecycle-status"),
    ),
)
def test_rejects_missing_required_manifest_fields(missing_field: str) -> None:
    payload = _manifest_payload()
    del payload[missing_field]

    with pytest.raises(ValidationError) as excinfo:
        BucketManifest.model_validate(payload)

    assert missing_field in str(excinfo.value)


def test_rejects_empty_bucket_id() -> None:
    with pytest.raises(ValidationError):
        _manifest(bucket_id="")


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        pytest.param("created_at", datetime(2026, 1, 1, 0, 0, 0), id="created-naive"),
        pytest.param(
            "created_at",
            datetime(2026, 1, 1, 0, 0, 0, tzinfo=_PLUS_ONE),
            id="created-non-utc",
        ),
        pytest.param("last_unlocked_at", datetime(2026, 1, 1, 0, 0, 0), id="unlocked-naive"),
        pytest.param(
            "last_unlocked_at",
            datetime(2026, 1, 1, 0, 0, 0, tzinfo=_PLUS_ONE),
            id="unlocked-non-utc",
        ),
    ),
)
def test_rejects_non_utc_manifest_timestamps(field_name: str, value: datetime) -> None:
    with pytest.raises(ValidationError):
        _manifest(**{field_name: value})


def test_rejects_non_positive_schema_version() -> None:
    with pytest.raises(ValidationError):
        _manifest(schema_version=0)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        pytest.param("salt", _SHORT_SALT, id="salt-length"),
        pytest.param("algorithm", "", id="algorithm-empty"),
    ),
)
def test_rejects_invalid_kdf_parameters(field_name: str, value: object) -> None:
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
