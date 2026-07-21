"""Structural gate: CI lanes are sized for the shared machines, never `-n auto`.

The fleet is six runners on TWO physical machines (three per box, see
`.github/README.md`), so a lane that sizes itself as if it owns the machine
(`pytest -n auto` grabbing every logical CPU) over-subscribes whatever runs
beside it. Every CI pytest invocation must carry an explicit worker count, the
packaging campaign legs must pass their per-machine sizing env, and the
Homebrew matrix — three of whose four legs live on the one MacBook — must be
parallelism-bounded.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = Path(__file__).resolve().parents[3] / ".github" / "workflows"
_EXPLICIT_WORKERS: Final = re.compile(r"pytest\b[^\n]*\s-n\s*\d+")


def _document(name: str) -> dict[str, Any]:
    return yaml.safe_load((_WORKFLOWS_DIR / name).read_text(encoding="utf-8"))


def _pytest_lines(document: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for job in document["jobs"].values():
        for step in job.get("steps") or []:
            for line in str(step.get("run", "")).splitlines():
                if "pytest" in line:
                    lines.append(line.strip())
    return lines


@pytest.mark.parametrize(
    "workflow",
    ("ci.yml", "ci-full.yml", "agent-harness-eval.yml", "aeat-drift-detector.yml"),
)
def test_ci_pytest_invocations_carry_explicit_worker_counts(workflow: str) -> None:
    """Every CI pytest run line declares an explicit ``-n <int>``.

    ``-n auto`` — spelled out or inherited from the addopts default — must
    never reach a shared machine from CI.
    """
    lines = _pytest_lines(_document(workflow))
    assert lines, f"{workflow} carries no pytest invocation to gate"
    for line in lines:
        assert "-n auto" not in line, (workflow, line)
        assert _EXPLICIT_WORKERS.search(line) or re.search(r"pytest\b[^\n]*\s-n0\b", line), (workflow, line)


def test_campaign_legs_pass_machine_share_sizing() -> None:
    """Each packaging-smoke campaign step sets the per-machine sizing env.

    Workstation legs (24 logical CPUs / 3 runners) get 8 test workers; the
    MacBook leg (6 CPUs / 3 runners) gets 2; lane concurrency is bounded per
    leg. The campaign driver turns CADRUMO_TEST_WORKERS into an explicit
    `-n N` on its preflight pytest pass.
    """
    document = _document("packaging-smoke.yml")
    campaign_steps = [
        step
        for job in document["jobs"].values()
        for step in job.get("steps") or []
        if "packaging campaign" in str(step.get("name", ""))
    ]
    assert len(campaign_steps) == 3, [step.get("name") for step in campaign_steps]
    sizes = sorted(
        (step["env"]["CADRUMO_TEST_WORKERS"], step["env"]["CADRUMO_PACKAGING_LANE_CONCURRENCY"])
        for step in campaign_steps
    )
    assert sizes == [("2", "2"), ("8", "2"), ("8", "3")], sizes


def test_homebrew_matrix_is_parallelism_bounded_with_per_leg_make_jobs() -> None:
    """Three of the four homebrew legs share the MacBook: bound them.

    ``max-parallel: 2`` caps co-landing legs, and brew's build-from-source
    parallelism is sized per leg via ``HOMEBREW_MAKE_JOBS``.
    """
    document = _document("packaging-homebrew.yml")
    strategy = document["jobs"]["cadrumo-homebrew-acquisition"]["strategy"]
    assert strategy["max-parallel"] == 2
    rows = strategy["matrix"]["include"]
    jobs_by_id = {row["id"]: row["make_jobs"] for row in rows}
    assert jobs_by_id == {
        "macos-arm64": "2",
        "macos-intel": "2",
        "linux-arm64": "2",
        "linux-x86_64": "8",
    }
    audit = next(
        step
        for job in document["jobs"].values()
        for step in job.get("steps") or []
        if step.get("name") == "Audit install and exercise Cadrumo through Homebrew"
    )
    assert audit["env"]["HOMEBREW_MAKE_JOBS"] == "${{ matrix.make_jobs }}"
