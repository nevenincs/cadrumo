"""Structural gates for the change-class tier topology.

The push and pull-request discipline is tiered by change class — T0 vault/docs churn runs
nothing, T1 code changes run the quick profile, T2 release-artifact-shaping
changes auto-dispatch the full campaign, T3 releases bind to the
publish-release gate topology. Classification is structural (path filters and
workflow topology), so these gates pin the boundaries: the T0 carve-out set,
the T2 detector's paths, the fork pull-request guard on every fleet-facing job, the
repo-wide zero-Actions-artifact posture, and the workflow naming convention.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import pytest
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = Path(__file__).resolve().parents[3] / ".github" / "workflows"
_TRIGGER: Final = _WORKFLOWS_DIR / "packaging-campaign-trigger.yml"
_CI: Final = _WORKFLOWS_DIR / "ci.yml"
_QUICK: Final = _WORKFLOWS_DIR / "packaging-quick.yml"
_FULL: Final = _WORKFLOWS_DIR / "ci-full.yml"

# The T0 carve-out: agent/vault/docs churn that never reaches the code or
# artifact surface. Shared verbatim by every per-push T1 workflow so a path
# cannot be T0 for one lane and T1 for another.
_T0_CARVE_OUT: Final = frozenset(
    {".vault/**", ".vaultspec/**", ".claude/**", ".codex/**", ".gemini/**", ".agents/**", "**.md"}
)

# The T2 boundary: the files that define the shipped artifact set. A push
# touching any of these auto-dispatches the full campaign.
_T2_RELEASE_ARTIFACT_SURFACE: Final = frozenset(
    {
        "pyproject.toml",
        "uv.lock",
        "packaging/**",
        "dev/packaging/**",
        ".github/workflows/packaging-smoke.yml",
    }
)

_SAME_REPO_GUARD: Final = (
    "github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository"
)


def _document(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(document: dict[str, Any]) -> Any:
    return document[True] if True in document else document["on"]


def test_t2_trigger_paths_pin_the_release_artifact_surface() -> None:
    """The campaign auto-dispatch fires exactly on the release-artifact paths."""
    document = _document(_TRIGGER)
    triggers = _triggers(document)
    assert set(triggers) == {"push"}
    push = triggers["push"]
    assert push["branches"] == ["main"]
    assert set(push["paths"]) == set(_T2_RELEASE_ARTIFACT_SURFACE)


def test_t2_trigger_dispatches_the_full_campaign_and_nothing_else() -> None:
    """One tiny job that presses the packaging-smoke dispatch button on main."""
    document = _document(_TRIGGER)
    assert "Cadrumo" in document["name"]
    assert document["permissions"] == {"actions": "write", "contents": "read"}
    assert set(document["jobs"]) == {"dispatch-full-campaign"}
    job = document["jobs"]["dispatch-full-campaign"]
    assert job["timeout-minutes"] <= 10
    commands = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "gh workflow run packaging-smoke.yml" in commands
    assert "--ref main" in commands
    # The trigger never runs the campaign inline or mints evidence itself.
    for forbidden in ("just packaging", "campaign.py", "evidence", "gh release"):
        assert forbidden not in commands, forbidden


def test_t0_carve_out_is_shared_by_every_per_push_t1_lane() -> None:
    """ci.yml and packaging-quick.yml agree on what counts as T0 churn."""
    for path in (_CI, _QUICK):
        push = _triggers(_document(path))["push"]
        assert set(push["paths-ignore"]) >= _T0_CARVE_OUT, path.name


def test_every_pull_request_workflow_guards_every_job_against_fork_heads() -> None:
    """Every pull_request workflow carries the same-repo guard on every job.

    Fork pull-request head code must never execute on the self-hosted fleet.
    """
    for path in sorted({*_WORKFLOWS_DIR.glob("*.yml"), *_WORKFLOWS_DIR.glob("*.yaml")}):
        document = _document(path)
        if "pull_request" not in set(_triggers(document)):
            continue
        for job_name, job in document["jobs"].items():
            assert job.get("if") == _SAME_REPO_GUARD, f"{path.name}:{job_name} lacks the fork guard"


def test_no_workflow_anywhere_uses_actions_artifact_storage() -> None:
    """Zero-Actions-artifact posture, promoted from per-family to repo-wide.

    Evidence rides draft releases; diagnostics live in job logs.
    """
    offending: list[str] = []
    for path in sorted({*_WORKFLOWS_DIR.glob("*.yml"), *_WORKFLOWS_DIR.glob("*.yaml")}):
        document = _document(path)
        for job_name, job in (document.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                uses = str(step.get("uses", ""))
                if "upload-artifact" in uses or "download-artifact" in uses:
                    offending.append(f"{path.name}:{job_name}")
    assert offending == [], offending


def test_no_workflow_carries_a_schedule_trigger() -> None:
    """Operator ruling 2026-07-21: manual cadence, no standing compute.

    The project is not developed continuously, so every lane is dispatch-,
    push-, or pull-request-triggered; a schedule trigger anywhere is creeping standing
    compute this gate refuses.
    """
    for path in sorted({*_WORKFLOWS_DIR.glob("*.yml"), *_WORKFLOWS_DIR.glob("*.yaml")}):
        assert "schedule" not in set(_triggers(_document(path))), path.name


def test_every_workflow_name_carries_the_product_identity() -> None:
    """Naming convention: kebab-case filenames, `name:` contains "Cadrumo"."""
    for path in sorted({*_WORKFLOWS_DIR.glob("*.yml"), *_WORKFLOWS_DIR.glob("*.yaml")}):
        document = _document(path)
        assert "Cadrumo" in document["name"], path.name
        assert path.stem == path.stem.lower(), path.name


def test_durable_maintenance_gates_moved_into_the_full_lane() -> None:
    """The retired weekly workflow's two gates live on in ci-full.yml.

    The vault structural-drift audit and the ledger + storage roundtrip suite
    (aeat-roundtrip-discipline: never removed without a replacement).
    """
    assert not (_WORKFLOWS_DIR / "durable-maintenance-gates.yml").exists()
    commands = "\n".join(
        str(step.get("run", "")) for step in _document(_FULL)["jobs"]["cadrumo-full-conformance"]["steps"]
    )
    assert "vaultspec-core vault check all" in commands
    assert "src/cadrumo/tests/test_roundtrip_coverage.py" in commands
    assert "src/cadrumo/application/ledger/tests" in commands
    assert "src/cadrumo/adapters/persistence/storage" in commands
    assert "src/cadrumo/adapters/persistence/profile" in commands
    assert "-k roundtrip" in commands


def test_drift_detector_targets_exist_on_disk() -> None:
    """Every drift-detector pytest target must exist on disk.

    The l1-anchor-drift failure class: a scheduled workflow whose pytest
    targets moved leaves a red cron nobody attributes.
    """
    repo_root = _WORKFLOWS_DIR.parents[1]
    document = _document(_WORKFLOWS_DIR / "aeat-drift-detector.yml")
    commands = "\n".join(str(step.get("run", "")) for job in document["jobs"].values() for step in job["steps"])
    targets = [token for token in commands.replace("\\", " ").split() if token.startswith("src/")]
    assert targets, "drift detector runs no src-tree pytest targets"
    for target in targets:
        assert (repo_root / target).exists(), f"drift-detector target moved or deleted: {target}"
