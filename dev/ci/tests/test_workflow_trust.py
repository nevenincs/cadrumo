"""Fork and pull request safety of the workflows, read from the files themselves.

The live workflows must satisfy every rule in :mod:`dev.ci.workflow_trust`,
and each rule is paired with a planted defect, built in isolation, that it
must report. The two lanes are also pinned to their sides of the split: the
merge gate runs on hosted runners only, the native lane on self-hosted
runners only. The merge gate's concurrency is pinned in both directions: a
pull request's superseded run is cancelled, and no landed head's run is.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from cadrumo.core.directory_scan import scan_directory
from dev.paths import REPO_ROOT

from ..workflow_trust import (
    ADMISSION,
    HOSTED_RUNNERS,
    admission_violations,
    checkout_credential_violations,
    is_hosted,
    landed_head_violations,
    pull_request_reachable,
    pull_request_target_violations,
    superseded_run_violations,
    triggers,
    untrusted_job_violations,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_MERGE_GATE: Final = "merge-gate.yml"
_NATIVE: Final = "native.yml"
#: Below this the walk has stopped covering the workflow directory.
_MINIMUM_WORKFLOWS: Final = 7
_CHECKOUT: Final = "actions/checkout@" + "0" * 40


def _live() -> list[tuple[str, dict[str, Any]]]:
    paths = sorted(scan_directory(_WORKFLOWS_DIR, pattern="*.yml"))
    assert len(paths) >= _MINIMUM_WORKFLOWS, f"only {len(paths)} workflow(s) were walked"
    assert not list(scan_directory(_WORKFLOWS_DIR, pattern="*.yaml")), "a .yaml workflow would escape this walk"
    return [(path.name, yaml.safe_load(path.read_text(encoding="utf-8"))) for path in paths]


def _workflow(name: str) -> dict[str, Any]:
    return dict(_live())[name]


def _planted(text: str) -> list[tuple[str, dict[str, Any]]]:
    return [("planted.yml", yaml.safe_load(text))]


def _job(*, runs_on: str = "ubuntu-24.04", condition: str | None = None, body: str = "") -> str:
    guard = f"    if: ${{{{ {condition} }}}}\n" if condition is not None else ""
    return f"  probe:\n{guard}    runs-on: {runs_on}\n{body}    steps:\n      - run: echo probe\n"


def _pull_request_workflow(job: str, *, head: str = "") -> str:
    return f"name: Cadrumo Planted\non:\n  pull_request:\n{head}jobs:\n{job}"


# --- the live workflows -------------------------------------------------------


def test_some_workflow_is_reachable_by_a_pull_request() -> None:
    """Anchor: with no pull request workflow every rule below would hold of nothing."""
    reachable = {name for name, document in _live() if pull_request_reachable(document)}
    assert {_MERGE_GATE, _NATIVE} <= reachable


def test_no_workflow_runs_on_pull_request_target() -> None:
    assert pull_request_target_violations(_live()) == []


def test_no_untrusted_pull_request_reaches_a_self_hosted_runner() -> None:
    assert admission_violations(_live()) == []


def test_no_pull_request_job_holds_a_secret_a_variable_or_a_write_permission() -> None:
    assert untrusted_job_violations(_live()) == []


def test_every_checkout_drops_its_credentials() -> None:
    documents = _live()
    checkouts = [
        step
        for _, document in documents
        for job in document["jobs"].values()
        for step in job.get("steps") or []
        if str(step.get("uses", "")).startswith("actions/checkout@")
    ]
    assert len(checkouts) >= 10, "the walk found too few checkouts to say anything about them"
    assert checkout_credential_violations(documents) == []


def test_a_superseded_pull_request_run_is_cancelled() -> None:
    assert superseded_run_violations(_live()) == []


def test_every_landed_head_keeps_its_own_run() -> None:
    """A push to the development branch neither cancels nor replaces an earlier head's run."""
    documents = _live()
    assert landed_head_violations(documents) == []
    # Anchor: the merge gate is the workflow the rule judges, and it still
    # runs on a push to the development branch alone.
    assert triggers(_workflow(_MERGE_GATE))["push"] == {"branches": ["feature/tui"]}
    judged = [name for name, document in documents if (triggers(document).get("push") or {}).get("branches")]
    assert _MERGE_GATE in judged


