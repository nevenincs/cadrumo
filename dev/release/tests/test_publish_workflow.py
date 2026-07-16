"""Structural proof that release publication stays fail-closed."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "publish.yml"
_JUSTFILE = _REPO_ROOT / "justfile"


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
