"""Sealed-archive schema-version boundary tests."""

from __future__ import annotations

import pytest

from .._service import (
    _ARCHIVE_SCHEMA_VERSION,
    BucketImportError,
    ensure_archive_schema_supported,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_current_archive_version_is_supported() -> None:
    ensure_archive_schema_supported(_ARCHIVE_SCHEMA_VERSION)


def test_future_archive_version_is_refused_as_newer_application() -> None:
    with pytest.raises(BucketImportError) as excinfo:
        ensure_archive_schema_supported(_ARCHIVE_SCHEMA_VERSION + 1)
    assert (
        excinfo.value.translated_message == "application.bucket_maintenance.errors.archive_schema_version_from_future"
    )
    assert excinfo.value.context == {
        "archive_schema_version": str(_ARCHIVE_SCHEMA_VERSION + 1),
        "max_supported": str(_ARCHIVE_SCHEMA_VERSION),
    }


def test_pre_current_archive_version_is_refused_without_migration() -> None:
    with pytest.raises(BucketImportError) as excinfo:
        ensure_archive_schema_supported(_ARCHIVE_SCHEMA_VERSION - 1)
    assert (
        excinfo.value.translated_message == "application.bucket_maintenance.errors.unsupported_archive_schema_version"
    )
    assert excinfo.value.context == {
        "archive_schema_version": str(_ARCHIVE_SCHEMA_VERSION - 1),
    }
