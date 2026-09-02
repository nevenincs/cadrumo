"""Conformance gates for the classifiers shared by the release cohort."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from pathlib import Path

import pytest

from ...ci.python_runtime_matrix import load_runtime_inventory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).parents[3]

_PYPROJECTS = {
    "root": _REPO_ROOT / "pyproject.toml",
    "cadrumo_data_manuals": _REPO_ROOT / "packaging" / "cadrumo_data_manuals" / "pyproject.toml",
    "cadrumo_data_official": _REPO_ROOT / "packaging" / "cadrumo_data_official" / "pyproject.toml",
}

_DEV_STATUS_PREFIX = "Development Status ::"
_PYTHON_CLASSIFIER_PREFIX = "Programming Language :: Python :: "
_PYTHON_MINOR_RE = re.compile(r"^3\.\d+$")
_INVENTORY_PATH = _REPO_ROOT / "dev" / "ci" / "python-runtime-matrix.json"


def _extract_dev_status(pyproject_path: Path) -> str:
    """Return the single Development Status classifier value from a pyproject.toml."""
    with pyproject_path.open("rb") as fh:
        data = tomllib.load(fh)
    classifiers: list[str] = data.get("project", {}).get("classifiers", [])
    matches = [c for c in classifiers if c.startswith(_DEV_STATUS_PREFIX)]
    assert len(matches) == 1, (
        f"{pyproject_path}: expected exactly one '{_DEV_STATUS_PREFIX}' classifier, found {len(matches)}: {matches}"
    )
    return matches[0]


def _extract_python_minors(pyproject_path: Path) -> frozenset[str]:
    """Return exact CPython minor classifiers from one project declaration."""
    with pyproject_path.open("rb") as fh:
        data = tomllib.load(fh)
    classifiers: list[str] = data.get("project", {}).get("classifiers", [])
    minors: set[str] = set()
    for classifier in classifiers:
        if not classifier.startswith(_PYTHON_CLASSIFIER_PREFIX):
            continue
        minor = classifier.removeprefix(_PYTHON_CLASSIFIER_PREFIX)
        assert _PYTHON_MINOR_RE.fullmatch(minor), (
            f"{pyproject_path}: Python classifiers must identify an exact 3.x minor, got {classifier!r}"
        )
        minors.add(minor)
    return frozenset(minors)


def _assert_python_classifier_policy(
    classifiers: Mapping[str, frozenset[str]],
    *,
    eligible_minors: frozenset[str],
    prerelease_minor: str,
) -> None:
    """Enforce one proven stable classifier set across the release cohort."""
    unique_sets = set(classifiers.values())
    assert len(unique_sets) == 1, "Python runtime classifiers diverge across cohort distributions:\n" + "\n".join(
        f"  {name}: {sorted(value)}" for name, value in sorted(classifiers.items())
    )
    claimed = next(iter(unique_sets), frozenset())
    assert claimed == eligible_minors, (
        "Python runtime classifiers must equal the inventory's proven stable rows: "
        f"claimed={sorted(claimed)}, eligible={sorted(eligible_minors)}"
    )
    assert prerelease_minor not in claimed, f"prerelease runtime {prerelease_minor} cannot receive a stable classifier"


def test_development_status_classifiers_are_identical_across_cohort() -> None:
    """All three cohort pyprojects must declare the same Development Status classifier."""
    statuses = {name: _extract_dev_status(path) for name, path in _PYPROJECTS.items()}
    unique_values = set(statuses.values())
    assert len(unique_values) == 1, "Development Status classifiers diverge across cohort distributions:\n" + "\n".join(
        f"  {name}: {value}" for name, value in sorted(statuses.items())
    )


def test_python_runtime_classifiers_match_proven_inventory_rows() -> None:
    """All cohort packages claim exactly the stable runtimes proven by inventory."""
    inventory = load_runtime_inventory(_INVENTORY_PATH)
    classifiers = {name: _extract_python_minors(path) for name, path in _PYPROJECTS.items()}
    eligible_minors = frozenset(row.minor for row in inventory.stable if row.classifier_eligible)

    _assert_python_classifier_policy(
        classifiers,
        eligible_minors=eligible_minors,
        prerelease_minor=inventory.next.minor,
    )


def test_python_classifier_gate_detects_divergence() -> None:
    """A companion that drifts from the root cannot pass the parity contract."""
    inventory = load_runtime_inventory(_INVENTORY_PATH)
    classifiers = {name: _extract_python_minors(path) for name, path in _PYPROJECTS.items()}
    classifiers["cadrumo_data_manuals"] = frozenset({"3.13", "3.14"})

    with pytest.raises(AssertionError, match="diverge"):
        _assert_python_classifier_policy(
            classifiers,
            eligible_minors=frozenset({"3.13"}),
            prerelease_minor=inventory.next.minor,
        )


def test_python_classifier_gate_rejects_unproven_and_prerelease_rows() -> None:
    """A stable-looking or prerelease classifier cannot outrun inventory evidence."""
    inventory = load_runtime_inventory(_INVENTORY_PATH)
    classifiers = {name: frozenset({"3.13", "3.15"}) for name in _PYPROJECTS}

    with pytest.raises(AssertionError, match="equal the inventory"):
        _assert_python_classifier_policy(
            classifiers,
            eligible_minors=frozenset({"3.13"}),
            prerelease_minor=inventory.next.minor,
        )
