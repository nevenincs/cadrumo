"""Repository-wide contract for the exact CI Python toolchain pin."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_COMPATIBILITY_WORKFLOW: Final = _WORKFLOWS_DIR / "python-runtime-compatibility.yml"
_PYTHON_VERSION_FILE: Final = REPO_ROOT / ".python-version"
_EXACT_PATCH: Final = re.compile(r"\d+\.\d+\.\d+")
_MATRIX_EXPRESSION: Final = re.compile(r"\$\{\{\s*matrix\.([A-Za-z][\w-]*)\s*\}\}")


def _python_pin() -> str:
    pin = _PYTHON_VERSION_FILE.read_text(encoding="utf-8").strip()
    assert _EXACT_PATCH.fullmatch(pin), ".python-version must select one exact Python patch"
    return pin


def _workflow_documents() -> list[tuple[Path, dict[str, Any]]]:
    paths = sorted((*_WORKFLOWS_DIR.glob("*.yml"), *_WORKFLOWS_DIR.glob("*.yaml")))
    return [(path, yaml.safe_load(path.read_text(encoding="utf-8"))) for path in paths]


def _is_compatibility_matrix_override(*, selection: object, matrix: object, pin: str) -> bool:
    """Return whether an override is a real matrix containing the pin and an alternative."""
    match = _MATRIX_EXPRESSION.fullmatch(str(selection))
    if match is None or not isinstance(matrix, dict):
        return False
    values = matrix.get(match.group(1))
    return (
        isinstance(values, list)
        and pin in {str(value) for value in values}
        and any(str(value) != pin for value in values)
    )


def _assert_setup_uv_consumers_follow_pin(
    documents: list[tuple[Path, dict[str, Any]]],
    *,
    pin: str,
) -> None:
    consumer_found = False
    violations: list[str] = []

    for path, document in documents:
        for job_name, job in (document.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            steps = job.get("steps") or []
            for step_index, step in enumerate(steps):
                if not isinstance(step, dict) or not str(step.get("uses", "")).startswith("astral-sh/setup-uv@"):
                    continue
                consumer_found = True
                selection = (step.get("with") or {}).get("python-version")
                if selection is None:
                    # With no UV_PYTHON override, uv resolves the checked-in
                    # exact .python-version pin itself. The checkout must already
                    # exist when setup-uv establishes the job's toolchain context.
                    checked_out = any(
                        isinstance(previous, dict) and str(previous.get("uses", "")).startswith("actions/checkout@")
                        for previous in steps[:step_index]
                    )
                    if not checked_out:
                        violations.append(f"{path.name}:{job_name}: setup-uv precedes checkout")
                    continue

                matrix = (job.get("strategy") or {}).get("matrix") or {}
                if (
                    path != _COMPATIBILITY_WORKFLOW
                    or not _is_compatibility_matrix_override(selection=selection, matrix=matrix, pin=pin)
                ):
                    violations.append(f"{path.name}:{job_name}: {selection!r}")

    assert consumer_found, "no setup-uv consumer was found; the CI Python pin contract has no live surface"
    assert violations == [], (
        "setup-uv Python overrides bypass .python-version unless they are a "
        f"compatibility matrix containing the exact pin and an alternative: {violations}"
    )


def test_setup_uv_consumers_follow_the_repository_python_pin() -> None:
    """Ordinary jobs defer to .python-version; genuine compatibility matrices may vary."""
    _assert_setup_uv_consumers_follow_pin(_workflow_documents(), pin=_python_pin())


def test_empty_setup_uv_surface_is_rejected() -> None:
    """Deleting every consumer cannot make the repository-wide gate pass vacuously."""
    with pytest.raises(AssertionError, match="no setup-uv consumer was found"):
        _assert_setup_uv_consumers_follow_pin([], pin=_python_pin())


@pytest.mark.parametrize(
    ("selection", "matrix", "expected"),
    [
        ("${{ matrix.python-version }}", {"python-version": ["{pin}", "3.13t"]}, True),
        ("${{ matrix.python-version }}", {"python-version": ["3.13t", "3.12"]}, False),
        ("${{ matrix.python-version }}", {"python-version": ["{pin}"]}, False),
        ("3.13", {}, False),
        ("${{ inputs.python-version }}", {"python-version": ["{pin}", "3.13t"]}, False),
        ("${{ matrix.python-version }}", {"other-version": ["{pin}", "3.13t"]}, False),
    ],
    ids=(
        "canonical-pin-and-alternative",
        "missing-canonical-pin",
        "canonical-pin-without-alternative",
        "loose-literal",
        "non-matrix-expression",
        "mismatched-matrix-key",
    ),
)
def test_compatibility_matrix_override_classifier(
    selection: str,
    matrix: dict[str, list[str]],
    expected: bool,
) -> None:
    """Only the deliberate compatibility-matrix exception is accepted."""
    pin = _python_pin()
    resolved_matrix = {key: [pin if value == "{pin}" else value for value in values] for key, values in matrix.items()}
    assert _is_compatibility_matrix_override(selection=selection, matrix=resolved_matrix, pin=pin) is expected


def test_release_cohort_enforces_the_repository_python_pin() -> None:
    """The reproducible cohort builder consumes the same pin as CI."""
    from ...packaging.release_cohort import _REQUIRED_PYTHON_VERSION

    assert _python_pin() == _REQUIRED_PYTHON_VERSION


def test_matrix_override_is_rejected_outside_the_compatibility_workflow() -> None:
    """A second matrix lane cannot quietly replace the release-builder pin."""
    pin = _python_pin()
    foreign = Path("ci.yml")
    documents = [
        (
            foreign,
            {
                "jobs": {
                    "foreign-matrix": {
                        "steps": [
                            {"uses": "actions/checkout@v4"},
                            {
                                "uses": "astral-sh/setup-uv@v5",
                                "with": {"python-version": "${{ matrix.python-version }}"},
                            },
                        ],
                        "strategy": {"matrix": {"python-version": [pin, "3.15"]}},
                    },
                },
            },
        ),
    ]

    with pytest.raises(AssertionError, match="bypass"):
        _assert_setup_uv_consumers_follow_pin(documents, pin=pin)
