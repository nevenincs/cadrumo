"""Structural gate: every workflow job runs on the self-hosted fleet only.

Operator mandate 2026-07-21: NO hosted/cloud runners were ever authorized —
expense control is absolute, and the ARM MacBook is the only permitted
non-workstation avenue. Every ``runs-on`` (including every matrix value
feeding one, list-dimension or include-row alike, in ``.yml`` and ``.yaml``
workflows both) must be a self-hosted label set; a GitHub-hosted image
(``ubuntu-latest``, ``windows-2022``, ``macos-15-intel``,
``ubuntu-24.04-arm``, ...) anywhere in the tree is a spend regression this
gate refuses. Fail-closed: a matrix-referencing ``runs-on`` that resolves to
zero concrete targets is itself a violation, never a silent pass. No workflow
is exempt.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from cadrumo.core import scan_directory

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_MATRIX_DIMENSION: Final = re.compile(r"matrix\.([A-Za-z_][\w-]*)")
_UNRESOLVED: Final = "<matrix runs-on resolved to zero targets>"


def _runner_targets(job: dict[str, Any]) -> list[object]:
    """Resolve a job's concrete runner targets, expanding matrix indirection.

    Both matrix shapes feed targets: ``include`` rows carrying the referenced
    key, and a top-level list dimension of the same name (``matrix.os:
    [ubuntu-latest]``). A matrix reference that resolves to nothing returns a
    sentinel so the gate refuses rather than silently passing zero targets.
    """
    runs_on = job.get("runs-on")
    if not (isinstance(runs_on, str) and "matrix" in runs_on):
        return [runs_on]
    matrix = (job.get("strategy") or {}).get("matrix") or {}
    dimension_match = _MATRIX_DIMENSION.search(runs_on)
    dimension = dimension_match.group(1) if dimension_match else None
    targets: list[object] = []
    for row in matrix.get("include") or []:
        if isinstance(row, dict) and dimension in row:
            targets.append(row[dimension])
    top_level = matrix.get(dimension)
    if isinstance(top_level, list):
        targets.extend(top_level)
    return targets or [_UNRESOLVED]


def _collect_violations(workflows_dir: Path) -> list[tuple[str, str, object]]:
    """Return every (workflow, job, target) whose runner is not self-hosted."""
    workflows = sorted(
        {*scan_directory(workflows_dir, pattern="*.yml"), *scan_directory(workflows_dir, pattern="*.yaml")}
    )
    assert workflows, f"no workflows found to gate under {workflows_dir}"
    violations: list[tuple[str, str, object]] = []
    for workflow in workflows:
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        for job_name, job in (document.get("jobs") or {}).items():
            for target in _runner_targets(job):
                if not (isinstance(target, list) and target and target[0] == "self-hosted"):
                    violations.append((workflow.name, job_name, target))
    return violations


def test_every_workflow_job_runs_on_the_self_hosted_fleet() -> None:
    """Zero GitHub-hosted runner images anywhere; no workflow is exempt."""
    violations = _collect_violations(_WORKFLOWS_DIR)
    assert violations == [], f"hosted (or unresolvable) runner targets found: {violations}"


def test_gate_refuses_a_hosted_yaml_extension_workflow(tmp_path: Path) -> None:
    """GitHub honors .yaml too; a hosted foo.yaml cannot slip past the glob."""
    (tmp_path / "sneaky.yaml").write_text(
        "name: sneaky\non: workflow_dispatch\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps: []\n",
        encoding="utf-8",
    )
    violations = _collect_violations(tmp_path)
    assert violations == [("sneaky.yaml", "build", "ubuntu-latest")]


def test_gate_refuses_a_hosted_top_level_matrix_dimension(tmp_path: Path) -> None:
    """A list-dimension matrix (matrix.os: [ubuntu-latest]) is expanded and refused."""
    (tmp_path / "matrixed.yml").write_text(
        "name: matrixed\n"
        "on: workflow_dispatch\n"
        "jobs:\n"
        "  build:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        os: [ubuntu-latest, [self-hosted, Linux, X64]]\n"
        "    runs-on: ${{ matrix.os }}\n"
        "    steps: []\n",
        encoding="utf-8",
    )
    violations = _collect_violations(tmp_path)
    assert violations == [("matrixed.yml", "build", "ubuntu-latest")]


def test_gate_fails_closed_on_an_unresolvable_matrix_reference(tmp_path: Path) -> None:
    """A matrix runs-on resolving to zero targets is a violation, never a pass."""
    (tmp_path / "opaque.yml").write_text(
        "name: opaque\n"
        "on: workflow_dispatch\n"
        "jobs:\n"
        "  build:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        other: [x]\n"
        "    runs-on: ${{ matrix.runner }}\n"
        "    steps: []\n",
        encoding="utf-8",
    )
    violations = _collect_violations(tmp_path)
    assert len(violations) == 1
    assert violations[0][:2] == ("opaque.yml", "build")
    assert "zero targets" in str(violations[0][2])
