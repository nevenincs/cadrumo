"""Structural gate for the clean Cadrumo Scoop acquisition workflow."""

from __future__ import annotations

import pytest
import yaml

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "packaging-scoop.yml"


def _workflow() -> dict[str, object]:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def test_scoop_workflow_declares_the_native_release_row() -> None:
    """The acquisition job runs natively on the labelled self-hosted Windows runner.

    Operator mandate 2026-07-21: no hosted/cloud runners. The lane is pinned to
    the ``windows-scoop`` label so it schedules only onto the dedicated
    non-admin runner user, leaving the fleet's one Docker daemon permanently in
    Linux-container mode.

    The preflight is retargeted rather than dropped: it fails fast and free on
    anything but AMD64 with a resolvable Scoop profile, and refuses an elevated
    identity, which is the privilege boundary the container used to supply.
    """
    document = _workflow()
    assert document["name"] == "Cadrumo Scoop Acquisition"
    assert set(document["jobs"]) == {"cadrumo-scoop-acquisition", "runner-queue-watchdog"}

    job = document["jobs"]["cadrumo-scoop-acquisition"]
    assert job["name"] == "Cadrumo / Windows / x64 / Scoop Native"
    assert job["runs-on"] == ["self-hosted", "Windows", "X64", "windows-scoop"]
    preflight = next(step for step in job["steps"] if step["name"] == "Verify declared Windows native release row")
    assert 'PROCESSOR_ARCHITECTURE -ne "AMD64"' in preflight["run"]
    assert "Get-Command scoop" in preflight["run"]
    assert 'foreach ($required in @("apps", "buckets", "shims"))' in preflight["run"]
    assert "WindowsBuiltInRole]::Administrator" in preflight["run"]
    # An elevation check alone is not the privilege gate this topology needs:
    # under UAC an administrator account runs with a filtered token that reports
    # IsInRole false, so membership must be read from the group itself. The
    # well-known SID keeps that read locale-independent, and a failure to
    # determine membership must refuse rather than assume the safe answer.
    assert 'Get-LocalGroupMember -SID "S-1-5-32-544"' in preflight["run"]
    assert "refusing rather than assuming it is not" in preflight["run"]
    # Pin the whole guard, not the expressions it is built from. Both arms also
    # appear in the refusal message that explains which one fired, so pinning
    # them individually is satisfied by that message alone and leaves the guard
    # itself defeatable in silence.
    assert "if ($memberSid -eq $identity.User.Value -or $tokenGroups -contains $memberSid) {" in preflight["run"]
    # The daemon stays in Linux-container mode for the standing Linux runners,
    # so a reintroduced docker-mode gate would refuse this lane forever.
    assert "docker" not in preflight["run"]


def test_scoop_workflow_consumes_one_successful_commit_bound_cohort() -> None:
    """The row downloads stored tested bytes from the named successful source run."""
    document = _workflow()
    job = document["jobs"]["cadrumo-scoop-acquisition"]
    steps = job["steps"]
    source_gate = next(step for step in steps if step["name"] == "Verify source workflow identity")
    checkout = next(step for step in steps if step["name"] == "Checkout tested source commit")
    download = next(
        step for step in steps if step["name"] == "Download the tested cohorts from the verified source run"
    )

    assert source_gate["env"]["SOURCE_COMMIT"] == "${{ inputs.source_commit }}"
    assert source_gate["env"]["SOURCE_RUN_ID"] == "${{ inputs.source_run_id }}"
    assert '$run.name -ne "Cadrumo Packaging Smoke"' in source_gate["run"]
    assert '$run.path -ne ".github/workflows/packaging-smoke.yml"' in source_gate["run"]
    assert '$run.conclusion -ne "success"' in source_gate["run"]
    # Trusted-source predicate (ci-speed redesign): main-branch runs, either
    # push (historical) or dispatch verified on main history via compare API.
    assert '$run.head_branch -ne "main"' in source_gate["run"]
    assert '$run.event -eq "workflow_dispatch"' in source_gate["run"]
    assert "/compare/main..." in source_gate["run"]
    assert '$ancestry.status -ne "identical" -and $ancestry.status -ne "behind"' in source_gate["run"]
    assert '$run.event -ne "push"' in source_gate["run"]
    assert "$run.head_repository.full_name -ne $env:GITHUB_REPOSITORY" in source_gate["run"]
    assert "$run.head_sha -ne $env:SOURCE_COMMIT.ToLowerInvariant()" in source_gate["run"]
    assert checkout["with"]["ref"] == "${{ inputs.source_commit }}"
    assert checkout["with"]["persist-credentials"] is False
    # The cohorts come from the source run's own artifacts, which bind them to
    # that run by construction; the source-identity gate above is the whole
    # provenance check. The lane consumes the LINUX-built python cohort
    # (wheels are py3-none-any) plus the sealed full release cohort.
    assert "gh run download" in download["run"]
    assert "--name cadrumo-python-cohort-linux" in download["run"]
    assert "--name cadrumo-release-cohort" in download["run"]
    # Least privilege: workflow-level stays read; only the uploader job holds
    # contents:write for the draft-release transport.
    assert document["permissions"] == {"actions": "read", "contents": "read"}
    assert job["permissions"] == {"actions": "read", "contents": "read"}


