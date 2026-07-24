"""Conformance gate: Development Status classifier is identical across all three distributions."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).parents[3]

_PYPROJECTS = {
    "root": _REPO_ROOT / "pyproject.toml",
    "cadrumo_data_manuals": _REPO_ROOT / "packaging" / "cadrumo_data_manuals" / "pyproject.toml",
    "cadrumo_data_official": _REPO_ROOT / "packaging" / "cadrumo_data_official" / "pyproject.toml",
}

_DEV_STATUS_PREFIX = "Development Status ::"


def _extract_dev_status(pyproject_path: Path) -> str:
    """Return the single Development Status classifier value from a pyproject.toml."""
    with pyproject_path.open("rb") as fh:
        data = tomllib.load(fh)
    classifiers: list[str] = data.get("project", {}).get("classifiers", [])
    matches = [c for c in classifiers if c.startswith(_DEV_STATUS_PREFIX)]
    assert len(matches) == 1, (
        f"{pyproject_path}: expected exactly one '{_DEV_STATUS_PREFIX}' classifier, "
        f"found {len(matches)}: {matches}"
    )
    return matches[0]


def test_development_status_classifiers_are_identical_across_cohort() -> None:
    """All three cohort pyprojects must declare the same Development Status classifier."""
    statuses = {name: _extract_dev_status(path) for name, path in _PYPROJECTS.items()}
    unique_values = set(statuses.values())
    assert len(unique_values) == 1, (
        "Development Status classifiers diverge across cohort distributions:\n"
        + "\n".join(f"  {name}: {value}" for name, value in sorted(statuses.items()))
    )
