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
        "product": "cadrumo",
        "bucket_id": "bucket-001",
        "manifest_digest": _VALID_DIGEST,
        "recovery_wrap_present": True,
        "archive_schema_version": 3,
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


def test_rejects_former_product_marker() -> None:
    with pytest.raises(ValidationError, match="product must be 'cadrumo'"):
        _header(product="aeat")


def test_header_is_frozen() -> None:
    header = _header()
    with pytest.raises((ValidationError, TypeError), match=r"frozen|Instance is frozen|attribute"):
        header.archive_schema_version = 2


def test_rejects_missing_required_header_fields() -> None:
    for missing_field in ("product", "bucket_id", "manifest_digest"):
        payload = _header_payload()
        del payload[missing_field]

        with pytest.raises(ValidationError) as excinfo:
            ExportArchiveHeader.model_validate(payload)

        assert missing_field in str(excinfo.value)


def test_rejects_invalid_digest_spellings() -> None:
    for manifest_digest in (
        "z" * 64,
        "a" * 63,
        _VALID_DIGEST.upper(),
        "+" + ("a" * 63),
        " " + ("a" * 63),
        ("a" * 63) + "\n",
    ):
        with pytest.raises(ValidationError):
            _header(manifest_digest=manifest_digest)


def test_rejects_invalid_header_scalars() -> None:
    for field_name, value in (
        ("bucket_id", ""),
        ("archive_schema_version", 0),
        ("archive_schema_version", "1"),
        ("recovery_wrap_present", 1),
    ):
        with pytest.raises(ValidationError):
            _header(**{field_name: value})


def test_rejects_non_utc_created_at() -> None:
    for created_at in (
        datetime(2026, 1, 1),
        datetime(2026, 1, 1, tzinfo=_PLUS_ONE),
    ):
        with pytest.raises(ValidationError):
            _header(created_at=created_at)
