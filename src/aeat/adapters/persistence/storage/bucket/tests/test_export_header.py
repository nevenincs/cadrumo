"""Tests for the :class:`ExportArchiveHeader` record."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from .._export_header import ExportArchiveHeader

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _digest() -> str:
    return hashlib.sha256(b"manifest-payload").hexdigest()


def _header(**overrides: object) -> ExportArchiveHeader:
    defaults: dict[str, Any] = {
        "bucket_id": "bucket-001",
        "manifest_digest": _digest(),
        "recovery_wrap_present": True,
        "archive_schema_version": 1,
        "created_at": datetime.now(tz=UTC),
    }
    defaults.update(overrides)
    return ExportArchiveHeader(**defaults)


def test_round_trip() -> None:
    header = _header()
    revived = ExportArchiveHeader.model_validate_json(header.model_dump_json())
    assert revived == header


def test_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        ExportArchiveHeader.model_validate(
            {
                "bucket_id": "bucket-001",
                "manifest_digest": _digest(),
                "recovery_wrap_present": True,
                "archive_schema_version": 1,
                "created_at": datetime.now(tz=UTC),
                "unexpected": 1,
            },
        )


def test_header_is_frozen() -> None:
    header = _header()
    with pytest.raises((ValidationError, TypeError), match=r"frozen|Instance is frozen|attribute"):
        header.archive_schema_version = 2


def test_rejects_missing_digest() -> None:
    with pytest.raises(ValidationError):
        ExportArchiveHeader.model_validate(
            {
                "bucket_id": "bucket-001",
                "recovery_wrap_present": True,
                "archive_schema_version": 1,
                "created_at": datetime.now(tz=UTC),
            },
        )


def test_rejects_non_hex_digest() -> None:
    with pytest.raises(ValidationError):
        _header(manifest_digest="z" * 64)


def test_rejects_short_digest() -> None:
    with pytest.raises(ValidationError):
        _header(manifest_digest="a" * 63)


def test_rejects_uppercase_digest() -> None:
    with pytest.raises(ValidationError):
        _header(manifest_digest=_digest().upper())


@pytest.mark.parametrize(
    "manifest_digest",
    (
        "+" + ("a" * 63),
        " " + ("a" * 63),
        ("a" * 63) + "\n",
    ),
)
def test_rejects_sign_or_whitespace_digest_spellings(manifest_digest: str) -> None:
    with pytest.raises(ValidationError):
        _header(manifest_digest=manifest_digest)


def test_rejects_empty_bucket_id() -> None:
    with pytest.raises(ValidationError):
        _header(bucket_id="")


def test_rejects_non_positive_archive_schema_version() -> None:
    with pytest.raises(ValidationError):
        _header(archive_schema_version=0)


def test_rejects_coerced_archive_schema_version() -> None:
    with pytest.raises(ValidationError):
        _header(archive_schema_version="1")


def test_rejects_coerced_recovery_wrap_flag() -> None:
    with pytest.raises(ValidationError):
        _header(recovery_wrap_present=1)


def test_rejects_naive_created_at() -> None:
    with pytest.raises(ValidationError):
        _header(created_at=datetime(2026, 1, 1))


def test_rejects_non_utc_offset_created_at() -> None:
    plus_one = timezone(timedelta(hours=1))
    with pytest.raises(ValidationError):
        _header(created_at=datetime(2026, 1, 1, tzinfo=plus_one))
