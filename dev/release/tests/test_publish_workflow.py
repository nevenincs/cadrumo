"""Structural proof that release publication stays fail-closed."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "publish.yml"
_JUSTFILE = _REPO_ROOT / "justfile"

# Structural denylist for a build/publish invocation inside any validate-job step.
# The `\s+` between a tool and its subcommand makes a differently-spelled variant
# (a double-spaced `uv  build`, a tab, or a line continuation) match the same rule,
# closing the gap the exact-substring `"uv build" not in workflow_text` guards leave.
_BUILD_PUBLISH_RUN_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\buv\s+build\b", re.IGNORECASE),
    re.compile(r"\buv\s+publish\b", re.IGNORECASE),
    re.compile(r"\bpython[0-9.]*\s+-m\s+build\b", re.IGNORECASE),
    re.compile(r"\bpython[0-9.]*\s+-m\s+twine\b", re.IGNORECASE),
    re.compile(r"\btwine\s+upload\b", re.IGNORECASE),
    re.compile(r"\bpip[0-9.]*\s+wheel\b", re.IGNORECASE),
    re.compile(r"\b(?:poetry|flit|hatch|pdm)\s+(?:build|publish)\b", re.IGNORECASE),
    re.compile(r"\bsetup\.py\b[^\n]*\b(?:sdist|bdist_wheel|bdist|upload|build)\b", re.IGNORECASE),
    re.compile(r"\bgh\s+release\s+(?:create|upload|edit|delete)\b", re.IGNORECASE),
)
# Publish-capable third-party actions denied in a read-only validate job's `uses`.
_PUBLISH_USES_MARKERS: Final[tuple[str, ...]] = (
    "gh-action-pypi-publish",
    "pypi-publish",
    "action-gh-release",
)


def _build_publish_invocations(step: Mapping[str, object]) -> list[str]:
    """Return every build/publish tool a single workflow step would invoke."""
    hits: list[str] = []
    run = step.get("run")
    if isinstance(run, str):
        for pattern in _BUILD_PUBLISH_RUN_PATTERNS:
            hits.extend(" ".join(match.group(0).split()) for match in pattern.finditer(run))
    uses = step.get("uses")
    if isinstance(uses, str):
        lowered = uses.lower()
        hits.extend(f"uses:{marker}" for marker in _PUBLISH_USES_MARKERS if marker in lowered)
    return hits


def test_release_candidate_workflow_has_one_run_bound_validation_authority() -> None:
    """One successful packaging run supplies the retained diagnostic candidate."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    dispatch = document[True]["workflow_dispatch"]
    assert set(dispatch["inputs"]) == {"packaging_run_id"}
    assert document["permissions"] == {"actions": "read", "contents": "read"}
    assert set(document["jobs"]) == {"validate"}

    validate = document["jobs"]["validate"]
    surface = "\n".join(str(step.get("run", "")) for step in validate["steps"] if "run" in step)
    assert ".github/workflows/packaging-smoke.yml" in surface
    assert 'conclusion" != "success' in surface
    assert "cadrumo-python-cohort" in surface
    assert "cadrumo-packaging-smoke-evidence" in surface
    assert "dev.release.promote_python_cohort" in surface
    assert "--check-pypi" in surface
    checkout = next(step for step in validate["steps"] if str(step.get("uses", "")).startswith("actions/checkout@"))
    assert checkout["with"]["ref"] == "${{ steps.source-run.outputs.source_commit }}"


def test_publication_stays_absent_until_the_complete_cohort_gate_exists() -> None:
    """The diagnostic can verify retained bytes but has no upload capability."""
    workflow_text = _WORKFLOW.read_text(encoding="utf-8")
    just_text = _JUSTFILE.read_text(encoding="utf-8")

    assert "uv build" not in workflow_text
    assert "uv publish" not in workflow_text
    assert "id-token: write" not in workflow_text
    assert "pypi-data-manuals" not in workflow_text
    assert "pypi-data-official" not in workflow_text
    assert "\n    environment: pypi\n" not in workflow_text
    assert "UV_PUBLISH_TOKEN" not in workflow_text
    assert "UV_PUBLISH_TOKEN" not in just_text
    assert "publish-data confirm" not in just_text
    assert '\npublish confirm=""' not in just_text
    assert "Publication remains blocked until the full plugin, MCPB, Scoop, Homebrew" in workflow_text


def test_no_validate_step_invokes_a_build_or_publish_tool() -> None:
    """Structurally scan every validate-job step so no build/publish tool can slip past."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["validate"]["steps"]
    assert steps, "validate job has no steps to scan"

    invocations = {
        str(step.get("name", f"step[{index}]")): hits
        for index, step in enumerate(steps)
        if (hits := _build_publish_invocations(step))
    }

    assert invocations == {}, f"validate job invokes build/publish tooling: {invocations}"


def test_build_publish_denylist_catches_differently_spelled_invocations() -> None:
    """The scanner flags variants the exact-substring guards miss, and leaves benign steps."""
    forbidden: tuple[Mapping[str, object], ...] = (
        {"run": "uv  build"},
        {"run": "uv\tpublish"},
        {"run": "python -m build"},
        {"run": "python3.11 -m build --wheel"},
        {"run": "python -m twine upload dist/*"},
        {"run": "twine upload dist/*"},
        {"run": "pip wheel ."},
        {"run": "poetry publish --build"},
        {"run": "hatch build"},
        {"run": "python setup.py sdist bdist_wheel"},
        {"run": "gh release create v1.0.0 dist/*"},
        {"uses": "pypa/gh-action-pypi-publish@release/v1"},
        {"uses": "softprops/action-gh-release@v2"},
    )
    for step in forbidden:
        assert _build_publish_invocations(step), f"scanner missed a build/publish variant: {step}"

    benign: tuple[Mapping[str, object], ...] = (
        {"uses": "actions/checkout@v4"},
        {"uses": "astral-sh/setup-uv@v5"},
        {"run": 'gh run download "$PACKAGING_RUN_ID" --name cadrumo-python-cohort'},
        {"run": "uv run --frozen python -m dev.release.promote_python_cohort --check-pypi"},
        {"run": "echo 'Publication remains blocked until the full GitHub release evidence set exists.'"},
    )
    for step in benign:
        assert _build_publish_invocations(step) == [], f"scanner false-positive on a benign step: {step}"
