"""Worker containment on hosted Linux runners, read from the workflow files themselves.

The runtime launches every profile worker as a transient systemd user service
and refuses with ``runtime_containment_unavailable`` when it cannot drive the
user manager. A GitHub-hosted job runs as ``runner`` outside a login session,
so no ``user@<uid>.service`` and no bus at ``/run/user/<uid>/bus`` exist until
something starts them. Two facts keep the runtime-backed tests from refusing,
and each is pinned here with a planted defect it must report:

- the setup action's containment step starts the user manager, waits for its
  bus and runs one transient user unit under the environment the runtime gives
  its own control calls, and it fails the job when any of that fails;
- every hosted job that runs a test recipe asks the setup action for that step
  before the recipe runs, unless the recipe is named as launching no worker.

The step itself runs only on a Linux runner; nothing here executes it.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

import pytest
import yaml

from cadrumo.core.directory_scan import scan_directory
from dev.paths import REPO_ROOT

from ..lane_recipe_commands import recipes_invoked_by
from ..workflow_run_text import executed_lines
from ..workflow_trust import is_hosted

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_SETUP_ACTION_FILE: Final = REPO_ROOT / ".github" / "actions" / "setup" / "action.yml"
_MERGE_GATE: Final = "merge-gate.yml"
_SETUP_ACTION: Final = "./.github/actions/setup"
_INPUT: Final = "worker-containment"
_STEP_CONDITION: Final = f"inputs.{_INPUT} == 'true'"
_STRICT_SHELL: Final = "set -euo pipefail"

#: The runtime's own launch, reduced to a unit that does nothing: the fixed
#: tool path, a cleared environment holding only the search path and the
#: default runtime directory, and the kill mode every worker unit carries.
_PROBE: Final = (
    'env -i PATH=/usr/bin:/bin XDG_RUNTIME_DIR="/run/user/${uid}" '
    "/usr/bin/systemd-run --user --collect --wait --property=KillMode=control-group /bin/true || refuse"
)
#: What the step must run, in this order, before it may report success.
_REQUIRED_IN_ORDER: Final = (
    ('[ "$RUNNER_OS" = "Linux" ] || refuse', "refuse a runner that is not Linux"),
    ('sudo loginctl enable-linger "$user" || refuse', "enable lingering for the job's user"),
    ('sudo systemctl start "user@${uid}.service" || refuse', "start the user manager"),
    ('[ -S "$bus" ] || refuse', "refuse when the user bus never appears"),
    (_PROBE, "run the transient user unit probe"),
)
_REFUSAL: Final = re.compile(r"^refuse\(\) \{\n(?:.*\n)*?exit 1\n\}$", re.MULTILINE)
_TOLERATED_FAILURE: Final = re.compile(r"\|\|(?!\s*refuse\b)")

#: Test recipes a hosted job may run without the user manager. The plan only
#: deals test files into shards. The CI contracts read workflows, recipes and
#: release metadata and launch no profile worker.
_RECIPES_LAUNCHING_NO_WORKER: Final = frozenset({"test-gate-plan", "test-ci-contracts-gate"})
#: The merge gate jobs whose tests start the runtime today.
_RUNTIME_BACKED_JOBS: Final = frozenset({"goldens", "tests", "harness"})

type _Documents = Sequence[tuple[str, Mapping[str, Any]]]


def _step_violations(action: Mapping[str, Any]) -> list[str]:
    """Report every way the setup action's containment step could pass without proving containment."""
    declared = (action.get("inputs") or {}).get(_INPUT)
    if not isinstance(declared, Mapping):
        return [f"the setup action declares no {_INPUT} input"]
    violations: list[str] = []
    # Off unless asked for: a self-hosted machine keeps state between jobs,
    # and lingering is a lasting change to it.
    if declared.get("default") != "false":
        violations.append(f"the {_INPUT} input is not off by default")
    steps = [
        step for step in (action.get("runs") or {}).get("steps") or [] if f"inputs.{_INPUT}" in str(step.get("if", ""))
    ]
    if len(steps) != 1:
        return [*violations, f"the setup action holds {len(steps)} containment steps, not one"]
    step = steps[0]
    if str(step.get("if", "")).strip() != _STEP_CONDITION:
        violations.append("the containment step can be skipped by more than its own input")
    if "continue-on-error" in step:
        violations.append("the containment step tolerates its own failure")
    lines = executed_lines(step.get("run"))
    script = "\n".join(lines)
    if not lines or lines[0] != _STRICT_SHELL:
        violations.append(f"the containment step does not start with `{_STRICT_SHELL}`")
    if _REFUSAL.search(script) is None:
        violations.append("the containment step's refusal does not exit 1")
    position = 0
    for fragment, purpose in _REQUIRED_IN_ORDER:
        found = script.find(fragment, position)
        if found < 0:
            violations.append(f"the containment step does not {purpose}, in order")
            continue
        position = found + len(fragment)
    if _TOLERATED_FAILURE.search(script) or "set +e" in script:
        violations.append("the containment step lets a failed command pass")
    # The runtime clears its control calls' environment and reaches the bus at
    # the default path, so a probe that names the bus proves a different launch.
    if "DBUS_SESSION_BUS_ADDRESS" in script:
        violations.append("the containment step names a bus address the runtime ignores")
    return violations


