"""Real stamping tests pinning the cohort's extra wheel members to what the build writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.packaging.python_cohort import (
    COHORT_STAMPED_WHEEL_DATA_PATHS,
    _stamp_bundled_verdict_into_build_tree,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _build_tree(root: Path) -> Path:
    """Materialise the extracted-source layout the cohort build stamps into."""
    registry_root = root / "src" / "cadrumo" / "_data" / "registry" / "aeat"
    registry_root.mkdir(parents=True)
    (registry_root / "manifest.toml").write_text("modelos = []\n", encoding="utf-8")
    return registry_root


def test_stamped_member_matches_the_declared_cohort_set(tmp_path: Path) -> None:
    """Running the real stamp writes exactly the members the payload check expects.

    Exercises the production stamping path rather than restating the constant, so a
    change to the verdict filename or to its sibling-of-the-registry-root location
    fails here instead of surfacing as an ``unexpected`` wheel member in CI.
    """
    build_root = tmp_path / "cohort-source"
    build_root.mkdir()
    _build_tree(build_root)

    stamped = _stamp_bundled_verdict_into_build_tree(build_root)

    assert stamped in COHORT_STAMPED_WHEEL_DATA_PATHS
    assert {stamped} == COHORT_STAMPED_WHEEL_DATA_PATHS


def test_stamped_member_lands_on_disk_where_the_wheel_will_carry_it(tmp_path: Path) -> None:
    """The returned wheel-relative path resolves to the file the build actually wrote.

    Guards the ``relative_to`` derivation: a stamp written outside the packaged
    ``src`` root would still return a string, but would not exist at the archive
    location the payload check asserts against.
    """
    build_root = tmp_path / "cohort-source"
    build_root.mkdir()
    _build_tree(build_root)

    stamped = _stamp_bundled_verdict_into_build_tree(build_root)

    assert (build_root / "src" / stamped).is_file()
