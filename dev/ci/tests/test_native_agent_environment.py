"""The Windows contracts job gives the agent-service tests the agent they start.

The tests that start the real cadrumo-agent are Windows-only and are selected
by ``just test-windows`` alone. They fail, and do not skip, without a synced
agent checkout and without a root that no Git checkout contains. The job that
runs the recipe is pinned here with planted defects:

- the checkout is the Windows runner's own, from the repository variable the
  package job already reads, and a blank variable is refused before the tests;
- the agent's test roots sit under the runner's temporary directory, never
  under the workspace, which is a Git checkout.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

import pytest
import yaml

from dev.paths import REPO_ROOT

from ..lane_recipe_commands import recipes_invoked_by

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NATIVE: Final = REPO_ROOT / ".github" / "workflows" / "native.yml"
_RECIPE: Final = "test-windows"
_CHECKOUT: Final = "CADRUMO_DEV_AGENT_CHECKOUT"
_HOSTED_ROOT: Final = "CADRUMO_DEV_AGENT_HOSTED_ROOT"
_RUNNER_CHECKOUT: Final = "${{ vars.CADRUMO_PACKAGE_AGENT_SOURCE_DIR_WINDOWS }}"
_RUNNER_TEMP: Final = "${{ runner.temp }}/"
_AGENT_TESTS: Final = REPO_ROOT / "src" / "cadrumo_agent_service" / "host" / "tests"


def _refuses_a_blank_checkout(step: Mapping[str, Any]) -> bool:
    script = str(step.get("run") or "")
    return f"IsNullOrWhiteSpace($env:{_CHECKOUT})" in script and "throw " in script


def _agent_environment_violations(document: Mapping[str, Any]) -> list[str]:
    """Report every way a job that runs the Windows contracts could start them without their agent."""
    violations: list[str] = []
    for job_name, job in (document.get("jobs") or {}).items():
        steps = job.get("steps") or []
        for index, step in enumerate(steps):
            if _RECIPE not in recipes_invoked_by(str(step.get("run") or "")):
                continue
            environment = {**(job.get("env") or {}), **(step.get("env") or {})}
            if environment.get(_CHECKOUT) != _RUNNER_CHECKOUT:
                violations.append(f"{job_name} does not start the agent from the Windows runner's own checkout")
            hosted_root = str(environment.get(_HOSTED_ROOT, ""))
            if not hosted_root.startswith(_RUNNER_TEMP) or not hosted_root.removeprefix(_RUNNER_TEMP).strip("/"):
                violations.append(
                    f"{job_name} does not keep the agent's test roots under the runner's temporary directory"
                )
            if not any(_refuses_a_blank_checkout(earlier) for earlier in steps[:index]):
                violations.append(f"{job_name} starts the contracts without refusing a blank agent-source variable")
    return violations


def _live() -> dict[str, Any]:
    return yaml.safe_load(_NATIVE.read_text(encoding="utf-8"))


def _contracts_step(document: dict[str, Any]) -> dict[str, Any]:
    steps = document["jobs"]["windows-contracts"]["steps"]
    return next(step for step in steps if _RECIPE in recipes_invoked_by(str(step.get("run") or "")))


def test_the_windows_contracts_job_gives_the_agent_tests_their_checkout_and_root() -> None:
    document = _live()
    assert _agent_environment_violations(document) == []
    # Anchor: the rule judges the one job that runs the Windows-only contracts.
    judged = [
        name
        for name, job in document["jobs"].items()
        if any(_RECIPE in recipes_invoked_by(str(step.get("run") or "")) for step in job.get("steps") or [])
    ]
    assert judged == ["windows-contracts"]


def test_the_two_names_are_the_ones_the_agent_fixtures_read() -> None:
    """Independent of the workflow: a renamed variable in the fixtures would leave the job setting nothing."""
    assert f'"{_HOSTED_ROOT}"' in (_AGENT_TESTS / "conftest.py").read_text(encoding="utf-8")
    assert f'"{_CHECKOUT}"' in (_AGENT_TESTS / "agent_checkout_support.py").read_text(encoding="utf-8")


# --- teeth --------------------------------------------------------------------


@pytest.mark.parametrize(
    "checkout",
    [None, "", "${{ vars.CADRUMO_PACKAGE_AGENT_SOURCE_DIR_LINUX }}", "${{ github.workspace }}/cadrumo-agent"],
)
def test_the_rule_reports_a_job_that_names_no_or_another_checkout(checkout: str | None) -> None:
    document = _live()
    environment = document["jobs"]["windows-contracts"]["env"]
    if checkout is None:
        del environment[_CHECKOUT]
    else:
        environment[_CHECKOUT] = checkout
    assert _agent_environment_violations(document) == [
        "windows-contracts does not start the agent from the Windows runner's own checkout"
    ]


@pytest.mark.parametrize(
    "hosted_root",
    [None, "", "${{ runner.temp }}/", "${{ github.workspace }}/.tmp/agent", ".tmp/agent"],
)
def test_the_rule_reports_test_roots_that_could_lie_inside_a_checkout(hosted_root: str | None) -> None:
    document = _live()
    environment = _contracts_step(document)["env"]
    if hosted_root is None:
        del environment[_HOSTED_ROOT]
    else:
        environment[_HOSTED_ROOT] = hosted_root
    assert _agent_environment_violations(document) == [
        "windows-contracts does not keep the agent's test roots under the runner's temporary directory"
    ]


def test_the_rule_reports_a_missing_and_a_late_refusal_of_a_blank_variable() -> None:
    def refusal(document: dict[str, Any]) -> dict[str, Any]:
        return next(step for step in document["jobs"]["windows-contracts"]["steps"] if _refuses_a_blank_checkout(step))

    expected = ["windows-contracts starts the contracts without refusing a blank agent-source variable"]

    removed = _live()
    removed["jobs"]["windows-contracts"]["steps"].remove(refusal(removed))
    assert _agent_environment_violations(removed) == expected

    late = _live()
    steps = late["jobs"]["windows-contracts"]["steps"]
    steps.append(steps.pop(steps.index(refusal(late))))
    assert _agent_environment_violations(late) == expected
