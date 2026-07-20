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


_EXPECTED_CREATOR_JOB: Final = {
    "packaging-smoke.yml": "build-release-cohort",
    "packaging-scoop.yml": "cadrumo-scoop-acquisition",
    "packaging-homebrew.yml": "create-evidence-draft",
    "packaging-claude.yml": "cadrumo-claude-acquisition",
}


@pytest.mark.parametrize("workflow", _PACKAGING_WORKFLOWS)
def test_every_packaging_release_create_is_an_evidence_draft(workflow: str) -> None:
    """Packaging workflows only ever create DRAFT releases in the reserved namespace."""
    document = _document(workflow)
    creates = [line.strip() for line in _run_surface(document).splitlines() if "gh release create" in line]
    assert creates, f"{workflow} must create its evidence draft"
    for line in creates:
        assert "--draft" in line, line
        assert "EVIDENCE_TAG" in line, line
        # A draft reserves no tag ref, so a suppressed create can still mint a
        # duplicate — creators must probe-then-create, never create-or-ignore.
        assert "|| true" not in line, line
    # Tags for the SMOKE draft (consumed by acquisition lanes) may coexist with
    # the workflow's own lane tag; the workflow's own creates all target its
    # own lane tag derived from THIS run's id.
    lane = workflow.removeprefix("packaging-").removesuffix(".yml")
    own_tag = f"evidence-{lane}-${{{{ github.run_id }}}}"
    create_step_tags = {
        str(step["env"]["EVIDENCE_TAG"])
        for step in _steps(document)
        if isinstance(step.get("env"), dict)
        and "EVIDENCE_TAG" in step["env"]
        and "gh release create" in str(step.get("run", ""))
    }
    assert create_step_tags == {own_tag}, create_step_tags


@pytest.mark.parametrize("workflow", _PACKAGING_WORKFLOWS)
def test_exactly_one_creator_job_per_workflow(workflow: str) -> None:
    """Single-creator topology: concurrent creates would mint duplicate drafts.

    Drafts reserve no tag ref (cli/cli#4270 and siblings), so exactly one job
    per workflow creates the run's draft; every other uploader is upload-only
    and waits on the creator through the ``needs:`` graph.
    """
    document = _document(workflow)
    creator_jobs = [
        job_name
        for job_name, job in document["jobs"].items()
        if "gh release create" in "\n".join(str(step.get("run", "")) for step in (job.get("steps") or []))
    ]
    assert creator_jobs == [_EXPECTED_CREATOR_JOB[workflow]], (workflow, creator_jobs)


def test_smoke_uploaders_wait_on_the_sole_creator() -> None:
    """Every smoke uploader job needs: build-release-cohort before it uploads."""
    document = _document("packaging-smoke.yml")
    for job_name, job in document["jobs"].items():
        if job_name in {"build-release-cohort", "seal-evidence-manifest"}:
            continue
        needs = job.get("needs")
        needs_list = [needs] if isinstance(needs, str) else list(needs or [])
        assert "build-release-cohort" in needs_list, job_name
    homebrew = _document("packaging-homebrew.yml")
    matrix_needs = homebrew["jobs"]["cadrumo-homebrew-acquisition"]["needs"]
    assert matrix_needs == "create-evidence-draft"


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


def test_gate3_attaches_only_sweep_passed_evidence() -> None:
    """Gate 3 leak-sweeps every evidence asset BEFORE anything can be attached.

    Reconciled D9: rows are scrubbed at mint time; the sweep is the fail-closed
    publication tripwire (verify-then-refuse, no rewriting) over the attach
    directory, and the v-release create comes only after it.
    """
    document = _document("publish-release.yml")
    surface = "\n".join(str(step.get("run", "")) for step in (document["jobs"]["publish"].get("steps") or []))
    assert "dev.packaging.evidence_release leak-sweep" in surface
    # The sweep covers the UNION of everything Gate 3 attaches: the evidence
    # attach dir AND the cohort files themselves.
    assert '--directory "$EVIDENCE_FINAL_DIR/attach"' in surface
    assert '--directory "$RELEASE_COHORT_DIR"' in surface
    assert surface.index("leak-sweep") < surface.index('gh release create "v$VERSION"')
    # The final release's assets come exclusively from the two swept roots.
    assert '"$RELEASE_COHORT_DIR" "$EVIDENCE_FINAL_DIR/attach" -type f' in surface


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


def test_windows_transport_steps_pin_shell_pwsh() -> None:
    """Every Windows transport step declares ``shell: pwsh``, never 5.1.

    The setup actions rewrite PSModulePath for pwsh, which breaks Windows
    PowerShell 5.1 module auto-loading on the self-hosted runner (observed
    live: ``Get-FileHash is not recognized``). Transport steps (anything
    touching ``gh release`` or the evidence_release helper) must therefore
    pin pwsh explicitly rather than rely on default shell resolution.
    """
    for workflow in _PACKAGING_WORKFLOWS:
        for step in _steps(_document(workflow)):
            run = str(step.get("run", ""))
            if "gh release" not in run and "evidence_release" not in run:
                continue
            shell = step.get("shell")
            assert shell in (None, "pwsh"), (workflow, step.get("name"), shell)
    # The claude lane runs on the SAME broken-5.1 self-hosted runner; its
    # module-cmdlet steps (ConvertTo-Json, Invoke-RestMethod, Get-ChildItem/
    # Copy-Item) are pinned too, even though they predate the transport.
    claude_steps = {str(step.get("name")): step.get("shell") for step in _steps(_document("packaging-claude.yml"))}
    for step_name in (
        "Initialize current-run evidence root",
        "Verify source workflow identity",
        "Curate non-sensitive acquisition evidence",
    ):
        assert claude_steps[step_name] == "pwsh", (step_name, claude_steps[step_name])


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