def test_scoop_workflow_runs_the_real_native_lifecycle_without_rebuilding() -> None:
    """The row generates only channel metadata and executes the real native harness."""
    document = _workflow()
    steps = document["jobs"]["cadrumo-scoop-acquisition"]["steps"]
    generate = next(step for step in steps if step["name"] == "Generate cohort-bound Scoop source manifest")
    initialize = next(step for step in steps if step["name"] == "Initialize current-run evidence root")
    stage = next(step for step in steps if step["name"] == "Stage token-free smoke harness")
    smoke = next(
        step for step in steps if step["name"] == "Install and exercise Cadrumo in the lane user's Scoop profile"
    )
    publish = next(step for step in steps if step["name"] == "Stage the Scoop acquisition bundle")
    commands = "\n".join(str(step.get("run", "")) for step in steps)

    assert "packaging/scoop/generate.py" in generate["run"]
    assert '--cohort-dir "$env:CADRUMO_SCOOP_ROOT/cohort"' in generate["run"]
    assert "$env:RUNNER_TEMP" in initialize["run"]
    assert "$env:GITHUB_RUN_ATTEMPT" in initialize["run"]
    assert "run-context.json" in initialize["run"]
    assert initialize["id"] == "initialize"
    assert '"ready=true"' in initialize["run"]
    # Every first-party module the harness executes must be staged: the smoke
    # asserts the installed venv landed on the manifest's pinned closure before
    # the tax oracle runs, so a missing constraint_effect fails the lane there.
    assert "_command.py" in stage["run"]
    assert "constraint_effect.py" in stage["run"]
    assert "installed_tax_oracle.py" in stage["run"]
    assert "$env:CADRUMO_SCOOP_ROOT/harness/dev/packaging/smoke_scoop.ps1" in smoke["run"]
    assert "-Mode Host" in smoke["run"]
    # Negative pins: a silent revert to the container lane would strand the row
    # behind a docker-mode gate the fleet's daemon can never satisfy.
    assert "-Mode Container" not in commands
    assert "mcr.microsoft.com/windows/servercore" not in commands
    assert publish["if"] == "always() && steps.initialize.outputs.ready == 'true'"
    # Evidence rides this run's OWN artifacts; nothing reaches the releases API.
    assert "gh release" not in publish["run"]
    assert "cadrumo-scoop-acquisition-evidence.tar.gz" in publish["run"]
    assert "uv build" not in commands
    assert "python -m build" not in commands
    assert "hatch build" not in commands


def test_scoop_workflow_binds_the_smoke_evidence_before_minting_the_row() -> None:
    """Nothing may reach the emitter that is not a clean native run of this manifest.

    Container mode had an orchestrator that verified the child's identity and
    source binding before returning. Invoking the smoke directly removes that
    orchestrator, so the lane re-asserts the same bindings itself, ahead of the
    step that mints the distribution-evidence row.
    """
    steps = _workflow()["jobs"]["cadrumo-scoop-acquisition"]["steps"]
    names = [step["name"] for step in steps]
    verify = next(step for step in steps if step["name"] == "Verify the smoke evidence binds to this run")
    emit = next(step for step in steps if step["name"] == "Emit the sanctioned Scoop distribution-evidence record")

    assert names.index("Verify the smoke evidence binds to this run") < names.index(
        "Emit the sanctioned Scoop distribution-evidence record"
    )
    # The CLI-only lane emits from the tax oracle JSON alone: the emitter runs
    # without the mcp dependency and the record marks the MCP leg absent.
    assert "--tax-evidence $tax" in emit["run"]
    assert "mcp-evidence.json" not in emit["run"]
    assert "--mcp-evidence" not in emit["run"]
    assert "--with mcp" not in emit["run"]
    assert '$evidence.status -ne "passed"' in verify["run"]
    assert '$evidence.mode -ne "Host"' in verify["run"]
    assert "$evidence.container_identity_verified -ne $false" in verify["run"]
    assert "$evidence.orchestration_nonce" in verify["run"]
    assert "$evidence.source_manifest_sha256 -ne $expectedManifestHash" in verify["run"]
    assert '$evidence.cleanup_status -ne "passed"' in verify["run"]
    assert "$evidence.runtime_identity" in verify["run"]
    # A failed smoke writes scoop-failure.json instead; surface its reason
    # rather than a bare missing-file error.
    assert "scoop-failure.json" in verify["run"]
