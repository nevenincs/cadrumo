"""Sealed-archive version gate: ceiling with a durability floor.

Companion to the storage-substrate and bundle lineage gates
(``2026-07-08-released-data-durability-adr``): the sealed-archive import
gate distinguishes an archive exported by a newer application (upgrade the
application) from one below the durability floor (predates the guarantee),
and every version between the floor and the current version stays
importable so an archive-version bump cannot silently orphan a taxpayer's
existing backups.
"""

from __future__ import annotations

import pytest

from .._service import (
    _ARCHIVE_DURABILITY_FLOOR,
    _ARCHIVE_SCHEMA_VERSION,
    BucketImportError,
    ensure_archive_schema_readable,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_floor_does_not_exceed_current_version() -> None:
    assert _ARCHIVE_DURABILITY_FLOOR <= _ARCHIVE_SCHEMA_VERSION


def test_every_version_from_floor_to_current_is_importable() -> None:
    for version in range(_ARCHIVE_DURABILITY_FLOOR, _ARCHIVE_SCHEMA_VERSION + 1):
        ensure_archive_schema_readable(version)


def test_a_future_archive_version_is_refused_as_newer_application() -> None:
    with pytest.raises(BucketImportError) as excinfo:
        ensure_archive_schema_readable(_ARCHIVE_SCHEMA_VERSION + 1)
    assert (
        excinfo.value.translated_message == "application.bucket_maintenance.errors.archive_schema_version_from_future"
    )
    assert excinfo.value.context == {
        "archive_schema_version": str(_ARCHIVE_SCHEMA_VERSION + 1),
        "max_supported": str(_ARCHIVE_SCHEMA_VERSION),
    }


def test_a_version_below_the_floor_is_refused_as_unsupported() -> None:
    with pytest.raises(BucketImportError) as excinfo:
        ensure_archive_schema_readable(_ARCHIVE_DURABILITY_FLOOR - 1)
    assert (
        excinfo.value.translated_message == "application.bucket_maintenance.errors.unsupported_archive_schema_version"
    )
    assert excinfo.value.context == {
        "archive_schema_version": str(_ARCHIVE_DURABILITY_FLOOR - 1),
    }