def test_the_merge_gate_runs_on_hosted_runners_only() -> None:
    """The headless lane never touches a self-hosted machine, so a fork may run all of it."""
    jobs = _workflow(_MERGE_GATE)["jobs"]
    assert len(jobs) >= 8
    assert [name for name, job in jobs.items() if not is_hosted(job)] == []
    # Hosted jobs need no admission, and carrying one would withhold the
    # verdict from the fork pull requests this lane exists to serve.
    assert [name for name, job in jobs.items() if ADMISSION in str(job.get("if", ""))] == []


def test_the_native_lane_runs_on_self_hosted_runners_only_and_never_decides_a_merge() -> None:
    """Native work stays off hosted runners, and its jobs cannot satisfy the required check."""
    document = _workflow(_NATIVE)
    jobs = document["jobs"]
    assert jobs, "the native lane declares no job"
    assert [name for name, job in jobs.items() if "self-hosted" not in str(job.get("runs-on"))] == []
    assert "Check: Merge gate (Linux)" not in {job.get("name") for job in jobs.values()}
    assert set(triggers(document)) == {"pull_request", "workflow_dispatch", "workflow_call"}
    assert triggers(document)["pull_request"].get("paths"), "an unfiltered native lane would run on every pull request"


def test_the_headless_lane_builds_no_native_code() -> None:
    """No hosted job configures CMake, builds Rust or drives a desktop window."""
    text = yaml.safe_dump(_workflow(_MERGE_GATE)["jobs"])
    for token in ("cmake", "rustup", "cargo", "tauri", "test-native", "test-frontend", "test-windows", "xvfb"):
        assert token not in text.lower(), f"the headless lane names {token}"


# --- teeth --------------------------------------------------------------------


def test_the_target_rule_reports_a_pull_request_target_trigger() -> None:
    planted = _planted("name: Cadrumo Planted\non:\n  pull_request_target:\njobs:\n" + _job())
    assert pull_request_target_violations(planted) == ["planted.yml runs on pull_request_target"]


@pytest.mark.parametrize(
    ("runs_on", "condition", "expected"),
    [
        ("[self-hosted, Linux, X64]", None, "without the admission clause"),
        ("[self-hosted, Linux, X64]", "github.event.pull_request.head.repo.full_name == github.repository", "without"),
        ("[self-hosted, Linux, X64]", f"!{ADMISSION}", "without the admission clause"),
        ("[self-hosted, Linux, X64]", f"{ADMISSION} || github.actor == 'someone'", "behind a widened admission clause"),
        ("${{ matrix.runner }}", None, "without the admission clause"),
        ("ubuntu-latest-8-cores", None, "without the admission clause"),
    ],
)
def test_the_admission_rule_reports_each_way_onto_a_self_hosted_runner(
    runs_on: str, condition: str | None, expected: str
) -> None:
    """An unguarded, weakly guarded, negated or widened job, and a runner that is not provably hosted."""
    planted = _planted(_pull_request_workflow(_job(runs_on=runs_on, condition=condition)))
    violations = admission_violations(planted)
    assert len(violations) == 1
    assert violations[0].startswith("planted.yml: probe reaches a self-hosted runner")
    assert expected in violations[0]


def test_the_admission_rule_accepts_a_guarded_job_and_a_hosted_one() -> None:
    """The positive control: the rule is not satisfied only by having no jobs."""
    guarded = _job(runs_on="[self-hosted, Linux, X64]", condition=f"{ADMISSION} && github.event_name != 'pull_request'")
    assert admission_violations(_planted(_pull_request_workflow(guarded))) == []
    assert admission_violations(_planted(_pull_request_workflow(_job()))) == []
    assert "ubuntu-24.04" in HOSTED_RUNNERS


def test_the_admission_rule_follows_a_called_workflow_and_refuses_a_foreign_one() -> None:
    """A callable workflow is judged as pull request reachable; a call out of the repository needs the clause."""
    callee = yaml.safe_load(
        "name: Cadrumo Callee\non:\n  workflow_call:\njobs:\n" + _job(runs_on="[self-hosted, Linux, X64]")
    )
    caller = yaml.safe_load(
        "name: Cadrumo Caller\non:\n  pull_request:\njobs:\n"
        "  local:\n    uses: ./.github/workflows/callee.yml\n"
        "  foreign:\n    uses: someone/else/.github/workflows/build.yml@" + "0" * 40 + "\n"
    )
    assert admission_violations([("callee.yml", callee), ("caller.yml", caller)]) == [
        "callee.yml: probe reaches a self-hosted runner without the admission clause",
        "caller.yml: foreign calls a workflow outside the repository without the admission clause",
    ]


