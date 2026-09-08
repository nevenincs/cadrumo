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

#: The roster is derived, never restated. A hand-written roster passes green
#: over a companion project it does not name: the new distribution's
#: classifiers are simply never compared, and no assertion here can notice an
#: absence it was never told about. The floor keeps an empty or truncated glob
#: from satisfying a comparison between two nearly empty sides.
_MINIMUM_COHORT_PYPROJECTS = 3


def _cohort_pyprojects(root: Path) -> dict[str, Path]:
    """Return every packaging manifest the release cohort publishes, keyed by name."""
    companions = sorted((root / "packaging").glob("*/pyproject.toml"))
    manifests = {"root": root / "pyproject.toml"}
    manifests.update({path.parent.name: path for path in companions})
    return manifests


_PYPROJECTS = _cohort_pyprojects(_REPO_ROOT)
assert len(_PYPROJECTS) >= _MINIMUM_COHORT_PYPROJECTS, (
    f"the cohort classifier roster derived only {sorted(_PYPROJECTS)} from {_REPO_ROOT}"
)

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
    """Every cohort pyproject must declare the same Development Status classifier."""
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
    classifiers["cadrumo_data_manuals"] = frozenset({"3.13"})

    with pytest.raises(AssertionError, match="diverge"):
        _assert_python_classifier_policy(
            classifiers,
            eligible_minors=frozenset({"3.13", "3.14"}),
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


def test_the_roster_covers_every_packaging_manifest_on_disk(tmp_path: Path) -> None:
    """A companion added under ``packaging/`` joins the roster without an edit here."""
    assert set(_PYPROJECTS) == {"root", "cadrumo_data_manuals", "cadrumo_data_official"}

    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    for companion in ("cadrumo_data_manuals", "cadrumo_data_official", "cadrumo_data_forms"):
        manifest = tmp_path / "packaging" / companion / "pyproject.toml"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("", encoding="utf-8")

    assert set(_cohort_pyprojects(tmp_path)) == {
        "root",
        "cadrumo_data_manuals",
        "cadrumo_data_official",
        "cadrumo_data_forms",
    }


#: ``requires-python`` is the field that actually gates installation, and it is
#: the one cohort metadata field joined to nothing. The inventory calls
#: ``minimum_minor`` "the package floor", but no package reads it: the value is
#: consumed only inside its own module, to shape the stable sequence. So the
#: floor is declared twice over -- once in the inventory, once per manifest --
#: and the two spellings are free to disagree.
#:
#: The reachable way in is a routine floor bump, not sabotage. When a dependency
#: drops a minor, the author raises ``minimum_minor``, raises the root manifest,
#: and is FORCED to fix the classifiers by the parity gate above. Nothing
#: mentions the companions. Their wheels keep advertising the old floor, stay
#: installable on a runtime the root now refuses, and no job fails: a wheel that
#: installs is not an error anywhere. The cohort splits in the direction only a
#: user on the dropped runtime can see.
_REQUIRES_PYTHON_RE = re.compile(r"^>=\s*(?P<minor>3\.\d+)$")


def _extract_requires_python(pyproject_path: Path) -> str:
    """Return the ``project.requires-python`` specifier declared by a manifest."""
    with pyproject_path.open("rb") as fh:
        data = tomllib.load(fh)
    declared = data.get("project", {}).get("requires-python")
    assert isinstance(declared, str) and declared, (
        f"{pyproject_path}: declares no `project.requires-python` floor to compare"
    )
    return declared


def _assert_requires_python_policy(declared: Mapping[str, str], *, minimum_minor: str) -> None:
    """Enforce one installation floor across the cohort, joined to the inventory.

    The specifier is parsed rather than string-compared so a legitimate
    respelling reds nothing, while an upper bound -- which would make a
    published wheel refuse a runtime the inventory proves -- still cannot pass.
    """
    floors: dict[str, str] = {}
    for name, specifier in sorted(declared.items()):
        match = _REQUIRES_PYTHON_RE.fullmatch(specifier.strip())
        assert match is not None, f"{name}: requires-python must be a bare '>=3.N' floor, got {specifier!r}"
        floors[name] = match.group("minor")
    unique_floors = set(floors.values())
    assert len(unique_floors) == 1, "installation floors diverge across cohort distributions:\n" + "\n".join(
        f"  {name}: {value}" for name, value in sorted(floors.items())
    )
    claimed = next(iter(unique_floors), "")
    assert claimed == minimum_minor, (
        "the cohort installation floor must equal the inventory's declared minimum: "
        f"claimed={claimed!r}, minimum_minor={minimum_minor!r}"
    )


def test_requires_python_floor_is_shared_and_matches_the_inventory_minimum() -> None:
    """Every cohort manifest names the floor the runtime inventory declares."""
    inventory = load_runtime_inventory(_INVENTORY_PATH)
    declared = {name: _extract_requires_python(path) for name, path in _PYPROJECTS.items()}

    _assert_requires_python_policy(declared, minimum_minor=inventory.minimum_minor)


def test_the_floor_gate_detects_a_companion_left_behind_by_a_bump() -> None:
    """The routine defect: the root is raised and a companion is not."""
    declared = {name: ">=3.14" for name in _PYPROJECTS}
    declared["cadrumo_data_manuals"] = ">=3.13"

    with pytest.raises(AssertionError, match="floors diverge"):
        _assert_requires_python_policy(declared, minimum_minor="3.14")


def test_the_floor_gate_detects_a_cohort_that_agrees_but_lags_the_inventory() -> None:
    """Unanimity is not correctness: every manifest can be stale together."""
    declared = {name: ">=3.13" for name in _PYPROJECTS}

    with pytest.raises(AssertionError, match="equal the inventory"):
        _assert_requires_python_policy(declared, minimum_minor="3.14")


def test_the_floor_gate_refuses_an_upper_bound_that_would_cap_a_proven_runtime() -> None:
    """A capped specifier refuses a runtime the inventory proves, so it cannot pass."""
    declared = {name: ">=3.13,<3.14" for name in _PYPROJECTS}

    with pytest.raises(AssertionError, match=r"bare '>=3\.N' floor"):
        _assert_requires_python_policy(declared, minimum_minor="3.13")
