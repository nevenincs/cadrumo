"""Structural gate for the clean Cadrumo Scoop acquisition workflow."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "packaging-scoop.yml"


def _workflow() -> dict[str, object]:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def test_scoop_workflow_declares_the_container_release_row() -> None:
    """The acquisition job runs on a GitHub-hosted Windows-container host."""
    document = _workflow()
    assert document["name"] == "Cadrumo Scoop Acquisition"
    assert set(document["jobs"]) == {"cadrumo-scoop-acquisition"}

    job = document["jobs"]["cadrumo-scoop-acquisition"]
    assert job["name"] == "Cadrumo / Windows / x64 / Scoop Container"
    assert job["runs-on"] == "windows-2022"
    preflight = next(step for step in job["steps"] if step["name"] == "Verify declared Windows container release row")
    assert 'PROCESSOR_ARCHITECTURE -ne "AMD64"' in preflight["run"]
    assert "docker version --format" in preflight["run"]
    assert '$serverOs -ne "windows"' in preflight["run"]


def test_scoop_workflow_consumes_one_successful_commit_bound_cohort() -> None:
    """The row downloads stored tested bytes from the named successful source run."""
    document = _workflow()
    job = document["jobs"]["cadrumo-scoop-acquisition"]
    steps = job["steps"]
    source_gate = next(step for step in steps if step["name"] == "Verify source workflow identity")
    checkout = next(step for step in steps if step["name"] == "Checkout tested source commit")
    download = next(
        step for step in steps if step["name"] == "Download and verify the tested cohorts from the smoke evidence draft"
    )

    assert source_gate["env"]["SOURCE_COMMIT"] == "${{ inputs.source_commit }}"
    assert source_gate["env"]["SOURCE_RUN_ID"] == "${{ inputs.source_run_id }}"
    assert '$run.name -ne "Cadrumo Packaging Smoke"' in source_gate["run"]
    assert '$run.path -ne ".github/workflows/packaging-smoke.yml"' in source_gate["run"]
    assert '$run.conclusion -ne "success"' in source_gate["run"]
    assert '$run.event -ne "push" -or $run.head_branch -ne "main"' in source_gate["run"]
    assert "$run.head_repository.full_name -ne $env:GITHUB_REPOSITORY" in source_gate["run"]
    assert "$run.head_sha -ne $env:SOURCE_COMMIT.ToLowerInvariant()" in source_gate["run"]
    assert checkout["with"]["ref"] == "${{ inputs.source_commit }}"
    assert checkout["with"]["persist-credentials"] is False
    # The cohorts come hash-verified from the smoke run's evidence draft, with
    # the tag DERIVED from the run-id input; the lane consumes the LINUX-built
    # python cohort (wheels are py3-none-any; parity with the pre-transport
    # unsuffixed artifact) plus the sealed full release cohort.
    assert "dev.packaging.evidence_release verify" in download["run"]
    assert '--tag "evidence-smoke-$env:SOURCE_RUN_ID"' in download["run"]
    assert '--expect-workflow ".github/workflows/packaging-smoke.yml"' in download["run"]
    assert '--pattern "cadrumo-python-cohort-linux.tar.gz"' in download["run"]
    assert '--pattern "cadrumo-release-cohort.tar.gz"' in download["run"]
    # Least privilege: workflow-level stays read; only the uploader job holds
    # contents:write for the draft-release transport.
    assert document["permissions"] == {"actions": "read", "contents": "read"}
    assert job["permissions"] == {"actions": "read", "contents": "write"}


def test_scoop_workflow_runs_the_real_container_lifecycle_without_rebuilding() -> None:
    """The row generates only channel metadata and executes the real container harness."""
    document = _workflow()
    steps = document["jobs"]["cadrumo-scoop-acquisition"]["steps"]
    generate = next(step for step in steps if step["name"] == "Generate cohort-bound Scoop source manifest")
    initialize = next(step for step in steps if step["name"] == "Initialize current-run evidence root")
    stage = next(step for step in steps if step["name"] == "Stage token-free container harness")
    smoke = next(step for step in steps if step["name"] == "Install and exercise Cadrumo inside a Windows container")
    publish = next(
        step for step in steps if step["name"] == "Publish Scoop evidence to the run's evidence draft and seal it"
    )
    commands = "\n".join(str(step.get("run", "")) for step in steps)

    assert "packaging/scoop/generate.py" in generate["run"]
    assert '--cohort-dir "$env:CADRUMO_S20_ROOT/cohort"' in generate["run"]
    assert "$env:RUNNER_TEMP" in initialize["run"]
    assert "$env:GITHUB_RUN_ATTEMPT" in initialize["run"]
    assert "run-context.json" in initialize["run"]
    assert initialize["id"] == "initialize"
    assert '"ready=true"' in initialize["run"]
    assert "installed_tax_oracle.py" in stage["run"]
    assert "installed_mcp_oracle.py" in stage["run"]
    assert "$env:CADRUMO_S20_ROOT/harness/dev/packaging/smoke_scoop.ps1" in smoke["run"]
    assert "-Mode Container" in smoke["run"]
    assert "mcr.microsoft.com/windows/servercore:ltsc2022" in smoke["run"]
    assert "-TimeoutMinutes 60" in smoke["run"]
    assert publish["if"] == "always() && steps.initialize.outputs.ready == 'true'"
    # Evidence rides this run's OWN draft (rows + bundle + sealed manifest).
    assert publish["env"]["EVIDENCE_TAG"] == "evidence-scoop-${{ github.run_id }}"
    assert "gh release create $env:EVIDENCE_TAG --draft" in publish["run"]
    assert "distribution-install-readiness" in publish["run"]
    assert "cadrumo-scoop-acquisition-evidence.tar.gz" in publish["run"]
    assert "dev.packaging.evidence_release emit-manifest" in publish["run"]
    assert "gh release upload $env:EVIDENCE_TAG evidence-manifest.json --clobber" in publish["run"]
    assert "uv build" not in commands
    assert "python -m build" not in commands
    assert "hatch build" not in commands