def _requests_containment(step: Mapping[str, Any]) -> bool:
    if step.get("uses") != _SETUP_ACTION:
        return False
    return (step.get("with") or {}).get(_INPUT) in (True, "true")


def _worker_recipes(step: Mapping[str, Any]) -> list[str]:
    return sorted(
        recipe
        for recipe in recipes_invoked_by(str(step.get("run") or ""))
        if recipe.startswith("test-") and recipe not in _RECIPES_LAUNCHING_NO_WORKER
    )


def _request_violations(documents: _Documents) -> list[str]:
    """Report every hosted job that runs a test recipe before containment is proven.

    A self-hosted job is reported for the opposite reason: the step changes
    the machine for good, and that machine's own session holds its user manager.
    """
    violations: list[str] = []
    for name, document in documents:
        for job_name, job in (document.get("jobs") or {}).items():
            steps = job.get("steps") or []
            if not is_hosted(job):
                if any(_requests_containment(step) for step in steps):
                    violations.append(f"{name}: {job_name} enables lingering on a self-hosted runner")
                continue
            proven = False
            for step in steps:
                proven = proven or _requests_containment(step)
                if not proven:
                    violations.extend(
                        f"{name}: {job_name} runs {recipe} before worker containment is proven"
                        for recipe in _worker_recipes(step)
                    )
    return violations


def _live() -> list[tuple[str, dict[str, Any]]]:
    paths = sorted(scan_directory(_WORKFLOWS_DIR, pattern="*.yml"))
    assert len(paths) >= 7, f"only {len(paths)} workflow(s) were walked"
    return [(path.name, yaml.safe_load(path.read_text(encoding="utf-8"))) for path in paths]


def _action() -> dict[str, Any]:
    return yaml.safe_load(_SETUP_ACTION_FILE.read_text(encoding="utf-8"))


def _containment_step(action: dict[str, Any]) -> dict[str, Any]:
    (step,) = [step for step in action["runs"]["steps"] if f"inputs.{_INPUT}" in str(step.get("if", ""))]
    return step


# --- the live files -----------------------------------------------------------


def test_the_setup_action_proves_worker_containment_or_fails_the_job() -> None:
    assert _step_violations(_action()) == []


def test_containment_is_proven_before_anything_else_is_set_up() -> None:
    """A job that cannot contain a worker says so before it spends minutes on the toolchain."""
    action = _action()
    assert action["runs"]["steps"][0] is _containment_step(action)


def test_every_hosted_job_that_starts_the_runtime_proves_containment_first() -> None:
    documents = _live()
    assert _request_violations(documents) == []
    # Anchor: the rule reads real test recipes, and the jobs known to start
    # the runtime are the ones that ask.
    merge_gate = dict(documents)[_MERGE_GATE]
    asking = {
        job_name
        for job_name, job in merge_gate["jobs"].items()
        if any(_requests_containment(step) for step in job.get("steps") or [])
    }
    assert asking == _RUNTIME_BACKED_JOBS
    judged = {
        recipe
        for job in merge_gate["jobs"].values()
        for step in job.get("steps") or []
        for recipe in _worker_recipes(step)
    }
    assert judged == {"test-gate-shard", "test-pytest-harness", "test-sequence-goldens-gate"}


# --- teeth --------------------------------------------------------------------


def _with_script(replace: tuple[str, str]) -> dict[str, Any]:
    action = copy.deepcopy(_action())
    step = _containment_step(action)
    old, new = replace
    assert str(step["run"]).count(old) == 1, f"mutation anchor is not unique: {old!r}"
    step["run"] = str(step["run"]).replace(old, new)
    return action


@pytest.mark.parametrize(
    ("replace", "expected"),
    [
        (("set -euo pipefail\n", ""), "the containment step does not start with `set -euo pipefail`"),
        ((' || refuse "loginctl', ' || echo "loginctl'), "the containment step does not enable lingering"),
        (("sudo systemctl start", "systemctl --user start"), "the containment step does not start the user manager"),
        (('[ -S "$bus" ] || refuse', '[ -S "$bus" ] || echo'), "does not refuse when the user bus never appears"),
        (("--wait ", ""), "the containment step does not run the transient user unit probe"),
        (("env -i PATH=/usr/bin:/bin ", ""), "the containment step does not run the transient user unit probe"),
        (("/bin/true || refuse", "/bin/true || true #"), "the containment step does not run the transient user unit"),
        (("exit 1\n", "return 0\n"), "the containment step's refusal does not exit 1"),
        (('[ "$RUNNER_OS" = "Linux" ] || refuse', '[ "$RUNNER_OS" = "Linux" ] || exit 0 #'), "not Linux"),
        (("env -i PATH", "DBUS_SESSION_BUS_ADDRESS=unix:path=$bus env -i PATH"), "names a bus address"),
    ],
)
def test_the_step_rule_reports_each_way_the_probe_could_pass_without_proof(
    replace: tuple[str, str], expected: str
) -> None:
    violations = _step_violations(_with_script(replace))
    assert any(expected in violation for violation in violations), violations