def test_the_admission_rule_reports_a_label_trigger() -> None:
    planted = _planted(_pull_request_workflow(_job(), head="    types: [opened, labeled]\n"))
    assert admission_violations(planted) == ["planted.yml admits label events, which a bot can raise"]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            "    env:\n      TOKEN: ${{ secrets.HOMEBREW_TAP_TOKEN }}\n",
            "planted.yml: probe references HOMEBREW_TAP_TOKEN",
        ),
        ("    env:\n      TOKEN: ${{ secrets['PYPI'] }}\n", "planted.yml: probe references PYPI"),
        ("    env:\n      ALL: ${{ toJSON(secrets) }}\n", "planted.yml: probe references the whole secrets object"),
        (
            "    env:\n      DIR: ${{ vars.CADRUMO_PACKAGE_AGENT_SOURCE_DIR }}\n",
            "planted.yml: probe reads a repository variable on an untrusted pull request",
        ),
        (
            "    permissions:\n      contents: write\n",
            "planted.yml: probe holds contents: write on an untrusted pull request",
        ),
    ],
)
def test_the_untrusted_job_rule_reports_each_thing_a_pull_request_could_take(body: str, expected: str) -> None:
    """A secret by either spelling, the whole secrets object, a repository variable and a write scope."""
    head = "" if "permissions" in body else "permissions:\n  contents: read\n"
    planted = _planted(head + _pull_request_workflow(_job(body=body)))
    assert untrusted_job_violations(planted) == [expected]


def test_the_untrusted_job_rule_reports_an_undeclared_permission_set_and_inherited_secrets() -> None:
    """Repository settings decide an undeclared token, so the file cannot call it read-only."""
    undeclared = _planted(_pull_request_workflow(_job()))
    assert untrusted_job_violations(undeclared) == [
        "planted.yml: probe holds an undeclared permission set on an untrusted pull request"
    ]
    inheriting = _planted(
        "name: Cadrumo Planted\npermissions:\n  contents: read\non:\n  pull_request:\njobs:\n"
        "  probe:\n    uses: ./.github/workflows/callee.yml\n    secrets: inherit\n"
    )
    assert untrusted_job_violations(inheriting) == ["planted.yml: probe inherits its caller's secrets"]


def test_the_untrusted_job_rule_allows_the_run_token_and_an_admitted_variable() -> None:
    """The positive control: the run's own token, and a variable behind the admission clause."""
    own = "    env:\n      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n"
    variable = "    env:\n      DIR: ${{ vars.CADRUMO_PACKAGE_AGENT_SOURCE_DIR }}\n"
    head = "permissions:\n  contents: read\n"
    assert untrusted_job_violations(_planted(head + _pull_request_workflow(_job(body=own)))) == []
    admitted = _job(runs_on="[self-hosted, Linux, X64]", condition=ADMISSION, body=variable)
    assert untrusted_job_violations(_planted(head + _pull_request_workflow(admitted))) == []
    # Still no secret, admitted or not.
    secret = _job(condition=ADMISSION, body="    env:\n      T: ${{ secrets.PYPI }}\n")
    assert untrusted_job_violations(_planted(head + _pull_request_workflow(secret))) == [
        "planted.yml: probe references PYPI"
    ]


def test_the_checkout_rule_reports_a_persisted_and_a_defaulted_credential(tmp_path: Path) -> None:
    """An explicit true and an omitted key both leave the token in the working tree."""
    workflow = tmp_path / "planted.yml"
    workflow.write_text(
        "name: Cadrumo Planted\non: workflow_dispatch\njobs:\n"
        f"  kept:\n    runs-on: ubuntu-24.04\n    steps:\n      - uses: {_CHECKOUT}\n"
        "        with:\n          persist-credentials: true\n"
        f"  defaulted:\n    runs-on: ubuntu-24.04\n    steps:\n      - uses: {_CHECKOUT}\n"
        f"  dropped:\n    runs-on: ubuntu-24.04\n    steps:\n      - uses: {_CHECKOUT}\n"
        "        with:\n          persist-credentials: false\n",
        encoding="utf-8",
    )
    planted = [(workflow.name, yaml.safe_load(workflow.read_text(encoding="utf-8")))]
    assert checkout_credential_violations(planted) == [
        "planted.yml: kept checks out with persisted credentials",
        "planted.yml: defaulted checks out with persisted credentials",
    ]


