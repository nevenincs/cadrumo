"""Structural gates for the three CI lanes and the workflows beside them.

Every change reaches the default branch through the merge gate
(`merge-gate.yml`), every release is proposed by `release-please.yml`, and
`release.yml` proves and publishes it. The remaining workflows are
dispatch-only reports. These gates pin that topology: which workflow may start
on a push, that the merge gate always reaches a verdict, that the verdict
requires every gate job and refuses fork pull requests, that the release cohort is built once and consumed by every
verifier, and the naming convention. Each gate is paired with an inline
defective workflow it must refuse. Workflows are enumerated from the
filesystem.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from cadrumo.core.directory_scan import scan_directory
from dev._paths import REPO_ROOT

from ..workflow_run_text import executed_text

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_MERGE_GATE: Final = _WORKFLOWS_DIR / "merge-gate.yml"
_RELEASE: Final = _WORKFLOWS_DIR / "release.yml"
_RELEASE_PLEASE: Final = _WORKFLOWS_DIR / "release-please.yml"

#: The only workflow a push to the default branch may start.
_PUSH_WORKFLOWS: Final = frozenset({_RELEASE_PLEASE.name})
#: The artifact the release build job seals and every verifier downloads.
_COHORT_ARTIFACT: Final = "cadrumo-release-cohort"
_COHORT_BUILD_JOB: Final = "build-cohort"
#: The command that builds the cohort; exactly one job may run it.
_COHORT_BUILD_COMMAND: Final = "dev.packaging.release_cohort build"
_LINT_JOB: Final = "lint"
_GATE_JOB: Final = "gate"

#: Below this the walk has stopped covering the workflow directory. Live: six
#: workflows (three lanes, three dispatch-only reports).
_MINIMUM_WORKFLOWS: Final = 6


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


def test_no_workflow_but_release_please_starts_on_a_push() -> None:
    """Pushes to main start only the release proposal; verification runs on the pull request."""
    documents = [(path, _document(path)) for path in _workflow_paths()]
    assert _push_workflows(documents) == set(_PUSH_WORKFLOWS)
    release_please = _triggers(_document(_RELEASE_PLEASE))["push"]
    assert release_please["branches"] == ["main"]


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

#: The required check. It is never skipped, so it is the one job allowed to
#: decide the pull request.
_VERDICT_JOB: Final = "verdict"
_VERDICT_CONDITION: Final = "${{ !cancelled() }}"
#: The clause that keeps a fork pull request from starting a working job.
_SAME_REPOSITORY: Final = "github.event.pull_request.head.repo.full_name == github.repository"
_FORK_HEAD: Final = "github.event.pull_request.head.repo.full_name != github.repository"


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
    if pull_request.get("branches") not in (None, ["main"]):
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
    return violations


def test_the_merge_gate_has_no_path_filter_and_an_unskippable_verdict() -> None:
    """Every pull request reaches the required verdict, and it sees every job."""
    document = _document(_MERGE_GATE)
    assert "pull_request" in _triggers(document)
    assert _merge_gate_reach_violations(document) == []


def test_the_merge_gate_reach_check_refuses_a_filter_a_skip_and_an_unwatched_job() -> None:
    """Teeth: a path filter, a skippable verdict and a job the verdict ignores."""
    document = deepcopy(_document(_MERGE_GATE))
    # `_triggers` copies the block but not its members, so this edits the document.
    _triggers(document)["pull_request"]["paths"] = ["src/**"]
    document["jobs"][_VERDICT_JOB]["if"] = "github.actor != 'dependabot[bot]'"
    document["jobs"][_VERDICT_JOB]["needs"] = [_LINT_JOB]
    assert _merge_gate_reach_violations(document) == [
        "pull_request carries a paths filter",
        f"{_VERDICT_JOB} is skippable by `if: github.actor != 'dependabot[bot]'`",
        f"{_VERDICT_JOB} does not need ['{_GATE_JOB}'], so their skip or failure goes unseen",
    ]


def _success_requirement_violations(document: dict[str, Any]) -> list[str]:
    """Why the verdict might report success while a gate job did not succeed."""
    verdict = (document.get("jobs") or {}).get(_VERDICT_JOB) or {}
    violations = [
        f"{_VERDICT_JOB} does not need {job}" for job in (_LINT_JOB, _GATE_JOB) if job not in _needs_list(verdict)
    ]
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
    """The merge verdict is red whenever lint or the scoped gate is anything but success."""
    assert _success_requirement_violations(_document(_MERGE_GATE)) == []


def test_the_success_requirement_refuses_a_verdict_that_ignores_results() -> None:
    """Teeth: dropping the dependency and commenting out the refusal are both reported."""
    document = deepcopy(_document(_MERGE_GATE))
    verdict = document["jobs"][_VERDICT_JOB]
    verdict["needs"] = []
    for step in verdict["steps"]:
        if "toJSON(needs)" in str((step.get("env") or {}).get("NEEDS", "")):
            step["run"] = "# " + str(step["run"]).replace(chr(10), chr(10) + "# ")
    assert _success_requirement_violations(document) == [
        f"{_VERDICT_JOB} does not need {_LINT_JOB}",
        f"{_VERDICT_JOB} does not need {_GATE_JOB}",
        f"{_VERDICT_JOB} has no unconditional step failing on a non-success job result",
    ]


def _fork_refusal_violations(document: dict[str, Any]) -> list[str]:
    """Why a fork pull request might start a working job or pass the verdict."""
    violations: list[str] = []
    jobs = document.get("jobs") or {}
    for name, job in jobs.items():
        if name == _VERDICT_JOB:
            continue
        condition = str(job.get("if", ""))
        # The clause must be a required conjunct, not one side of an `||`
        # that another disjunct could satisfy on a fork.
        if _SAME_REPOSITORY not in condition:
            violations.append(f"{name} can start on a fork pull request")
        elif condition.count("||") > 1 or "||" in condition.split(_SAME_REPOSITORY, 1)[1]:
            violations.append(f"{name} weakens the same-repository condition")
    verdict = jobs.get(_VERDICT_JOB) or {}
    refusal = next(
        (
            step
            for step in verdict.get("steps") or []
            if _FORK_HEAD in str(step.get("if", ""))
            and "github.event_name == 'pull_request'" in str(step.get("if", ""))
            and "exit 1" in executed_text(step.get("run"))
            and step.get("continue-on-error") is not True
        ),
        None,
    )
    if refusal is None:
        violations.append(f"{_VERDICT_JOB} does not fail a fork pull request")
    if any("checkout" in str(step.get("uses", "")) for step in verdict.get("steps") or []):
        violations.append(f"{_VERDICT_JOB} checks out code, which a fork pull request would supply")
    return violations


def test_fork_pull_requests_start_no_job_and_fail_the_verdict() -> None:
    """Refuse is the only fork policy: no working job, and a red required check."""
    assert _fork_refusal_violations(_document(_MERGE_GATE)) == []


def test_the_fork_refusal_check_detects_each_removed_clause() -> None:
    """Teeth: each removal is reported on its own, against the live document."""
    unguarded = deepcopy(_document(_MERGE_GATE))
    del unguarded["jobs"][_LINT_JOB]["if"]
    unguarded["jobs"][_GATE_JOB]["if"] = "${{ needs.lint.result == 'success' }}"
    assert _fork_refusal_violations(unguarded) == [
        f"{_LINT_JOB} can start on a fork pull request",
        f"{_GATE_JOB} can start on a fork pull request",
    ]

    widened = deepcopy(_document(_MERGE_GATE))
    widened["jobs"][_LINT_JOB]["if"] = f"${{{{ {_SAME_REPOSITORY} || github.actor == 'someone' }}}}"
    assert _fork_refusal_violations(widened) == [f"{_LINT_JOB} weakens the same-repository condition"]

    permissive = deepcopy(_document(_MERGE_GATE))
    permissive["jobs"][_VERDICT_JOB]["steps"] = [
        step for step in permissive["jobs"][_VERDICT_JOB]["steps"] if _FORK_HEAD not in str(step.get("if", ""))
    ]
    permissive["jobs"][_VERDICT_JOB]["steps"].insert(0, {"uses": "actions/checkout@" + "0" * 40})
    assert _fork_refusal_violations(permissive) == [
        f"{_VERDICT_JOB} does not fail a fork pull request",
        f"{_VERDICT_JOB} checks out code, which a fork pull request would supply",
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
