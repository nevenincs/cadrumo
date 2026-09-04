"""A packaged tool invoked as a script cannot import its own package.

`python3 dev/ci/runner_queue_watchdog.py` sets `__package__` to None, so a
module-level `from .._paths import ...` raises

    ImportError: attempted relative import with no known parent package

before the tool's first line of real work. The tool then fails identically on
every run, for a reason that has nothing to do with what it checks.

This is not hypothetical. `runner_queue_watchdog` was invoked as a script from
FIVE workflows - packaging-quick, packaging-homebrew, packaging-scoop,
packaging-smoke, and runner-fleet-health - and had therefore never once
executed. Its job is to fail a lane
fast when no online runner can serve it, and its step is named "Fail fast on a
lane no online runner can serve", so its failures read as the watchdog DOING its
job. During a real runner outage on 2026-08-31 it produced exactly that
misreading: the lane looked correctly guarded and was not guarded at all.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: `run:` lines invoking a repo-relative .py file directly, e.g.
#: `python3 dev/ci/runner_queue_watchdog.py`. The `-m` form is not matched
#: because it carries no path.
_SCRIPT_CALL = re.compile(r"python3?\s+((?:dev|packaging|src)/[\w/]+\.py)")

#: A module-level relative import. Indented forms are deliberately excluded:
#: an import inside a function or a `sys.path`-adjusted block does not fail at
#: module load, and several tools legitimately do that.
_MODULE_LEVEL_RELATIVE_IMPORT = re.compile(r"^from\s+\.", re.MULTILINE)

#: A module that assigns its own `__package__` has deliberately made itself
#: runnable as a script, and its relative imports resolve. `smoke_homebrew`
#: does exactly this, with a `sys.path` insert beside it, and forcing it to
#: `-m` would be churn on working code. Excluding it here keeps this guard
#: pointed at the real defect - a package-relative module with no such shim,
#: invoked in a way that cannot import it.
_SELF_PACKAGING_SHIM = re.compile(r"^\s*__package__\s*=", re.MULTILINE)


def _workflow_files() -> list[Path]:
    return sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))


def _script_invocation_offenders(workflows: list[Path], *, repo_root: Path) -> list[str]:
    """Return workflow calls that execute a relative-importing file directly."""
    offenders: list[str] = []
    for workflow in workflows:
        for match in _SCRIPT_CALL.finditer(workflow.read_text(encoding="utf-8")):
            target = repo_root / match.group(1)
            if not target.is_file():
                continue
            source = target.read_text(encoding="utf-8")
            if _SELF_PACKAGING_SHIM.search(source):
                continue
            if _MODULE_LEVEL_RELATIVE_IMPORT.search(source):
                dotted = match.group(1).removesuffix(".py").replace("/", ".")
                offenders.append(f"{workflow.name} runs {match.group(1)} as a script; use `python3 -m {dotted}`")
    return offenders


def test_no_workflow_runs_a_relative_importing_module_as_a_script() -> None:
    """Every call site of a package-relative tool must use `python -m`.

    Checks the two halves against each other rather than either alone: a script
    invocation is fine for a standalone file, and a relative import is fine in a
    module someone runs with `-m`. Only the COMBINATION is broken, and only the
    combination is reported - so this refuses the real defect without forbidding
    either practice on its own.
    """
    offenders = _script_invocation_offenders(_workflow_files(), repo_root=REPO_ROOT)
    assert not offenders, "packaged tool(s) invoked as scripts:\n  " + "\n  ".join(offenders)


def test_compatibility_workflow_uses_module_entry_points() -> None:
    """Inventory, probe, and cohort tools run with package context intact."""
    workflow = REPO_ROOT / ".github" / "workflows" / "python-runtime-compatibility.yml"
    surface = workflow.read_text(encoding="utf-8")
    for module in (
        "dev.ci.python_runtime_matrix",
        "dev.ci.python_runtime_compatibility",
        "dev.packaging.release_cohort",
    ):
        assert f"uv run --no-sync python -m {module}" in surface
    assert re.search(r"\bpython3?\s+(?:dev|packaging|src)/[\w/]+\.py", surface) is None


def test_direct_script_detector_has_detector_teeth(tmp_path: Path) -> None:
    """An isolated relative-importing tool called by path is rejected."""
    tool = tmp_path / "dev" / "ci" / "offender.py"
    tool.parent.mkdir(parents=True)
    tool.write_text("from .._paths import REPO_ROOT\n", encoding="utf-8")
    workflow = tmp_path / "offender.yml"
    workflow.write_text(
        "name: offender\n"
        "on: [workflow_dispatch]\n"
        "jobs:\n"
        "  run:\n"
        "    runs-on: [self-hosted, Linux, X64]\n"
        "    steps:\n"
        "      - run: python3 dev/ci/offender.py\n",
        encoding="utf-8",
    )

    offenders = _script_invocation_offenders([workflow], repo_root=tmp_path)
    assert offenders and "offender.py" in offenders[0]


def test_the_watchdog_is_importable_as_a_module() -> None:
    """The specific tool this guard was written for stays importable.

    Import, not invoke: the tool talks to the Actions API and reads environment
    the test does not have. What must hold is that its module-level imports
    resolve, which is the exact thing script invocation broke.
    """
    module = pytest.importorskip("dev.ci.runner_queue_watchdog")

    assert module.__package__ == "dev.ci", "the watchdog must resolve as part of its package"
