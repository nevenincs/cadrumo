"""Conformance proof for the standalone PyPI upload workflow's safety contract.

``pypi-upload.yml`` is a second, standalone publication authority (whether it is
retired in favour of ``publish-release.yml`` is a pending operator decision).
Until that decision, these tests pin the hardening applied to it: it refuses
unless the operator opts in, it cleans a reused runner workspace before the
download so stale artifacts cannot leak into the upload, it never swallows the
download failure, and it publishes only when exactly one wheel and one sdist are
present for the requested package.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "pypi-upload.yml"


def _document() -> Any:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _job() -> Mapping[str, Any]:
    job = _document()["jobs"]["pypi-upload"]
    assert isinstance(job, Mapping)
    return job


def _steps() -> list[Mapping[str, Any]]:
    steps = _job()["steps"]
    assert isinstance(steps, list)
    return [step for step in steps if isinstance(step, Mapping)]


def _run_surface(job: Mapping[str, Any]) -> str:
    steps = job["steps"]
    assert isinstance(steps, list)
    return "\n".join(str(step.get("run", "")) for step in steps if isinstance(step, Mapping) and "run" in step)


def test_opt_in_gate_is_the_first_step() -> None:
    """The workflow refuses unless the operator sets CADRUMO_PUBLISH_ENABLED=true, gated first."""
    first = _steps()[0]
    env = first.get("env", {})
    assert isinstance(env, Mapping)
    assert env.get("PUBLISH_ENABLED") == "${{ vars.CADRUMO_PUBLISH_ENABLED }}"
    run = str(first.get("run", ""))
    assert '"${PUBLISH_ENABLED}" != "true"' in run
    assert "REFUSED: Cadrumo publication is not enabled" in run
    assert "exit 1" in run


def test_reused_workspace_is_cleaned_before_download() -> None:
    """A stale-artifact clean of dist/ precedes the release download step."""
    steps = _steps()
    clean = next(i for i, s in enumerate(steps) if "rm -rf dist" in str(s.get("run", "")))
    download = next(i for i, s in enumerate(steps) if "gh release download" in str(s.get("run", "")))
    assert clean < download


def test_download_failure_is_not_swallowed() -> None:
    """No step masks a failing command with `|| true`; a failed download must abort."""
    assert "|| true" not in _run_surface(_job())


def test_exactly_one_wheel_and_sdist_asserted_before_publish() -> None:
    """A shell guard counts the glob matches and fails unless there is one wheel + one sdist."""
    surface = _run_surface(_job())
    assert "-name '*.whl'" in surface
    assert "-name '*.tar.gz'" in surface
    assert '"$wheels" -ne 1' in surface
    assert '"$sdists" -ne 1' in surface
    # The count guard must run before the publish verb.
    assert surface.index('"$wheels" -ne 1') < surface.index("uv publish")


def test_publish_uses_trusted_publishing() -> None:
    """Upload stays an OIDC Trusted Publishing promotion of the downloaded bytes."""
    assert "uv publish --trusted-publishing always dist/*" in _run_surface(_job())
