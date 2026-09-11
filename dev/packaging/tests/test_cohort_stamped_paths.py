"""Real stamping tests pinning the cohort's extra wheel members to what the build writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..python_cohort import (
    _stamp_bundled_registry_records_into_build_tree,
    cohort_stamped_wheel_data_paths,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _build_tree(root: Path) -> Path:
    """Materialise the extracted-source layout the cohort build stamps into."""
    registry_root = root / "src" / "cadrumo" / "_data" / "registry" / "aeat"
    registry_root.mkdir(parents=True)
    (registry_root / "manifest.toml").write_text("modelos = []\n", encoding="utf-8")
    return registry_root


def test_stamped_members_match_the_declared_cohort_set(tmp_path: Path) -> None:
    """Running the real stamp writes exactly the members the payload check expects.

    Exercises the production stamping path rather than restating the constant, so a
    change to either stamped filename or to their sibling-of-the-registry-root
    location fails here instead of surfacing as an ``unexpected`` wheel member in
    CI. Compares the whole set, so a record that STOPS being written is caught as
    surely as one that starts.
    """
    build_root = tmp_path / "cohort-source"
    build_root.mkdir()
    _build_tree(build_root)

    stamped = _stamp_bundled_registry_records_into_build_tree(build_root)

    assert stamped == cohort_stamped_wheel_data_paths()


def test_stamped_members_land_on_disk_where_the_wheel_will_carry_them(tmp_path: Path) -> None:
    """Every returned wheel-relative path resolves to a file the build actually wrote.

    Guards the ``relative_to`` derivation: a stamp written outside the packaged
    ``src`` root would still return a string, but would not exist at the archive
    location the payload check asserts against.
    """
    build_root = tmp_path / "cohort-source"
    build_root.mkdir()
    _build_tree(build_root)

    stamped = _stamp_bundled_registry_records_into_build_tree(build_root)

    assert stamped, "the build must stamp at least one member, or this loop proves nothing"
    for member in stamped:
        assert (build_root / "src" / member).is_file()
