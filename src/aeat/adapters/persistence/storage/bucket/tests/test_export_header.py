"""Tests for the :class:`ExportArchiveHeader` record."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from .._export_header import ExportArchiveHeader

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_VALID_DIGEST = hashlib.sha256(b"manifest-payload").hexdigest()
_CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)
_PLUS_ONE = timezone(timedelta(hours=1))


def _header_payload(**overrides: object) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "bucket_id": "bucket-001",
        "manifest_digest": _VALID_DIGEST,
        "recovery_wrap_present": True,
        "archive_schema_version": 1,
        "created_at": _CREATED_AT,
    }
    defaults.update(overrides)
    return defaults


def _header(**overrides: object) -> ExportArchiveHeader:
    return ExportArchiveHeader(**_header_payload(**overrides))


def test_round_trip() -> None:
    header = _header()
    revived = ExportArchiveHeader.model_validate_json(header.model_dump_json())
    assert revived == header


def test_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError) as excinfo:
        ExportArchiveHeader.model_validate(_header_payload(unexpected=1))

    assert "unexpected" in str(excinfo.value)


def test_header_is_frozen() -> None:
    header = _header()
    with pytest.raises((ValidationError, TypeError), match=r"frozen|Instance is frozen|attribute"):
        header.archive_schema_version = 2


@pytest.mark.parametrize(
    "missing_field",
    (
        pytest.param("bucket_id", id="bucket-id"),
        pytest.param("manifest_digest", id="manifest-digest"),
    ),
)
def test_rejects_missing_required_header_fields(missing_field: str) -> None:
    payload = _header_payload()
    del payload[missing_field]

    with pytest.raises(ValidationError) as excinfo:
        ExportArchiveHeader.model_validate(payload)

    assert missing_field in str(excinfo.value)


@pytest.mark.parametrize(
    "manifest_digest",
    (
        pytest.param("z" * 64, id="non-hex"),
        pytest.param("a" * 63, id="short"),
        pytest.param(_VALID_DIGEST.upper(), id="uppercase"),
        pytest.param("+" + ("a" * 63), id="leading-sign"),
        pytest.param(" " + ("a" * 63), id="leading-space"),
        pytest.param(("a" * 63) + "\n", id="trailing-newline"),
    ),
)
def test_rejects_invalid_digest_spellings(manifest_digest: str) -> None:
    with pytest.raises(ValidationError):
        _header(manifest_digest=manifest_digest)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        pytest.param("bucket_id", "", id="bucket-empty"),
        pytest.param("archive_schema_version", 0, id="schema-non-positive"),
        pytest.param("archive_schema_version", "1", id="schema-coerced"),
        pytest.param("recovery_wrap_present", 1, id="recovery-flag-coerced"),
    ),
)
def test_rejects_invalid_header_scalars(field_name: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _header(**{field_name: value})


@pytest.mark.parametrize(
    "created_at",
    (
        pytest.param(datetime(2026, 1, 1), id="naive"),
        pytest.param(datetime(2026, 1, 1, tzinfo=_PLUS_ONE), id="non-utc-offset"),
    ),
)
def test_rejects_non_utc_created_at(created_at: datetime) -> None:
    with pytest.raises(ValidationError):
        _header(created_at=created_at)
