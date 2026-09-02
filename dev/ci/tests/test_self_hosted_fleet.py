"""Structural gate: every workflow job runs on the self-hosted fleet only.

Operator mandate 2026-07-21: NO hosted/cloud runners were ever authorized —
expense control is absolute, and the ARM MacBook is the only permitted
non-workstation avenue. Every ``runs-on`` (including every matrix value
feeding one, list-dimension or include-row alike, in ``.yml`` and ``.yaml``
workflows both) must be a self-hosted label set; a GitHub-hosted image
(``ubuntu-latest``, ``windows-2022``, ``macos-15-intel``,
``ubuntu-24.04-arm``, ...) anywhere in the tree is a spend regression this
gate refuses. Fail-closed: a matrix-referencing ``runs-on`` that resolves to
zero concrete targets is itself a violation, never a silent pass.

The release path is exempt as a whole, enumerated in :data:`HOSTED_WORKFLOWS`
and pinned in both directions by the tests below. It is not a softening of the
mandate: those workflows build a `py3-none-any` artifact the host cannot
affect, and publication must not be gated on a fleet runner being free. The
spend premise does not apply either - this repository is public, and hosted
runners are free for public repositories.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_MATRIX_DIMENSION: Final = re.compile(r"matrix\.([A-Za-z_][\w-]*)")
_UNRESOLVED: Final = "<matrix runs-on resolved to zero targets>"

#: Workflows whose every job runs on a GitHub-hosted image.
#:
#: The release path belongs here for three standing reasons. The distributions
#: are `py3-none-any`, so the build host cannot affect the artifact. The
#: repository is public, so hosted runners cost nothing. And publication must
#: not be gated on a self-hosted runner being free, which this fleet cannot
#: guarantee: it carries one Linux x86-64 runner, and its macOS host serves
#: only on mains power.
#:
#: Every other workflow proves behaviour on a real target platform and stays on
#: the fleet.
HOSTED_WORKFLOWS: Final[frozenset[str]] = frozenset({"release-please.yml", "publish.yml"})



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
        if workflow.name in HOSTED_WORKFLOWS:
            continue
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        for job_name, job in (document.get("jobs") or {}).items():
            for target in _runner_targets(job):
                if not (isinstance(target, list) and target and target[0] == "self-hosted"):
                    violations.append((workflow.name, job_name, target))
    return violations


def test_the_release_path_workflows_run_on_hosted_images() -> None:
    """The hosted split is pinned in BOTH directions.

    A release job that drifts onto the fleet reintroduces the availability
    dependency the split exists to remove, and does so silently: the run does
    not error, it queues behind whatever already holds the runner.
    """
    for workflow_name in sorted(HOSTED_WORKFLOWS):
        workflow = _WORKFLOWS_DIR / workflow_name
        assert workflow.is_file(), f"{workflow_name} is declared hosted but does not exist"
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        jobs = document.get("jobs") or {}
        assert jobs, f"{workflow_name} declares no jobs"
        for job_name, job in jobs.items():
            for target in _runner_targets(job):
                assert isinstance(target, str) and target != _UNRESOLVED, (
                    f"{workflow_name}:{job_name} runs on {target!r}, not a hosted image"
                )


def test_every_workflow_job_runs_on_the_self_hosted_fleet() -> None:
    """Zero GitHub-hosted runner images anywhere; no workflow is exempt."""
    violations = _collect_violations(_WORKFLOWS_DIR)
    assert violations == [], f"hosted (or unresolvable) runner targets found: {violations}"


def test_gate_refuses_a_hosted_job_outside_the_exemption(tmp_path: Path) -> None:
    """The exemption is keyed to the workflow filename, not to the hosted label.

    A job in some other workflow is not part of the release path, so the gate
    must still refuse it. This is what stops the exemption widening into
    "hosted runners are fine if you pick the right job name".
    """
    workflow = tmp_path / "other.yml"
    workflow.write_text(
        """name: other
on: workflow_dispatch
jobs:
  campaign:
    runs-on: ubuntu-latest
    steps: []
""",
        encoding="utf-8",
    )
    assert _collect_violations(tmp_path) == [("other.yml", "campaign", "ubuntu-latest")]


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
