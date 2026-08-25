"""Structural gate for the per-push Cadrumo packaging quick workflow.

The quick workflow is the speed-budget per-push probe (one cohort build plus
one installed core smoke per OS). Its load-bearing invariant is evidence
honesty: a quick run mints NOTHING promotable — no draft release, no assets,
no DistributionEvidence rows — so publish-release Gate 2's workflow-path pin
(`.github/workflows/packaging-smoke.yml`) structurally refuses it. These
gates keep the quick profile from quietly growing back into the full
campaign or into an evidence producer.
"""

from __future__ import annotations

from typing import Any, Final

import pytest
import yaml

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_QUICK: Final = _WORKFLOWS_DIR / "packaging-quick.yml"
_SMOKE: Final = _WORKFLOWS_DIR / "packaging-smoke.yml"

_EXPECTED_JOBS: Final = {
    "quick-linux": ["self-hosted", "Linux", "X64"],
    "quick-windows": ["self-hosted", "Windows", "X64"],
    "quick-macos": ["self-hosted", "macOS", "ARM64"],
}


def _quick_document() -> dict[str, Any]:
    return yaml.safe_load(_QUICK.read_text(encoding="utf-8"))


def _run_surface(document: dict[str, Any]) -> str:
    return "\n".join(
        str(step.get("run", ""))
        for job in document["jobs"].values()
        for step in (job.get("steps") or [])
        if isinstance(step, dict)
    )


def test_quick_workflow_is_exactly_three_probe_jobs() -> None:
    """One probe job per OS, no matrix, each running the quick recipe with a hard ceiling."""
    document = _quick_document()
    assert document["name"] == "Cadrumo Packaging Quick"
    # The watchdog is not a probe leg and carries no OS profile; it exists so a
    # probe leg whose runner is offline fails fast instead of queueing.
    assert set(document["jobs"]) == set(_EXPECTED_JOBS) | {"runner-queue-watchdog"}
    for job_name, runs_on in _EXPECTED_JOBS.items():
        job = document["jobs"][job_name]
        assert job["runs-on"] == runs_on, job_name
        assert "strategy" not in job, f"{job_name}: the quick profile must not grow a flavor matrix"
        # Per-push budget enforcement: a wedged probe dies inside the ceiling,
        # never inherits the 6-hour default.
        assert job["timeout-minutes"] <= 25, job_name
        commands = [str(step.get("run", "")).strip() for step in job["steps"] if "run" in step]
        assert "just packaging-quick" in commands, job_name


def test_quick_workflow_mints_no_promotable_evidence() -> None:
    """No draft, no assets, no evidence rows, no write permission — ever."""
    document = _quick_document()
    surface = _run_surface(document)
    assert "gh release" not in surface
    assert "gh run" not in surface
    assert "EVIDENCE_TAG" not in _QUICK.read_text(encoding="utf-8")
    for module in ("oracle_emit_cohort", "evidence_release", "distribution_evidence", "dev.packaging.evidence"):
        assert module not in surface, module
    assert document["permissions"] == {"contents": "read"}
    for job_name, job in document["jobs"].items():
        # Evidence honesty is a CONTENTS question: a draft release and the assets
        # hanging off it are what make a run promotable, and no job in this lane
        # may reach them. `actions: write` is a different capability — it cancels
        # workflow runs and mints nothing — and exactly one job is allowed to
        # hold it, because cancelling is the only way to turn a lane no runner
        # can serve into a terminal state instead of a six-hour silent queue.
        permissions = job.get("permissions") or {}
        assert set(permissions) <= {"actions", "contents"}, f"{job_name}: unexpected permission scope"
        assert permissions.get("contents", "read") == "read", f"{job_name} must not escalate to contents:write"
        if permissions.get("actions") == "write":
            assert job_name == "runner-queue-watchdog", f"{job_name} must not take actions:write"
        for step in job["steps"]:
            uses = str(step.get("uses", ""))
            assert "upload-artifact" not in uses and "download-artifact" not in uses, job_name


def test_quick_workflow_triggers_on_artifact_relevant_pushes() -> None:
    """Main pushes complete the quick workflow while superseded pull requests cancel."""
    document = _quick_document()
    triggers = document[True] if True in document else document["on"]
    assert set(triggers) == {"workflow_dispatch", "push", "pull_request"}
    push = triggers["push"]
    assert push["branches"] == ["main"]
    assert ".vault/**" in push["paths-ignore"]
    assert "**.md" in push["paths-ignore"]
    concurrency = document["concurrency"]
    assert concurrency["group"] == "${{ github.workflow }}-${{ github.ref }}"
    assert concurrency["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}"
    # Future pull-request flow: same T1 probe, but never fork code on the fleet —
    # every job must carry the same-repo guard (see test_change_class_tiers).
    assert triggers["pull_request"]["branches"] == ["main"]


def test_full_campaign_is_dispatch_only() -> None:
    """The full campaign never runs per-push; quick carries the per-push signal.

    Gate 2 accepts historical push-event campaign runs, but the workflow
    itself must no longer start on push — the 20-30 minute matrix per push is
    exactly what the 2026-07-20 operator speed directive retired.
    """
    document = yaml.safe_load(_SMOKE.read_text(encoding="utf-8"))
    triggers = document[True] if True in document else document["on"]
    trigger_names = {triggers} if isinstance(triggers, str) else set(triggers)
    assert trigger_names == {"workflow_dispatch"}
