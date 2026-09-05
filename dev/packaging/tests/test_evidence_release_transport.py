"""Cross-workflow structural gates for the packaging evidence transport.

Inter-workflow payloads — the sealed release cohort, the per-OS smoke cohorts,
and the per-row ``DistributionEvidence`` records — ride Actions artifacts. They
briefly rode per-run draft releases instead, because artifact storage was
quota-capped while the repository was private on a Free plan; the repository is
public now, that storage is free, and the draft namespace only put machine
scaffolding on the owner's releases page.

These gates pin the invariants that span workflows. The load-bearing one is the
first: no packaging workflow may reach the releases API or hold the permission
that would let it. Exactly one job in the repository creates a release — the
human-armed publication gate — and it creates the one real ``v<version>``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_PACKAGING_WORKFLOWS: Final = (
    "packaging-smoke.yml",
    "packaging-scoop.yml",
    "packaging-homebrew.yml",
)
_TRANSPORT_WORKFLOWS: Final = _PACKAGING_WORKFLOWS


def _document(name: str) -> dict[str, Any]:
    return yaml.safe_load((_WORKFLOWS_DIR / name).read_text(encoding="utf-8"))


def _steps(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for job in document["jobs"].values() for step in (job.get("steps") or []) if isinstance(step, dict)]


def _run_surface(document: dict[str, Any]) -> str:
    return "\n".join(str(step.get("run", "")) for step in _steps(document))


def _invocations(surface: str, verb: str) -> list[str]:
    """Command lines only — workflow prose legitimately DESCRIBES a verb."""
    return [line.strip() for line in surface.splitlines() if line.strip().startswith(verb)]


@pytest.mark.parametrize("workflow", _PACKAGING_WORKFLOWS)
def test_no_packaging_workflow_touches_the_releases_api(workflow: str) -> None:
    """No packaging workflow creates, uploads to, or reads a GitHub release.

    This is the invariant the whole conversion exists to hold: CI must not put
    machine scaffolding on the repository's releases page. Asserted on
    invocation lines so a comment may still name the verb it warns against.
    """
    surface = _run_surface(_document(workflow))
    for verb in ("gh release create", "gh release upload", "gh release view", "gh release download"):
        assert _invocations(surface, verb) == [], f"{workflow} still calls {verb!r}"


@pytest.mark.parametrize("workflow", _PACKAGING_WORKFLOWS)
def test_no_packaging_job_can_write_repository_contents(workflow: str) -> None:
    """Least privilege carries the invariant above even if a verb slips back.

    ``contents: write`` is the permission that makes the releases API reachable
    at all, so no packaging job may hold it — at workflow or job level.
    """
    document = _document(workflow)
    assert (document.get("permissions") or {}).get("contents") != "write", workflow
    for job_name, job in document["jobs"].items():
        granted = (job.get("permissions") or {}).get("contents")
        assert granted != "write", f"{workflow}:{job_name} still grants contents:write"


@pytest.mark.parametrize("workflow", _PACKAGING_WORKFLOWS)
def test_packaging_payloads_ride_artifacts(workflow: str) -> None:
    """Every packaging workflow moves its payloads through Actions artifacts."""
    document = _document(workflow)
    uses = [str(step.get("uses", "")) for step in _steps(document)]
    artifact_steps = [entry for entry in uses if "upload-artifact" in entry or "download-artifact" in entry]
    cross_workflow = "gh run download" in _run_surface(document)
    assert artifact_steps or cross_workflow, f"{workflow} moves no payload through artifacts"
    for entry in artifact_steps:
        assert "@" in entry and len(entry.split("@")[1]) == 40, f"{workflow} pins {entry} to a tag, not a SHA"


#: Below this the workflow walk has stopped covering the directory. A floor,
#: not a pinned count: sixteen workflows ship today.
_MINIMUM_WORKFLOWS = 8


def _workflow_files() -> tuple[Path, ...]:
    """Every committed workflow, with the walk itself asserted.

    Both suffixes, because GitHub honours each and a workflow added as
    ``.yaml`` would otherwise sit outside every gate in this module without
    changing a single result. Sixteen ship today and none uses ``.yaml``, so
    this is closing the door rather than reporting a breach.

    The guards matter more than the widening: these gates assert that no
    workflow does a forbidden thing, and an empty walk satisfies that
    perfectly while proving nothing at all.
    """
    assert _WORKFLOWS_DIR.is_dir(), (
        f"no workflow directory at {_WORKFLOWS_DIR}; a relocated root walks nothing and "
        "every gate in this module would report the workflows clean"
    )

    found = tuple(
        sorted(path for pattern in ("*.yml", "*.yaml") for path in scan_directory(_WORKFLOWS_DIR, pattern=pattern))
    )

    assert len(found) >= _MINIMUM_WORKFLOWS, (
        f"only {len(found)} workflow(s) were walked; below this an empty finding list says "
        "nothing about what the workflows actually do"
    )
    return found


def test_no_workflow_creates_a_release_by_hand() -> None:
    """The release is cut by the versioning action, never by a shell step.

    A hand-rolled ``gh release create`` beside the action would produce either a
    second release for the same version or one the publish path never proved.
    """
    creators: list[tuple[str, str]] = []
    for path in _workflow_files():
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in (document.get("jobs") or {}).items():
            surface = "\n".join(str(step.get("run", "")) for step in (job.get("steps") or []))
            if _invocations(surface, "gh release create"):
                creators.append((path.name, job_name))
    assert creators == [], creators


def test_no_workflow_creates_a_draft_release() -> None:
    """The reserved evidence-* draft namespace is retired, not merely emptied."""
    for path in _workflow_files():
        surface = path.read_text(encoding="utf-8")
        assert "--draft" not in surface, f"{path.name} still creates a draft release"
        assert "evidence-smoke-" not in surface, f"{path.name} still names an evidence draft tag"
