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

from ....core import COMPATIBILITY_REGIME, RELEASED_FORMAT_FLOORS, expected_floor
from .._service import (
    _ARCHIVE_DURABILITY_FLOOR,
    _ARCHIVE_SCHEMA_VERSION,
    BucketImportError,
    ensure_archive_schema_readable,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_floor_does_not_exceed_current_version() -> None:
    assert _ARCHIVE_DURABILITY_FLOOR <= _ARCHIVE_SCHEMA_VERSION


def test_floor_matches_the_regime_expected_floor() -> None:
    """The archive floor tracks the regime-switched compatibility policy.

    While ``PRE_RELEASE`` (today) the expected floor IS the current version,
    so this asserts exactly the pre-release pin it asserted before: an
    archive-version bump must either raise the floor with it (dropping older
    archives) or — because the archive tier has no upgrade dispatch — land a
    version-aware reader plus an old-archive restorability test. Post-flip
    the expected floor becomes the frozen released value, and this same
    assertion demands the floor stay pinned there
    (``2026-07-09-compatibility-lifecycle-adr``).
    """
    assert expected_floor(
        COMPATIBILITY_REGIME,
        "archive",
        _ARCHIVE_SCHEMA_VERSION,
        RELEASED_FORMAT_FLOORS,
    ) == _ARCHIVE_DURABILITY_FLOOR, (
        "archive durability floor diverges from the regime-expected floor: while "
        "pre-release it must equal the current archive version (the archive tier has "
        "no upgrade dispatch, so a lower floor has no mechanism behind it); either "
        "raise the floor in the same change (dropping older archives) or land a "
        "version-aware reader/restore transform with an old-archive restorability test "
        "(2026-07-09-compatibility-lifecycle-adr)"
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
