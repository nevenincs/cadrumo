"""Structural gate: every workflow job runs on the self-hosted fleet only.

Operator mandate 2026-07-21: NO hosted/cloud runners were ever authorized —
expense control is absolute, and the ARM MacBook is the only permitted
non-workstation avenue. Every ``runs-on`` (including every matrix ``runner``
value feeding one) must be a self-hosted label set; a GitHub-hosted image
(``ubuntu-latest``, ``windows-2022``, ``macos-15-intel``,
``ubuntu-24.04-arm``, ...) anywhere in the tree is a spend regression this
gate refuses. No workflow is exempt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import pytest
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = Path(__file__).resolve().parents[3] / ".github" / "workflows"


def _runner_targets(job: dict[str, Any]) -> list[object]:
    """Resolve a job's concrete runner targets, expanding matrix indirection."""
    runs_on = job.get("runs-on")
    if isinstance(runs_on, str) and "matrix" in runs_on:
        matrix = (job.get("strategy") or {}).get("matrix") or {}
        rows = matrix.get("include") or []
        return [row.get("runner") for row in rows]
    return [runs_on]


def test_every_workflow_job_runs_on_the_self_hosted_fleet() -> None:
    """Zero GitHub-hosted runner images anywhere; no workflow is exempt."""
    workflows = sorted(_WORKFLOWS_DIR.glob("*.yml"))
    assert workflows, "no workflows found to gate"
    violations: list[tuple[str, str, object]] = []
    for workflow in workflows:
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        for job_name, job in (document.get("jobs") or {}).items():
            for target in _runner_targets(job):
                if not (isinstance(target, list) and target and target[0] == "self-hosted"):
                    violations.append((workflow.name, job_name, target))
    assert violations == [], f"hosted (or malformed) runner targets found: {violations}"
