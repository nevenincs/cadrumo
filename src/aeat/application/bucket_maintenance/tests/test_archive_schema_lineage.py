"""Sealed-archive version gate: ceiling with a durability floor.

Companion to the storage-substrate and bundle lineage gates
(``2026-07-08-released-data-durability-adr``): the sealed-archive import
gate distinguishes an archive exported by a newer application (upgrade the
application) from one below the durability floor (predates the guarantee).

The archive tier deliberately carries NO upgrade dispatch — unlike the
secure-object and bundle tiers, ``ensure_archive_schema_readable`` is a
range gate only and nothing transforms an older archive layout on restore.
The floor-equals-current tripwire below is what keeps that honest: an
archive-version bump that holds the floor without landing a version-aware
reader would pass the range gate green while restore misreads the old
layout, which is exactly the silent-stranding failure the durability ADR
exists to prevent.
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


def test_floor_is_pinned_to_current_until_a_version_aware_reader_exists() -> None:
    """An archive-version bump must decide: drop old archives or build the reader.

    The archive tier has no upgrade dispatch, so a floor held below the
    current version has no mechanism behind it — the range gate would accept
    an old archive that the restore path cannot actually read. Raising
    ``_ARCHIVE_SCHEMA_VERSION`` therefore requires, in the same change,
    either raising ``_ARCHIVE_DURABILITY_FLOOR`` with it (explicitly dropping
    older archives, the pre-release posture) or landing a version-aware
    ``read_sealed_archive``/restore transform plus a real old-archive
    restorability test, and only then widening this pin.
    """
    assert _ARCHIVE_DURABILITY_FLOOR == _ARCHIVE_SCHEMA_VERSION, (
        "archive durability floor is below the current archive version, but the "
        "archive tier has no upgrade dispatch: either raise the floor in the same "
        "change (dropping older archives) or land a version-aware reader/restore "
        "transform with an old-archive restorability test before widening the range "
        "(2026-07-08-released-data-durability-adr)"
    )


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