def test_the_step_rule_reports_a_tolerated_failure() -> None:
    swallowed = _with_script(("sleep 0.1\n", "sleep 0.1 || true\n"))
    assert _step_violations(swallowed) == ["the containment step lets a failed command pass"]


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("continue-on-error", True, "the containment step tolerates its own failure"),
        (
            "if",
            f"{_STEP_CONDITION} && runner.os == 'Linux'",
            "the containment step can be skipped by more than its own",
        ),
        ("if", f"{_STEP_CONDITION} && !cancelled()", "the containment step can be skipped by more than its own input"),
    ],
)
def test_the_step_rule_reports_a_step_that_may_be_skipped_or_ignored(key: str, value: object, expected: str) -> None:
    action = copy.deepcopy(_action())
    _containment_step(action)[key] = value
    assert [violation for violation in _step_violations(action) if expected in violation] != []


def test_the_step_rule_reports_a_missing_step_a_missing_input_and_a_default_that_is_on() -> None:
    removed = copy.deepcopy(_action())
    removed["runs"]["steps"].remove(_containment_step(removed))
    assert _step_violations(removed) == ["the setup action holds 0 containment steps, not one"]
    undeclared = copy.deepcopy(_action())
    del undeclared["inputs"][_INPUT]
    assert _step_violations(undeclared) == [f"the setup action declares no {_INPUT} input"]
    on = copy.deepcopy(_action())
    on["inputs"][_INPUT]["default"] = "true"
    assert _step_violations(on) == [f"the {_INPUT} input is not off by default"]


def _planted(job: str) -> list[tuple[str, dict[str, Any]]]:
    return [("planted.yml", yaml.safe_load("name: Cadrumo Planted\non: push\njobs:\n" + job))]


def _job(
    *, runs_on: str = "ubuntu-24.04", setup: str | None = "after-nothing", recipe: str = "test-gate-shard 1/8"
) -> str:
    asked = f'      - uses: {_SETUP_ACTION}\n        with:\n          {_INPUT}: "true"\n'
    bare = f"      - uses: {_SETUP_ACTION}\n"
    run = f"      - run: just {recipe}\n"
    steps = {"after-nothing": asked + run, "after-tests": run + asked, "unasked": bare + run, None: run}[setup]
    return f"  probe:\n    runs-on: {runs_on}\n    steps:\n{steps}"


@pytest.mark.parametrize("setup", ["after-tests", "unasked", None])
def test_the_request_rule_reports_a_hosted_test_job_without_containment_first(setup: str | None) -> None:
    """Asked for too late, not asked for, and no setup at all."""
    assert _request_violations(_planted(_job(setup=setup))) == [
        "planted.yml: probe runs test-gate-shard before worker containment is proven"
    ]


def test_the_request_rule_reads_a_recipe_it_has_never_seen_as_starting_the_runtime() -> None:
    """A new test recipe on a hosted runner must ask, or be named as launching no worker."""
    assert _request_violations(_planted(_job(setup="unasked", recipe="test-anything-new"))) == [
        "planted.yml: probe runs test-anything-new before worker containment is proven"
    ]


def test_the_request_rule_accepts_an_asking_job_an_exempt_recipe_and_a_job_that_runs_no_test() -> None:
    """The positive control: the rule is not satisfied only by reporting everything."""
    assert _request_violations(_planted(_job())) == []
    for recipe in sorted(_RECIPES_LAUNCHING_NO_WORKER):
        assert _request_violations(_planted(_job(setup="unasked", recipe=recipe))) == []
    assert _request_violations(_planted(_job(setup="unasked", recipe="check-style"))) == []
    # A recipe named only in a comment runs nothing.
    commented = (
        "  probe:\n    runs-on: ubuntu-24.04\n    steps:\n"
        "      - run: |\n          # just test-gate-shard\n          echo\n"
    )
    assert _request_violations(_planted(commented)) == []


def test_the_request_rule_reports_lingering_enabled_on_a_self_hosted_runner() -> None:
    assert _request_violations(_planted(_job(runs_on="[self-hosted, Linux, X64]"))) == [
        "planted.yml: probe enables lingering on a self-hosted runner"
    ]
    # A self-hosted job that does not ask is left to its machine's own session.
    assert _request_violations(_planted(_job(runs_on="[self-hosted, Linux, X64]", setup="unasked"))) == []
