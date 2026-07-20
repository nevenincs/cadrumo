"""Cross-workflow structural gates for the release-asset evidence transport.

The release-asset-transport ADR moved every inter-workflow payload off Actions
artifact storage (quota-broken on the private Free plan) onto per-run draft
releases in the reserved ``evidence-*`` tag namespace. These gates pin the
transport invariants that span workflows: no packaging workflow may fall back
to artifact actions, every packaging-side release create is a draft in the
reserved namespace, publish-release derives evidence tags from its run-id
inputs, write permission stays job-scoped, checkouts never persist
credentials, and the GC workflow is dispatch-only with a dry-run default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import pytest
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = Path(__file__).resolve().parents[3] / ".github" / "workflows"
_PACKAGING_WORKFLOWS: Final = (
    "packaging-smoke.yml",
    "packaging-scoop.yml",
    "packaging-homebrew.yml",
    "packaging-claude.yml",
)
_TRANSPORT_WORKFLOWS: Final = (*_PACKAGING_WORKFLOWS, "publish-release.yml", "evidence-gc.yml")


def _document(name: str) -> dict[str, Any]:
    return yaml.safe_load((_WORKFLOWS_DIR / name).read_text(encoding="utf-8"))


def _steps(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for job in document["jobs"].values() for step in (job.get("steps") or []) if isinstance(step, dict)]


def _run_surface(document: dict[str, Any]) -> str:
    return "\n".join(str(step.get("run", "")) for step in _steps(document))


@pytest.mark.parametrize("workflow", _PACKAGING_WORKFLOWS)
def test_no_packaging_workflow_uses_actions_artifact_storage(workflow: str) -> None:
    """Cohort and evidence payloads never ride quota-capped artifact storage."""
    document = _document(workflow)
    offending = [
        str(step.get("uses"))
        for step in _steps(document)
        if "upload-artifact" in str(step.get("uses", "")) or "download-artifact" in str(step.get("uses", ""))
    ]
    assert offending == [], f"{workflow} still uses Actions artifact storage: {offending}"
    assert "gh run download" not in _run_surface(document), workflow


@pytest.mark.parametrize("workflow", _PACKAGING_WORKFLOWS)
def test_every_packaging_release_create_is_an_evidence_draft(workflow: str) -> None:
    """Packaging workflows only ever create DRAFT releases in the reserved namespace."""
    document = _document(workflow)
    creates = [line.strip() for line in _run_surface(document).splitlines() if "gh release create" in line]
    assert creates, f"{workflow} must create its evidence draft"
    for line in creates:
        assert "--draft" in line, line
        assert "EVIDENCE_TAG" in line, line
    # Every declared evidence tag lives in the reserved namespace, derived from
    # THIS run's id (a re-run of the same SHA mints a new, non-colliding draft).
    tags = {
        str(step["env"]["EVIDENCE_TAG"])
        for step in _steps(document)
        if isinstance(step.get("env"), dict) and "EVIDENCE_TAG" in step["env"]
    }
    assert tags, workflow
    lane = workflow.removeprefix("packaging-").removesuffix(".yml")
    assert tags == {f"evidence-{lane}-${{{{ github.run_id }}}}"}, tags


def test_only_publish_release_gate3_creates_a_non_draft_release() -> None:
    """The single published v* release comes from the environment-protected publish job."""
    document = _document("publish-release.yml")
    publish_surface = "\n".join(str(step.get("run", "")) for step in (document["jobs"]["publish"].get("steps") or []))
    assert 'gh release create "v$VERSION"' in publish_surface
    for job_name, job in document["jobs"].items():
        if job_name == "publish":
            continue
        job_surface = "\n".join(str(step.get("run", "")) for step in (job.get("steps") or []))
        # Invocation lines only: the operator-preflight instruction text
        # legitimately DESCRIBES the operator's draft-create command.
        invocations = [line for line in job_surface.splitlines() if line.strip().startswith("gh release create")]
        assert invocations == [], (job_name, invocations)


def test_publish_release_derives_evidence_tags_from_run_id_inputs() -> None:
    """The run id stays the operator's only handle; evidence tags are derived."""
    document = _document("publish-release.yml")
    inputs = set(document[True]["workflow_dispatch"]["inputs"])
    # No free-form evidence-tag input beyond the operator's claude release
    # (which has no backing run to derive from).
    assert not {name for name in inputs if "tag" in name or name.startswith("evidence")}
    surface = _run_surface(document)
    assert "evidence-smoke-$PACKAGING_RUN_ID" in surface
    assert "evidence-scoop-$SCOOP_RUN_ID" in surface
    assert "evidence-homebrew-$HOMEBREW_RUN_ID" in surface


