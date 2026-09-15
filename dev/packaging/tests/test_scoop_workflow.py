"""Structural gate for the clean Cadrumo Scoop acquisition workflow."""

from __future__ import annotations

from typing import TypedDict

import pytest
import yaml

from dev._paths import REPO_ROOT
from dev.ci.workflow_permissions import jobs_granting
from dev.ci.workflow_run_text import executed_text

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "packaging-scoop.yml"


_Step = TypedDict(
    "_Step",
    {
        "name": str,
        "id": str,
        "shell": str,
        "uses": str,
        "run": str,
        "if": str,
        "env": dict[str, str],
        "with": dict[str, str | bool],
    },
    total=False,
)
_Job = TypedDict(
    "_Job",
    {
        "name": str,
        "runs-on": list[str],
        "timeout-minutes": int,
        "permissions": dict[str, str],
        "steps": list[_Step],
    },
    total=False,
)


class _Workflow(TypedDict, total=False):
    name: str
    jobs: dict[str, _Job]
    permissions: dict[str, str]


def _required_string(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise AssertionError(f"workflow field {field!r} is not a string")
    return value


def _string_list(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list):
        raise AssertionError(f"workflow field {field!r} is not a list")
    result: list[str] = []
    for item in value:
        result.append(_required_string(item, field=field))
    return result


def _string_mapping(value: object, *, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise AssertionError(f"workflow field {field!r} is not a mapping")
    result: dict[str, str] = {}
    for key, item in value.items():
        result[_required_string(key, field=field)] = _required_string(item, field=field)
    return result


def _string_bool_mapping(value: object, *, field: str) -> dict[str, str | bool]:
    if not isinstance(value, dict):
        raise AssertionError(f"workflow field {field!r} is not a mapping")
    result: dict[str, str | bool] = {}
    for key, item in value.items():
        if not isinstance(item, (str, bool)):
            raise AssertionError(f"workflow field {field!r} contains a non-string/bool value")
        result[_required_string(key, field=field)] = item
    return result


def _step(value: object) -> _Step:
    if not isinstance(value, dict):
        raise AssertionError("workflow step is not a mapping")
    step: _Step = {}
    for field in ("name", "id", "shell", "uses", "run", "if"):
        if field in value:
            step[field] = _required_string(value[field], field=field)
    if "env" in value:
        step["env"] = _string_mapping(value["env"], field="env")
    if "with" in value:
        step["with"] = _string_bool_mapping(value["with"], field="with")
    return step


def _job(value: object) -> _Job:
    if not isinstance(value, dict):
        raise AssertionError("workflow job is not a mapping")
    job: _Job = {}
    if "name" in value:
        job["name"] = _required_string(value["name"], field="name")
    if "runs-on" in value:
        job["runs-on"] = _string_list(value["runs-on"], field="runs-on")
    if "timeout-minutes" in value:
        timeout = value["timeout-minutes"]
        if not isinstance(timeout, int):
            raise AssertionError("workflow field 'timeout-minutes' is not an integer")
        job["timeout-minutes"] = timeout
    if "permissions" in value:
        job["permissions"] = _string_mapping(value["permissions"], field="permissions")
    raw_steps = value.get("steps")
    if not isinstance(raw_steps, list):
        raise AssertionError("workflow field 'steps' is not a list")
    job["steps"] = [_step(step) for step in raw_steps]
    return job


def _workflow() -> _Workflow:
    raw = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise AssertionError("workflow document is not a mapping")
    raw_jobs = raw.get("jobs")
    if not isinstance(raw_jobs, dict):
        raise AssertionError("workflow field 'jobs' is not a mapping")
    jobs: dict[str, _Job] = {}
    for name, job in raw_jobs.items():
        jobs[_required_string(name, field="jobs")] = _job(job)
    workflow: _Workflow = {
        "name": _required_string(raw.get("name"), field="name"),
        "jobs": jobs,
    }
    if "permissions" in raw:
        workflow["permissions"] = _string_mapping(raw["permissions"], field="permissions")
    return workflow


def test_scoop_workflow_declares_the_native_release_row() -> None:
    """The acquisition job runs natively on the labelled self-hosted Windows runner.

    Operator mandate 2026-07-21: no hosted/cloud runners. The lane selects the
    fleet's one self-hosted Windows runner by platform labels only (the fleet
    standard forbids repo/tool labels such as the former ``windows-scoop``),
    leaving the fleet's one Docker daemon permanently in Linux-container mode.

    The preflight is retargeted rather than dropped: it fails fast and free on
    anything but AMD64 with a resolvable Scoop profile, and refuses an elevated
    identity, which is the privilege boundary the container used to supply.
    """
    document = _workflow()
    assert document["name"] == "Cadrumo Scoop Acquisition"
    assert set(document["jobs"]) == {"cadrumo-scoop-acquisition", "runner-queue-watchdog"}

    job = document["jobs"]["cadrumo-scoop-acquisition"]
    assert job["name"] == "Test: Channel acquisition (Windows)"
    assert job["runs-on"] == ["self-hosted", "Windows", "X64"]
    preflight = next(step for step in job["steps"] if step["name"] == "Verify declared Windows native release row")
    assert 'PROCESSOR_ARCHITECTURE -ne "AMD64"' in _executable_lines(preflight["run"])
    assert "Get-Command scoop" in _executable_lines(preflight["run"])
    assert 'foreach ($required in @("apps", "buckets", "shims"))' in _executable_lines(preflight["run"])
    assert "WindowsBuiltInRole]::Administrator" in _executable_lines(preflight["run"])
    # An elevation check alone is not the privilege gate this topology needs:
    # under UAC an administrator account runs with a filtered token that reports
    # IsInRole false, so membership must be read from the group itself. The
    # well-known SID keeps that read locale-independent, and a failure to
    # determine membership must refuse rather than assume the safe answer.
    assert 'Get-LocalGroupMember -SID "S-1-5-32-544"' in _executable_lines(preflight["run"])
    assert "refusing rather than assuming it is not" in _executable_lines(preflight["run"])
    # Pin the whole guard, not the expressions it is built from. Both arms also
    # appear in the refusal message that explains which one fired, so pinning
    # them individually is satisfied by that message alone and leaves the guard
    # itself defeatable in silence.
    assert "if ($memberSid -eq $identity.User.Value -or $tokenGroups -contains $memberSid) {" in _executable_lines(
        preflight["run"]
    )
    # The daemon stays in Linux-container mode for the standing Linux runners,
    # so a reintroduced docker-mode gate would refuse this lane forever.
    assert "docker" not in preflight["run"]


def _executable_lines(script: str) -> str:
    """The script with comment-only lines removed.

    A structural assertion must read what the shell RUNS. Prose explaining why
    a token is absent from a branch contains that token, so a naive membership
    test matches the comment and reports the opposite of the truth. The rule
    that decides this is :mod:`dev.ci.workflow_run_text`'s, not a copy of it.
    """
    return executed_text(script)


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
    assert '$run.name -ne "Cadrumo Packaging Smoke"' in _executable_lines(source_gate["run"])
    assert '$run.path -ne ".github/workflows/packaging-smoke.yml"' in _executable_lines(source_gate["run"])
    assert '$run.conclusion -ne "success"' in _executable_lines(source_gate["run"])
    # Trusted-source predicate: a run is on main by HISTORY for a dispatch, and
    # by branch name for a push. See the sibling homebrew gate for why the two
    # arms must stay separate; in short, the unconditional name test made every
    # evidence row unobtainable, because the tagged commit `readiness.py`
    # demands is reachable only as `--ref v{version}`.
    assert '$run.event -eq "workflow_dispatch"' in _executable_lines(source_gate["run"])
    assert "/compare/main..." in _executable_lines(source_gate["run"])
    assert '$ancestry.status -ne "identical" -and $ancestry.status -ne "behind"' in _executable_lines(
        source_gate["run"]
    )
    assert '$run.event -eq "push"' in _executable_lines(source_gate["run"])
    assert '$run.head_branch -ne "main"' in _executable_lines(source_gate["run"])
    dispatch_arm, _, push_arm = _executable_lines(source_gate["run"]).partition("elseif")
    assert "head_branch" not in dispatch_arm, "the branch-name test must not gate a dispatch run"
    assert "head_branch" in push_arm, "a push run has no ancestry proof and must be pinned by branch name"
    assert "$run.head_repository.full_name -ne $env:GITHUB_REPOSITORY" in _executable_lines(source_gate["run"])
    assert "$run.head_sha -ne $env:SOURCE_COMMIT.ToLowerInvariant()" in _executable_lines(source_gate["run"])
    assert checkout["with"]["ref"] == "${{ inputs.source_commit }}"
    assert checkout["with"]["persist-credentials"] is False
    # The cohorts come from the source run's own artifacts, which bind them to
    # that run by construction; the source-identity gate above is the whole
    # provenance check. The lane consumes the LINUX-built python cohort
    # (wheels are py3-none-any) plus the sealed full release cohort.
    assert "gh run download" in _executable_lines(download["run"])
    assert "--name cadrumo-python-cohort-linux" in _executable_lines(download["run"])
    assert "--name cadrumo-release-cohort" in _executable_lines(download["run"])
    # Least privilege as the RUNTIME reads it: a job-level `permissions:` block
    # REPLACES the workflow-level map rather than merging into it, so the
    # declared map below settles nothing about what any job holds. `actions:
    # write` is the watchdog's cancel capability and belongs to that job alone.
    assert document["permissions"] == {"actions": "read", "contents": "read"}
    assert job["permissions"] == {"actions": "read", "contents": "read"}
    raw_document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert jobs_granting(raw_document, "actions", "write") == ("runner-queue-watchdog",)
    assert jobs_granting(raw_document, "contents", "write") == ()


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

    assert "packaging/scoop/generate.py" in _executable_lines(generate["run"])
    assert '--cohort-dir "$env:CADRUMO_SCOOP_ROOT/cohort"' in _executable_lines(generate["run"])
    assert "$env:RUNNER_TEMP" in _executable_lines(initialize["run"])
    assert "$env:GITHUB_RUN_ATTEMPT" in _executable_lines(initialize["run"])
    assert "run-context.json" in _executable_lines(initialize["run"])
    assert initialize["id"] == "initialize"
    assert '"ready=true"' in _executable_lines(initialize["run"])
    # Every first-party module the harness executes must be staged: the smoke
    # asserts the installed venv landed on the manifest's pinned closure before
    # the tax oracle runs, so a missing constraint_effect fails the lane there.
    assert "command_execution.py" in _executable_lines(stage["run"])
    assert "constraint_effect.py" in _executable_lines(stage["run"])
    assert "installed_tax_oracle.py" in _executable_lines(stage["run"])
    assert "$env:CADRUMO_SCOOP_ROOT/harness/dev/packaging/smoke_scoop.ps1" in _executable_lines(smoke["run"])
    assert "-Mode Host" in _executable_lines(smoke["run"])
    # Negative pins: a silent revert to the container lane would strand the row
    # behind a docker-mode gate the fleet's daemon can never satisfy.
    assert "-Mode Container" not in commands
    assert "mcr.microsoft.com/windows/servercore" not in commands
    assert publish["if"] == "always() && steps.initialize.outputs.ready == 'true'"
    # Evidence rides this run's OWN artifacts; nothing reaches the releases API.
    assert "gh release" not in publish["run"]
    assert "cadrumo-scoop-acquisition-evidence.tar.gz" in _executable_lines(publish["run"])
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
    # The CLI-only lane emits from the tax oracle JSON.
    assert "--tax-evidence $tax" in _executable_lines(emit["run"])
    assert '$evidence.status -ne "passed"' in _executable_lines(verify["run"])
    assert '$evidence.mode -ne "Host"' in _executable_lines(verify["run"])
    assert "$evidence.container_identity_verified -ne $false" in _executable_lines(verify["run"])
    assert "$evidence.orchestration_nonce" in _executable_lines(verify["run"])
    assert "$evidence.source_manifest_sha256 -ne $expectedManifestHash" in _executable_lines(verify["run"])
    assert '$evidence.cleanup_status -ne "passed"' in _executable_lines(verify["run"])
    assert "$evidence.runtime_identity" in _executable_lines(verify["run"])
    # A failed smoke writes scoop-failure.json instead; surface its reason
    # rather than a bare missing-file error.
    assert "scoop-failure.json" in _executable_lines(verify["run"])


def test_the_structural_check_detects_a_branch_test_that_gates_a_dispatch() -> None:
    """Teeth for the assertion above, in the exact shape of the real defect."""
    pre_fix = chr(10).join(
        (
            'if ($run.conclusion -ne "success") { throw "no" }',
            'if ($run.head_branch -ne "main") { throw "no" }',
            'if ($run.event -eq "workflow_dispatch") {',
            "  $ancestry = Invoke-RestMethod -Uri '.../compare/main...'",
            "}",
            'elseif ($run.event -eq "push") {',
            '  if ($run.head_branch -ne "main") { throw "no" }',
            "}",
        )
    )
    dispatch_arm, _, push_arm = _executable_lines(pre_fix).partition("elseif")

    assert "head_branch" in dispatch_arm, "the pre-fix shape must be detected, or this gate is inert"
    # The pre-fix script tested the name in BOTH arms, which is why presence
    # alone could never distinguish it from the corrected shape.
    assert "head_branch" in push_arm
