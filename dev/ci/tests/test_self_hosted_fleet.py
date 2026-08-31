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

Exactly two jobs are exempt, enumerated in :data:`POLLING_EXEMPTIONS` and
pinned in both directions by the tests below. They are not a softening of the
mandate: each dispatches a fleet workflow and then BLOCKS on it, so holding a
fleet runner to wait deadlocked against the run it had just dispatched. The
spend premise does not apply to them either - this repository is public, and
GitHub-hosted runners are free for public repositories.
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

#: (workflow, job) pairs permitted to run on `ubuntu-latest`, and nothing else.
#:
#: Both jobs dispatch a packaging workflow and then poll it to completion. Every
#: packaging lane targets `[self-hosted, Linux, X64]`, and this fleet has exactly
#: one such runner, so waiting here occupied the only machine the dispatched run
#: needed and the two waited on each other until the budget expired. Observed on
#: run 33335781162: `campaign` in_progress holding `cadrumo-linux-x64-1` while
#: `packaging-quick` sat queued 52 minutes and never started.
#:
#: The 2026-07-21 mandate is about SPEND and still binds everywhere else. It does
#: not bite here on either count: the work is `gh` plus a polling module, needing
#: nothing the fleet provides, and hosted runners are free for public
#: repositories, which this one is.
POLLING_EXEMPTIONS: Final[frozenset[tuple[str, str]]] = frozenset(
    {("release-orchestrator.yml", "campaign"), ("release-orchestrator.yml", "acquire")}
)
_EXEMPT_TARGET: Final = "ubuntu-latest"


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
            exempt = (workflow.name, job_name) in POLLING_EXEMPTIONS
            for target in _runner_targets(job):
                if exempt and target == _EXEMPT_TARGET:
                    continue
                if not (isinstance(target, list) and target and target[0] == "self-hosted"):
                    violations.append((workflow.name, job_name, target))
    return violations


def test_every_workflow_job_runs_on_the_self_hosted_fleet() -> None:
    """Zero GitHub-hosted runner images anywhere; no workflow is exempt."""
    violations = _collect_violations(_WORKFLOWS_DIR)
    assert violations == [], f"hosted (or unresolvable) runner targets found: {violations}"


def test_the_exempt_polling_jobs_are_still_hosted() -> None:
    """The exemption is pinned in BOTH directions, not merely tolerated.

    A job that quietly drifts back onto the fleet reintroduces the deadlock this
    exemption exists to break, and that failure is invisible - the run does not
    error, it queues behind the very workflow it dispatched. Asserting the
    positive here means the exemption cannot rot into a stale allowance for jobs
    that no longer use it.
    """
    for workflow_name, job_name in sorted(POLLING_EXEMPTIONS):
        document = yaml.safe_load((_WORKFLOWS_DIR / workflow_name).read_text(encoding="utf-8"))
        job = (document.get("jobs") or {}).get(job_name)
        assert job is not None, f"{workflow_name} no longer defines the exempt job {job_name}"
        assert job.get("runs-on") == _EXEMPT_TARGET, (
            f"{workflow_name}:{job_name} is exempt because it dispatches a fleet workflow and "
            f"blocks on it; running it on the fleet deadlocks against the run it dispatched"
        )


def test_gate_refuses_a_hosted_job_outside_the_exemption(tmp_path: Path) -> None:
    """The exemption is keyed to (workflow, job) - not to the hosted label.

    A job merely NAMED `campaign` in some other workflow is not the exempt one,
    so the gate must still refuse it. This is what stops the exemption widening
    into "hosted runners are fine if you pick the right job name".
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