@pytest.mark.parametrize("workflow", _TRANSPORT_WORKFLOWS)
def test_contents_write_is_job_scoped_and_checkouts_drop_credentials(workflow: str) -> None:
    """Least privilege: workflow-level read; write only on uploader jobs; no persisted token."""
    document = _document(workflow)
    top_level = document.get("permissions", {})
    assert top_level.get("contents") != "write", f"{workflow} grants contents:write workflow-wide"
    for job_name, job in document["jobs"].items():
        for step in job.get("steps") or []:
            if str(step.get("uses", "")).startswith("actions/checkout@"):
                with_block = step.get("with") or {}
                assert with_block.get("persist-credentials") is False, (workflow, job_name)


def test_uploader_jobs_hold_job_level_contents_write() -> None:
    """Every job that uploads to a draft carries its own contents:write grant."""
    for workflow in _PACKAGING_WORKFLOWS:
        document = _document(workflow)
        for job_name, job in document["jobs"].items():
            job_surface = "\n".join(str(step.get("run", "")) for step in (job.get("steps") or []))
            if "gh release upload" in job_surface or "gh release create" in job_surface:
                assert (job.get("permissions") or {}).get("contents") == "write", (workflow, job_name)


def test_acquisition_lanes_pin_the_linux_python_cohort_archive() -> None:
    """Decision pinned: every acquisition lane consumes the LINUX-built cohort.

    Wheels are py3-none-any, and the pre-transport lanes all downloaded the
    unsuffixed Linux artifact; the release-asset spelling keeps that parity.
    """
    for workflow in ("packaging-scoop.yml", "packaging-homebrew.yml", "packaging-claude.yml"):
        surface = _run_surface(_document(workflow))
        assert "cadrumo-python-cohort-linux.tar.gz" in surface, workflow
        assert "cadrumo-python-cohort-windows.tar.gz" not in surface, workflow
        assert "cadrumo-python-cohort-macos.tar.gz" not in surface, workflow


def test_oracle_emit_row_ids_stay_pairwise_disjoint() -> None:
    """The three oracle legs upload rows whose asset basenames cannot collide.

    Row files are ``{row_id}-{evidence_id}.json``; distinct row ids per leg
    keep the shared smoke draft collision-free.
    """
    document = _document("packaging-smoke.yml")
    row_ids = []
    for job_name in ("oracle-emit-linux", "oracle-emit-windows", "oracle-emit-macos"):
        surface = "\n".join(str(step.get("run", "")) for step in document["jobs"][job_name]["steps"])
        row_ids.extend(
            token.split()[1] for token in surface.replace("`", "").splitlines() if token.strip().startswith("--row-id ")
        )
    assert len(row_ids) == 3
    assert len(set(row_ids)) == 3, row_ids


def test_evidence_gc_workflow_is_dispatch_only_with_dry_run_default() -> None:
    """The GC is operator-armed: dispatch-only, dry-run default, helper-driven."""
    document = _document("evidence-gc.yml")
    triggers = document[True]
    assert set(triggers) == {"workflow_dispatch"}
    dry_run = triggers["workflow_dispatch"]["inputs"]["dry_run"]
    assert dry_run["type"] == "boolean"
    assert dry_run["default"] is True
    keep = triggers["workflow_dispatch"]["inputs"]["keep_per_workflow"]
    assert keep["default"] == "3"
    surface = _run_surface(document)
    # The retention decision lives in tested Python (namespace refusal, K per
    # lane, protected tags), never inline shell.
    assert "dev.packaging.evidence_release" in surface
    assert "--apply" in surface
    assert 'if [[ "$DRY_RUN" != "true" ]]' in surface
    gc_job = document["jobs"]["gc"]
    assert gc_job["runs-on"] == ["self-hosted", "Linux", "X64"]
    assert gc_job["permissions"] == {"contents": "write"}