def test_the_superseded_run_rule_reports_a_missing_group_and_a_run_left_going() -> None:
    bare = _planted(_pull_request_workflow(_job()))
    assert superseded_run_violations(bare) == ["planted.yml declares no concurrency group"]
    loose = _planted(
        "concurrency:\n  group: gate-${{ github.ref }}\n  cancel-in-progress: false\n" + _pull_request_workflow(_job())
    )
    assert superseded_run_violations(loose) == [
        "planted.yml does not group runs by pull request",
        "planted.yml does not cancel a superseded run",
    ]


_PUSH_SUFFIX: Final = "${{ github.event_name == 'push' && format('-{0}', github.sha) || '' }}"
_PULL_REQUESTS_ONLY: Final = "${{ github.event_name == 'pull_request' }}"


def _landing_workflow(*, group: str, cancel: str, job: str = "", branch: str = "feature/tui") -> str:
    return (
        f"name: Cadrumo Planted\nconcurrency:\n  group: {group}\n  cancel-in-progress: {cancel}\n"
        f"on:\n  pull_request:\n  push:\n    branches: [{branch}]\njobs:\n" + (job or _job())
    )


_PER_REQUEST_GROUP: Final = "gate-${{ github.event.pull_request.number || github.ref }}-${{ github.event_name }}"


@pytest.mark.parametrize(
    ("group", "cancel", "expected"),
    [
        # The gate as it stood: every landing cancelled the run before it.
        (
            _PER_REQUEST_GROUP,
            "true",
            [
                "planted.yml lets the runs of two landed heads share a concurrency group",
                "planted.yml lets a push cancel the run of an earlier landed head",
            ],
        ),
        # Nothing is cancelled in progress, yet a third landing still replaces
        # the pending run of the second.
        (
            _PER_REQUEST_GROUP,
            _PULL_REQUESTS_ONLY,
            ["planted.yml lets the runs of two landed heads share a concurrency group"],
        ),
        # A commit in every group would isolate the pushes and is refused all
        # the same: the suffix must be the push-only one.
        (
            _PER_REQUEST_GROUP + "-${{ github.sha }}",
            _PULL_REQUESTS_ONLY,
            ["planted.yml lets the runs of two landed heads share a concurrency group"],
        ),
        (
            _PER_REQUEST_GROUP + _PUSH_SUFFIX,
            "${{ github.event_name != 'workflow_call' }}",
            ["planted.yml lets a push cancel the run of an earlier landed head"],
        ),
    ],
)
def test_the_landed_head_rule_reports_each_way_a_landing_ends_an_earlier_run(
    group: str, cancel: str, expected: list[str]
) -> None:
    assert landed_head_violations(_planted(_landing_workflow(group=group, cancel=cancel))) == expected


def test_the_landed_head_rule_reports_a_job_level_group() -> None:
    """A job's own group is shared by every run, whatever the workflow's group ends in."""
    job = _job(body="    concurrency:\n      group: deploy\n      cancel-in-progress: false\n")
    planted = _planted(_landing_workflow(group=_PER_REQUEST_GROUP + _PUSH_SUFFIX, cancel=_PULL_REQUESTS_ONLY, job=job))
    assert landed_head_violations(planted) == [
        "planted.yml: probe holds a concurrency group a later landed head's run would contend for"
    ]


def test_the_landed_head_rule_accepts_the_isolated_gate_and_leaves_the_release_branch_to_its_own_contract() -> None:
    """The positive control, and the boundary with the release-branch rule."""
    isolated = _landing_workflow(group=_PER_REQUEST_GROUP + _PUSH_SUFFIX, cancel=_PULL_REQUESTS_ONLY)
    assert landed_head_violations(_planted(isolated)) == []
    # The isolated gate still cancels a pull request's superseded run.
    assert superseded_run_violations(_planted(isolated)) == []
    assert landed_head_violations(_planted(_landing_workflow(group=_PER_REQUEST_GROUP, cancel="false"))) == [
        "planted.yml lets the runs of two landed heads share a concurrency group"
    ]
    release = _landing_workflow(group=_PER_REQUEST_GROUP, cancel="true", branch="main")
    assert landed_head_violations(_planted(release)) == []
