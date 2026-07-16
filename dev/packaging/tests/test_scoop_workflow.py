"""Structural gate for the clean Cadrumo Scoop acquisition workflow."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "packaging-scoop.yml"


def _workflow() -> dict[str, object]:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def test_scoop_workflow_declares_the_sandbox_release_row() -> None:
    """The acquisition job can run only on the labelled Windows Sandbox host."""
    document = _workflow()
    assert document["name"] == "Cadrumo Scoop Acquisition"
    assert set(document["jobs"]) == {"cadrumo-scoop-acquisition"}

    job = document["jobs"]["cadrumo-scoop-acquisition"]
    assert job["name"] == "Cadrumo / Windows / x64 / Scoop Sandbox"
    assert job["runs-on"] == [
        "self-hosted",
        "Windows",
        "X64",
        "cadrumo-windows-sandbox",
    ]
    preflight = next(
        step for step in job["steps"] if step["name"] == "Verify declared Windows Sandbox release row"
    )
    assert "Containers-DisposableClientVM" in preflight["run"]
    assert "WindowsSandbox.exe" in preflight["run"]
    assert 'PROCESSOR_ARCHITECTURE -ne "AMD64"' in preflight["run"]


def test_scoop_workflow_consumes_one_successful_commit_bound_cohort() -> None:
    """The row downloads stored tested bytes from the named successful source run."""
    document = _workflow()
    job = document["jobs"]["cadrumo-scoop-acquisition"]
    steps = job["steps"]
    source_gate = next(step for step in steps if step["name"] == "Verify source workflow identity")
    checkout = next(step for step in steps if step["name"] == "Checkout tested source commit")
    download = next(step for step in steps if step["name"] == "Download tested Cadrumo Python cohort")

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
    assert download["with"] == {
        "name": "cadrumo-python-cohort",
        "path": "${{ env.CADRUMO_S20_ROOT }}/cohort",
        "github-token": "${{ github.token }}",
        "repository": "${{ github.repository }}",
        "run-id": "${{ inputs.source_run_id }}",
    }
    assert document["permissions"] == {"actions": "read", "contents": "read"}


def test_scoop_workflow_runs_the_real_sandbox_lifecycle_without_rebuilding() -> None:
    """The row generates only channel metadata and executes the real Sandbox harness."""
    document = _workflow()
    steps = document["jobs"]["cadrumo-scoop-acquisition"]["steps"]
    generate = next(step for step in steps if step["name"] == "Generate cohort-bound Scoop source manifest")
    initialize = next(step for step in steps if step["name"] == "Initialize current-run evidence root")
    stage = next(step for step in steps if step["name"] == "Stage token-free Sandbox harness")
    smoke = next(step for step in steps if step["name"] == "Install and exercise Cadrumo inside Windows Sandbox")
    upload = next(step for step in steps if step["name"] == "Upload Cadrumo Scoop acquisition evidence")
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
    assert '$env:CADRUMO_S20_ROOT/harness/dev/packaging/smoke_scoop.ps1' in smoke["run"]
    assert "-Mode Sandbox" in smoke["run"]
    assert "-TimeoutMinutes 60" in smoke["run"]
    assert upload["if"] == "always() && steps.initialize.outputs.ready == 'true'"
    assert upload["with"]["if-no-files-found"] == "error"
    assert upload["with"]["name"] == "cadrumo-scoop-acquisition-evidence-${{ github.run_attempt }}"
    assert upload["with"]["path"] == (
        "${{ runner.temp }}/cadrumo-s20-${{ github.run_id }}-${{ github.run_attempt }}/"
    )
    assert "uv build" not in commands
    assert "python -m build" not in commands
    assert "hatch build" not in commands
