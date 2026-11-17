"""Structural gates for the CI lanes and the workflows beside them.

Every change reaches a protected branch through the headless merge gate
(`merge-gate.yml`); the native lane (`native.yml`) is advisory beside it;
every release is proposed by `release-please.yml`, and `release.yml` proves
and publishes it. The remaining workflows are dispatch-only reports. These
gates pin that topology: which workflow may start on a push, that the merge
gate always reaches a verdict under the required name, that the verdict
requires every gate job, that the test matrix runs the shards it planned, that
the release cohort is built once and consumed by every verifier, and the naming
convention. Which jobs a pull request may reach, and what they may hold, is
pinned in `test_workflow_trust.py`. Each gate is paired with a defective
workflow it must refuse. Workflows are enumerated from the filesystem.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from cadrumo.core.directory_scan import scan_directory
from dev.paths import REPO_ROOT

from ..workflow_run_text import executed_text

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_MERGE_GATE: Final = _WORKFLOWS_DIR / "merge-gate.yml"
_RELEASE: Final = _WORKFLOWS_DIR / "release.yml"
_RELEASE_PLEASE: Final = _WORKFLOWS_DIR / "release-please.yml"
_DEFAULT_BRANCH: Final = "feature/tui"
#: Releases are proposed and cut from main only; feature/tui never starts one.
_RELEASE_BRANCH: Final = "main"
#: Pull requests into either branch run the merge gate.
_GATED_BRANCHES: Final = [_DEFAULT_BRANCH, _RELEASE_BRANCH]

#: The workflows a push may start: the release proposal on main, the merge gate on feature/tui.
_PUSH_WORKFLOWS: Final = frozenset({_RELEASE_PLEASE.name, _MERGE_GATE.name})
#: The artifact the release build job seals and every verifier downloads.
_COHORT_ARTIFACT: Final = "cadrumo-release-cohort"
_COHORT_BUILD_JOB: Final = "build-cohort"
#: The command that builds the cohort; exactly one job may run it.
_COHORT_BUILD_COMMAND: Final = "dev.packaging.release_cohort build"

#: Below this the walk has stopped covering the workflow directory. Live: seven
#: workflows (the merge gate, the native lane, the two release workflows and
#: three dispatch-only reports).
_MINIMUM_WORKFLOWS: Final = 7


def _document(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(document: dict[str, Any]) -> dict[str, Any]:
    trigger = document.get("on", document.get(True))
    if isinstance(trigger, str):
        return {trigger: None}
    if isinstance(trigger, list):
        return dict.fromkeys(trigger)
    return dict(trigger or {})


def _workflow_paths() -> list[Path]:
    """Every workflow GitHub reads, with the walk itself floored."""
    assert _WORKFLOWS_DIR.is_dir(), f"no workflow directory at {_WORKFLOWS_DIR}"
    found = sorted(
        {*scan_directory(_WORKFLOWS_DIR, pattern="*.yml"), *scan_directory(_WORKFLOWS_DIR, pattern="*.yaml")}
    )
    assert len(found) >= _MINIMUM_WORKFLOWS, (
        f"only {len(found)} workflow(s) were walked; below this an empty finding list says "
        "nothing about what the lanes actually do"
    )
    return found


def _steps_run(job: dict[str, Any]) -> str:
    return executed_text(step.get("run") for step in job.get("steps") or [])


# --- naming -------------------------------------------------------------------


def _naming_violations(path: Path, document: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    if not str(document.get("name", "")).startswith("Cadrumo "):
        violations.append(f"{path.name}: workflow name does not start with 'Cadrumo '")
    if path.stem != path.stem.lower() or " " in path.stem or "_" in path.stem:
        violations.append(f"{path.name}: filename is not kebab-case")
    return violations


def test_every_workflow_follows_the_naming_pattern() -> None:
    """Kebab-case filenames, and a `name:` that leads with the product identity."""
    violations = [entry for path in _workflow_paths() for entry in _naming_violations(path, _document(path))]
    assert violations == []


def test_the_naming_gate_refuses_a_misnamed_workflow() -> None:
    """Teeth: a snake_case file with an unbranded name is refused on both counts."""
    assert _naming_violations(Path("Nightly_Build.yml"), {"name": "Nightly"}) == [
        "Nightly_Build.yml: workflow name does not start with 'Cadrumo '",
        "Nightly_Build.yml: filename is not kebab-case",
    ]


# --- push triggers ------------------------------------------------------------


def _push_workflows(documents: list[tuple[Path, dict[str, Any]]]) -> set[str]:
    return {path.name for path, document in documents if "push" in _triggers(document)}


def test_a_push_starts_only_the_release_proposal_on_main_and_the_merge_gate_on_feature_tui() -> None:
    """A push to main proposes a release; a landing pushed to feature/tui is measured by the merge gate alone."""
    documents = [(path, _document(path)) for path in _workflow_paths()]
    assert _push_workflows(documents) == set(_PUSH_WORKFLOWS)
    release_please = _triggers(_document(_RELEASE_PLEASE))["push"]
    assert release_please["branches"] == [_RELEASE_BRANCH]
    merge_gate = _triggers(_document(_MERGE_GATE))["push"]
    assert merge_gate["branches"] == [_DEFAULT_BRANCH]


def test_the_push_gate_refuses_a_second_push_workflow() -> None:
    """Teeth: a lane re-acquiring a push trigger is reported."""
    rogue = yaml.safe_load("name: Cadrumo Rogue\non:\n  push:\n    branches: [main]\njobs: {}\n")
    documents = [(_RELEASE_PLEASE, _document(_RELEASE_PLEASE)), (Path("rogue.yml"), rogue)]
    assert _push_workflows(documents) == {_RELEASE_PLEASE.name, "rogue.yml"}


def _no_schedule_violations(documents: list[tuple[Path, dict[str, Any]]]) -> list[str]:
    return [path.name for path, document in documents if "schedule" in _triggers(document)]


def test_no_workflow_carries_standing_compute() -> None:
    """The reports beside the lanes run on dispatch only; nothing is scheduled."""
    assert _no_schedule_violations([(path, _document(path)) for path in _workflow_paths()]) == []


def test_the_schedule_gate_refuses_a_cron() -> None:
    """Teeth: a scheduled workflow is reported."""
    cron = yaml.safe_load("name: Cadrumo Cron\non:\n  schedule:\n    - cron: '0 3 * * 1'\njobs: {}\n")
    assert _no_schedule_violations([(Path("cron.yml"), cron)]) == ["cron.yml"]


# --- merge gate ---------------------------------------------------------------

#: The required check. `always()` runs it after a failure, a skip or a
#: cancellation, so it is the one job allowed to decide the pull request.
_VERDICT_JOB: Final = "verdict"
_VERDICT_CONDITION: Final = "${{ always() }}"
#: The context the branch rulesets require, as a literal: a name computed from
#: the event could report under another name and leave the requirement unmet
#: or, worse, met by a job that checked nothing.
_REQUIRED_CHECK: Final = "Check: Merge gate (Linux)"
_HOSTED_RUNNER: Final = "ubuntu-24.04"


def _needs_list(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs")
    return [needs] if isinstance(needs, str) else list(needs or [])


def _merge_gate_reach_violations(document: dict[str, Any]) -> list[str]:
    """Why the merge gate might fail to reach a verdict on some pull request."""
    violations: list[str] = []
    pull_request = _triggers(document).get("pull_request") or {}
    for key in ("paths", "paths-ignore", "branches-ignore"):
        if key in pull_request:
            violations.append(f"pull_request carries a {key} filter")
    if pull_request.get("branches") not in (None, _GATED_BRANCHES):
        violations.append(f"pull_request is narrowed to branches {pull_request['branches']}")
    jobs = document.get("jobs") or {}
    verdict = jobs.get(_VERDICT_JOB)
    if verdict is None:
        return [*violations, f"no {_VERDICT_JOB} job"]
    if str(verdict.get("if", "")).strip() != _VERDICT_CONDITION:
        violations.append(f"{_VERDICT_JOB} is skippable by `if: {verdict.get('if')}`")
    if verdict.get("continue-on-error") is True:
        violations.append(f"{_VERDICT_JOB} is advisory")
    missing = sorted(set(jobs) - {_VERDICT_JOB} - set(_needs_list(verdict)))
    if missing:
        violations.append(f"{_VERDICT_JOB} does not need {missing}, so their skip or failure goes unseen")
    # A job the verdict needs must not be skippable either: the verdict would
    # refuse the skip, and every pull request the condition excludes would be
    # unmergeable, which is how a gate gets switched off.
    violations.extend(
        f"{name} is skippable by `if: {job['if']}`"
        for name, job in jobs.items()
        if name != _VERDICT_JOB and "if" in job
    )
    violations.extend(
        f"{name} is advisory"
        for name, job in jobs.items()
        if name != _VERDICT_JOB and job.get("continue-on-error") is not None
    )
    return violations


def test_the_merge_gate_has_no_path_filter_and_an_unskippable_verdict() -> None:
    """Every pull request reaches the required verdict, and it sees every job."""
    document = _document(_MERGE_GATE)
    assert "pull_request" in _triggers(document)
    assert len(document["jobs"]) >= 8, "the gate has lost the jobs its verdict is meant to watch"
    assert _merge_gate_reach_violations(document) == []


def test_the_merge_gate_reach_check_refuses_a_filter_a_skip_and_an_unwatched_job() -> None:
    """Teeth: a path filter, a skippable verdict, a job the verdict ignores, and a skippable or advisory job."""
    document = deepcopy(_document(_MERGE_GATE))
    # `_triggers` copies the block but not its members, so this edits the document.
    _triggers(document)["pull_request"]["paths"] = ["src/**"]
    document["jobs"][_VERDICT_JOB]["if"] = "${{ !cancelled() }}"
    document["jobs"][_VERDICT_JOB]["needs"] = [
        name for name in document["jobs"] if name not in {_VERDICT_JOB, "tests", "fixtures"}
    ]
    document["jobs"]["lint"]["if"] = "github.actor != 'dependabot[bot]'"
    document["jobs"]["harness"]["continue-on-error"] = True
    assert _merge_gate_reach_violations(document) == [
        "pull_request carries a paths filter",
        f"{_VERDICT_JOB} is skippable by `if: ${{{{ !cancelled() }}}}`",
        f"{_VERDICT_JOB} does not need ['fixtures', 'tests'], so their skip or failure goes unseen",
        "lint is skippable by `if: github.actor != 'dependabot[bot]'`",
        "harness is advisory",
    ]


def test_the_merge_gate_is_never_dispatched() -> None:
    """A dispatched gate run attaches its checks to no pull request, so it proves nothing a merge needs."""
    assert "workflow_dispatch" not in _triggers(_document(_MERGE_GATE))


def _success_requirement_violations(document: dict[str, Any]) -> list[str]:
    """Why the verdict might report success while a gate job did not succeed."""
    verdict = (document.get("jobs") or {}).get(_VERDICT_JOB) or {}
    violations: list[str] = []
    guard = next(
        (
            step
            for step in verdict.get("steps") or []
            if "toJSON(needs)" in str((step.get("env") or {}).get("NEEDS", ""))
            and '.value.result != "success"' in executed_text(step.get("run"))
            and "exit 1" in executed_text(step.get("run"))
            and not step.get("if")
            and step.get("continue-on-error") is not True
        ),
        None,
    )
    if guard is None:
        violations.append(f"{_VERDICT_JOB} has no unconditional step failing on a non-success job result")
    return violations


def test_the_verdict_requires_every_gate_job_to_succeed() -> None:
    """The merge verdict is red whenever any job it needs is anything but success."""
    assert _success_requirement_violations(_document(_MERGE_GATE)) == []


@pytest.mark.parametrize("weakening", ["comment", "condition"])
def test_the_success_requirement_refuses_a_verdict_that_ignores_results(weakening: str) -> None:
    """Teeth: commenting out the refusal, and making it conditional, are each reported."""
    document = deepcopy(_document(_MERGE_GATE))
    for step in document["jobs"][_VERDICT_JOB]["steps"]:
        if "toJSON(needs)" in str((step.get("env") or {}).get("NEEDS", "")):
            if weakening == "comment":
                step["run"] = "# " + str(step["run"]).replace(chr(10), chr(10) + "# ")
            else:
                step["if"] = "github.event_name == 'pull_request'"
    assert _success_requirement_violations(document) == [
        f"{_VERDICT_JOB} has no unconditional step failing on a non-success job result"
    ]


def _verdict_identity_violations(document: dict[str, Any]) -> list[str]:
    """Why the verdict might miss the required context, or run code a pull request wrote."""
    violations: list[str] = []
    jobs = document.get("jobs") or {}
    verdict = jobs.get(_VERDICT_JOB) or {}
    if verdict.get("name") != _REQUIRED_CHECK:
        violations.append(f"{_VERDICT_JOB} does not report as {_REQUIRED_CHECK!r}")
    impostors = sorted(
        name for name, job in jobs.items() if name != _VERDICT_JOB and job.get("name") == _REQUIRED_CHECK
    )
    violations.extend(f"{name} also reports as {_REQUIRED_CHECK!r}" for name in impostors)
    if verdict.get("runs-on") != _HOSTED_RUNNER:
        violations.append(f"{_VERDICT_JOB} does not run on {_HOSTED_RUNNER}")
    if "strategy" in verdict:
        violations.append(f"{_VERDICT_JOB} is a matrix, so its check name is not the required one")
    if any("uses" in step for step in verdict.get("steps") or []):
        violations.append(f"{_VERDICT_JOB} runs an action or checks out code it never needs")
    return violations


def test_the_verdict_reports_the_required_check_and_runs_no_repository_code() -> None:
    """One job, on a hosted runner, carries the exact context the rulesets require."""
    assert _verdict_identity_violations(_document(_MERGE_GATE)) == []


def test_the_verdict_identity_check_detects_each_drift() -> None:
    """Teeth: a renamed verdict, a second job under its name, a moved runner, a matrix and a checkout."""
    document = deepcopy(_document(_MERGE_GATE))
    verdict = document["jobs"][_VERDICT_JOB]
    verdict["name"] = "${{ github.event_name == 'pull_request' && 'Check: Merge gate (Linux)' || 'Check: other' }}"
    document["jobs"]["lint"]["name"] = _REQUIRED_CHECK
    verdict["runs-on"] = ["self-hosted", "Linux", "X64"]
    verdict["strategy"] = {"matrix": {"leg": [1, 2]}}
    verdict["steps"].insert(0, {"uses": "actions/checkout@" + "0" * 40})
    assert _verdict_identity_violations(document) == [
        f"{_VERDICT_JOB} does not report as {_REQUIRED_CHECK!r}",
        f"lint also reports as {_REQUIRED_CHECK!r}",
        f"{_VERDICT_JOB} does not run on {_HOSTED_RUNNER}",
        f"{_VERDICT_JOB} is a matrix, so its check name is not the required one",
        f"{_VERDICT_JOB} runs an action or checks out code it never needs",
    ]


# --- the test matrix ----------------------------------------------------------


def _shard_matrix_violations(document: dict[str, Any]) -> list[str]:
    """Why the planned shards and the executed shards might differ, or a shard might hide a failure."""
    jobs = document.get("jobs") or {}
    plan, tests = jobs.get("plan") or {}, jobs.get("tests") or {}
    violations: list[str] = []
    if "just test-gate-plan" not in _steps_run(plan):
        violations.append("plan does not print the shard matrix through its recipe")
    if (plan.get("outputs") or {}).get("shards") != "${{ steps.plan.outputs.shards }}":
        violations.append("plan does not publish the shard matrix")
    strategy = tests.get("strategy") or {}
    if (strategy.get("matrix") or {}).get("shard") != "${{ fromJSON(needs.plan.outputs.shards) }}":
        violations.append("tests does not expand the planned shard matrix")
    if strategy.get("fail-fast") is not False:
        violations.append("tests stops its other shards at the first red one")
    if "just test-gate-shard" not in _steps_run(tests):
        violations.append("tests does not run a shard through its recipe")
    if not str((tests.get("env") or {}).get("CADRUMO_PYTEST_WORKERS", "")).isdigit():
        violations.append("tests does not pin its worker count")
    return violations


def test_the_test_matrix_executes_exactly_the_shards_the_plan_printed() -> None:
    """One selection plans the matrix and feeds every shard, and no shard is cut short by another."""
    assert _shard_matrix_violations(_document(_MERGE_GATE)) == []


def test_the_shard_matrix_check_detects_a_fixed_matrix_and_a_fail_fast() -> None:
    """Teeth: a hand-written shard list, a fail-fast matrix and an unpinned pool are each reported."""
    document = deepcopy(_document(_MERGE_GATE))
    tests = document["jobs"]["tests"]
    tests["strategy"] = {"matrix": {"shard": ["1/2", "2/2"]}}
    del tests["env"]["CADRUMO_PYTEST_WORKERS"]
    assert _shard_matrix_violations(document) == [
        "tests does not expand the planned shard matrix",
        "tests stops its other shards at the first red one",
        "tests does not pin its worker count",
    ]


# --- release cohort -----------------------------------------------------------


def _needs(job: dict[str, Any]) -> set[str]:
    needs = job.get("needs")
    return {needs} if isinstance(needs, str) else set(needs or [])


def _downloads_cohort(job: dict[str, Any]) -> bool:
    return any(
        "download-artifact" in str(step.get("uses", "")) and (step.get("with") or {}).get("name") == _COHORT_ARTIFACT
        for step in job.get("steps") or []
    )


def _cohort_violations(document: dict[str, Any]) -> list[str]:
    """Why the release proof might not verify the one cohort it built."""
    jobs = document.get("jobs") or {}
    violations: list[str] = []
    builders = sorted(name for name, job in jobs.items() if _COHORT_BUILD_COMMAND in _steps_run(job))
    if builders != [_COHORT_BUILD_JOB]:
        violations.append(f"the cohort is built by {builders}, not by {_COHORT_BUILD_JOB} alone")
    uploaders = sorted(
        name
        for name, job in jobs.items()
        for step in job.get("steps") or []
        if "upload-artifact" in str(step.get("uses", "")) and (step.get("with") or {}).get("name") == _COHORT_ARTIFACT
    )
    if uploaders != [_COHORT_BUILD_JOB]:
        violations.append(f"the cohort artifact is uploaded by {uploaders}")
    consumers = [name for name, job in jobs.items() if _COHORT_BUILD_JOB in _needs(job)]
    verifiers = [name for name in consumers if name.startswith("test-")]
    if not verifiers:
        violations.append(f"no verify job consumes {_COHORT_BUILD_JOB}")
    violations.extend(
        f"{name} needs {_COHORT_BUILD_JOB} but does not download {_COHORT_ARTIFACT}"
        for name in verifiers
        if not _downloads_cohort(jobs[name])
    )
    return violations


def test_the_release_builds_the_cohort_once_and_every_verifier_consumes_it() -> None:
    """One sealed cohort, built in one job, is what every verify job installs."""
    assert _cohort_violations(_document(_RELEASE)) == []


def test_the_cohort_check_refuses_a_verifier_that_rebuilds() -> None:
    """Teeth: a verify job that builds its own cohort instead of downloading it is reported."""
    document = deepcopy(_document(_RELEASE))
    verifier = next(
        name for name, job in document["jobs"].items() if name.startswith("test-") and _downloads_cohort(job)
    )
    steps = document["jobs"][verifier]["steps"]
    document["jobs"][verifier]["steps"] = [
        {"name": "Rebuild", "run": f"uv run --no-sync python -m {_COHORT_BUILD_COMMAND} --output dist"},
        *(step for step in steps if "download-artifact" not in str(step.get("uses", ""))),
    ]
    assert _cohort_violations(document) == [
        f"the cohort is built by {sorted([_COHORT_BUILD_JOB, verifier])}, not by {_COHORT_BUILD_JOB} alone",
        f"{verifier} needs {_COHORT_BUILD_JOB} but does not download {_COHORT_ARTIFACT}",
    ]


# --- dependency installation and dispatch-only reports ------------------------


def _unfrozen_syncs(documents: list[tuple[Path, dict[str, Any]]]) -> list[str]:
    offending: list[str] = []
    for path, document in documents:
        for job_name, job in (document.get("jobs") or {}).items():
            for line in _steps_run(job).splitlines():
                stripped = line.strip()
                if stripped.startswith("uv sync") and "--frozen" not in stripped and "--locked" not in stripped:
                    offending.append(f"{path.name}:{job_name}: {stripped}")
    return offending


def test_no_workflow_installs_python_dependencies_unfrozen() -> None:
    """Every lane installs from the committed lock, never a live resolve."""
    assert _unfrozen_syncs([(path, _document(path)) for path in _workflow_paths()]) == []


def test_the_frozen_install_gate_refuses_a_bare_sync() -> None:
    """Teeth: a bare `uv sync` is reported."""
    document = yaml.safe_load(
        "name: Cadrumo Resolve\non: workflow_dispatch\njobs:\n  setup:\n    steps:\n      - run: uv sync\n"
    )
    assert _unfrozen_syncs([(Path("resolve.yml"), document)]) == ["resolve.yml:setup: uv sync"]


def test_no_lane_verifies_a_website_this_repository_does_not_contain() -> None:
    """Refuse external-site source or CI ownership in the product repository."""
    assert not (REPO_ROOT / "frontend" / "package.json").exists(), (
        "external-site source does not belong in the product repository"
    )
    assert not (_WORKFLOWS_DIR / "frontend.yml").exists(), "an external-site lane entered the product repository"


def test_drift_detector_targets_exist_on_disk() -> None:
    """Every drift-detector pytest target must exist on disk.

    A dispatch-only workflow whose pytest targets moved leaves a red run nobody
    attributes.
    """
    document = _document(_WORKFLOWS_DIR / "aeat-drift-detector.yml")
    commands = executed_text(step.get("run") for job in document["jobs"].values() for step in job["steps"])
    targets = [token for token in commands.replace("\\", " ").split() if token.startswith("src/")]
    assert targets, "drift detector runs no src-tree pytest targets"
    for target in targets:
        assert (REPO_ROOT / target).exists(), f"drift-detector target moved or deleted: {target}"
