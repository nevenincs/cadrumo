"""Transitional gate: typing the declaration must not move a byte on disk.

The taxonomy replaces an untyped ``dict[str, str]`` that had been the authority
for where every derived output lands. The change is one of representation,
layer, and enforcement; it is emphatically not one of location. Real operator
data already sits at these paths, and the pre-release regime would permit
stranding it -- this declines to use that permission.

The comparison is byte-identical on the subpath string, not a normalised or
resolved path, because normalisation is exactly what would hide a moved
directory behind an equal-looking result.

This file is deliberately transitional. It exists only while both
representations do, and is deleted in the same change that deletes the dict --
comparing the taxonomy against itself would assert nothing.
"""

from __future__ import annotations

import pytest

from .._storage_taxonomy import STORAGE_TAXONOMY, StorageScope
from ..config import _STATE_ROOT_DERIVED_DIRS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _root_subpaths_by_field() -> dict[str, str]:
    return {
        location.settings_field: location.subpath
        for location in STORAGE_TAXONOMY.values()
        if location.scope is StorageScope.ROOT
        and location.settings_field is not None
        and location.derives_settings_default
    }


def test_every_shipped_entry_has_a_byte_identical_taxonomy_subpath() -> None:
    """No declared location moved when it gained a type."""
    declared = _root_subpaths_by_field()
    assert _STATE_ROOT_DERIVED_DIRS, "the shipped table must be non-empty, or this asserts nothing"

    missing = sorted(set(_STATE_ROOT_DERIVED_DIRS) - set(declared))
    assert not missing, f"the taxonomy declares no derived member for: {missing}"

    moved = {
        field_name: (subpath, declared[field_name])
        for field_name, subpath in _STATE_ROOT_DERIVED_DIRS.items()
        if declared[field_name] != subpath
    }
    assert not moved, f"subpaths changed (field: shipped -> declared): {moved}"


def test_the_derived_member_set_matches_the_shipped_table_exactly() -> None:
    """Both directions: an added derived member is as much a drift as a dropped one."""
    assert set(_root_subpaths_by_field()) == set(_STATE_ROOT_DERIVED_DIRS)
