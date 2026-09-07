"""Repository-wide contract for the exact CI Python toolchain pin.

The pin lives in ``.python-version`` and uv reads it -- unless something names
an interpreter first. ``with: python-version:`` is one way to name one and
``UV_PYTHON`` is the other, and only the first was ever read here: a workflow
declaring ``env: {UV_PYTHON: \"3.12\"}`` beside a bare ``setup-uv`` step ran on
3.12 and reported no violation. Both channels now resolve through
:mod:`dev.ci.workflow_python_selection`, which also keeps the third state
distinct: a file naming no selection is deferring to a value it cannot see,
not proving the pin applies."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from ..._paths import REPO_ROOT
from ..workflow_python_selection import declared_python_selection, uv_python_env

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
                selection = declared_python_selection(document, job_name, step_index)
                if selection is None:
                    # Neither channel names an interpreter, so uv resolves the
                    # checked-in exact .python-version pin. The checkout must already
                    # exist when setup-uv establishes the job's toolchain context.
                    checked_out = any(
                        isinstance(previous, dict) and str(previous.get("uses", "")).startswith("actions/checkout@")
                        for previous in steps[:step_index]
                    )
                    if not checked_out:
                        violations.append(f"{path.name}:{job_name}: setup-uv precedes checkout")
                    continue

                matrix = (job.get("strategy") or {}).get("matrix") or {}
                if path != _COMPATIBILITY_WORKFLOW or not _is_compatibility_matrix_override(
                    selection=selection, matrix=matrix, pin=pin
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


def _uv_step(**extra: Any) -> dict[str, Any]:
    return {"uses": "astral-sh/setup-uv@0000000000000000000000000000000000000000", **extra}


def _checkout() -> dict[str, Any]:
    return {"uses": "actions/checkout@0000000000000000000000000000000000000000"}


@pytest.mark.parametrize(
    "document",
    [
        {"env": {"UV_PYTHON": "3.12"}, "jobs": {"build": {"steps": [_checkout(), _uv_step()]}}},
        {"jobs": {"build": {"env": {"UV_PYTHON": "3.12"}, "steps": [_checkout(), _uv_step()]}}},
        {"jobs": {"build": {"steps": [_checkout(), _uv_step(env={"UV_PYTHON": "3.12"})]}}},
    ],
    ids=("workflow-env", "job-env", "step-env"),
)
def test_a_uv_python_override_is_refused_at_every_env_scope(document: dict[str, Any]) -> None:
    """The pin has two doors, and the gate reads both.

    Measured against uv 0.12.8: two projects pinned identically to 3.13 built a
    3.13 environment and, under ``UV_PYTHON=3.14``, a 3.14 one. So this document
    runs on 3.12 while declaring no ``with: python-version:`` at all, and before
    the selection moved behind one resolver it passed at all three scopes.
    """
    with pytest.raises(AssertionError, match=r"bypass \.python-version"):
        _assert_setup_uv_consumers_follow_pin([(Path("ci.yml"), document)], pin=_python_pin())


def test_the_innermost_uv_python_declaration_wins() -> None:
    """GitHub resolves ``env:`` narrowest-first, so a step override is the answer.

    Without this the resolver could read the outermost declaration and report a
    selection the runtime never applies -- the same "declared text is not the
    effective value" mistake one level down.
    """
    document = {
        "env": {"UV_PYTHON": "3.11"},
        "jobs": {"build": {"env": {"UV_PYTHON": "3.12"}, "steps": [_checkout(), _uv_step(env={"UV_PYTHON": "3.13"})]}},
    }

    assert uv_python_env(document, "build", 1) == "3.13"
    assert uv_python_env(document, "build", 0) == "3.12"


def test_a_step_with_neither_channel_is_unsettled_not_pinned() -> None:
    """Naming no selection is the third state, reported as ``None``.

    A resolver that answered the pin here would be asserting that no ambient
    ``UV_PYTHON`` exists on the runner, which no file in this repository can
    know. The caller pairs the ``None`` with the checkout-ordering check rather
    than treating it as proof.
    """
    document = {"jobs": {"build": {"steps": [_checkout(), _uv_step()]}}}

    assert declared_python_selection(document, "build", 1) is None
    assert uv_python_env(document, "build", 1) is None


def test_the_with_channel_still_outranks_an_ambient_declaration() -> None:
    """An explicit input is the selection setup-uv applies, env or not."""
    document = {
        "env": {"UV_PYTHON": "3.11"},
        "jobs": {"build": {"steps": [_checkout(), _uv_step(**{"with": {"python-version": "3.14"}})]}},
    }

    assert declared_python_selection(document, "build", 1) == "3.14"


def test_the_selection_resolver_refuses_an_unknown_job() -> None:
    """A misspelled job name is a lookup error, never a silent ``None``."""
    with pytest.raises(KeyError, match="no job named"):
        declared_python_selection({"jobs": {"build": {}}}, "absent", 0)
