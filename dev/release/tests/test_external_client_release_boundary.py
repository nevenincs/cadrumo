"""Regression gates for the base-CLI/harness dependency direction.

The harness ships inside the product wheel rather than as its own distribution,
so the direction is no longer expressed by a dependency declaration between two
projects. It is expressed by the import graph within one package, which is what
these gates read.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest
import yaml

from ..._paths import REPO_ROOT
from ...ci.workflow_run_text import executed_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BASE_PACKAGE = REPO_ROOT / "src" / "cadrumo"
_HARNESS_PACKAGE = REPO_ROOT / "src" / "cadrumo_harness"

_HARNESS_EVAL_WORKFLOW = REPO_ROOT / ".github/workflows/agent-harness-eval.yml"


#: Trigger events that fire without a person choosing to run the lane. A lane
#: whose only trigger is `workflow_dispatch` is run by nobody.
_AUTOMATIC_TRIGGERS: Final = frozenset({"push", "pull_request", "schedule", "merge_group"})


def _assert_lane_is_an_assurance_surface(path: Path, *, invocation: str) -> None:
    """Refuse a lane that nothing fires, nothing runs, or nothing can fail.

    A workflow file at a path is not assurance. Three properties make it
    assurance, and a lane that loses any one of them still parses, still sits
    where a presence check looks for it, and still reports nothing: an
    automatic trigger, a step that actually invokes the surface, and the
    absence of `continue-on-error` on that step and the job carrying it.

    The invocation is looked for in what the step EXECUTES, not in its text. A
    commented-out invocation is prose: it satisfies a substring reading of the
    `run:` block while the shell runs nothing, which is the exact shape that
    turns this gate back into the presence check it was written to replace.
    """
    assert path.is_file(), f"{path.name} is missing; the lane it names does not exist"

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict), (
        f"{path.name} does not parse as a workflow mapping; a file GitHub cannot read is a lane "
        "that never runs, and it occupies the path a presence check is satisfied by"
    )

    # `on:` is the YAML 1.1 boolean `True` once parsed, and may be a bare string,
    # a sequence, or a mapping of event names to filters.
    declared = document[True] if True in document else document.get("on")
    triggers = {declared} if isinstance(declared, str) else set(declared or ())
    assert _AUTOMATIC_TRIGGERS & triggers, (
        f"{path.name} declares only {sorted(triggers)}; a lane nothing fires automatically is "
        "run by nobody, and its green is the green of a lane that never ran"
    )

    jobs = document.get("jobs") or {}
    assert jobs, f"{path.name} declares no job; nothing about the lane can run"
    invoking = [
        (job_name, job, step)
        for job_name, job in jobs.items()
        for step in (job.get("steps") or ())
        if invocation in executed_text(step.get("run"))
    ]
    assert invoking, (
        f"no step across the {len(jobs)} job(s) in {path.name} invokes {invocation!r}; the lane "
        "exists but exercises nothing"
    )

    for job_name, job, step in invoking:
        where = f"{path.name}:{job_name}:{step.get('name', '<unnamed>')}"
        assert job.get("continue-on-error") is not True, f"{where} sits in a job that cannot fail"
        assert step.get("continue-on-error") is not True, f"{where} cannot fail the lane"


def _import_targets(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            targets.append(node.module)
    return tuple(targets)


#: Below this the base-package walk has stopped covering the shipped surface.
#: A floor, not a pinned count: 5,854 modules ship today.
_MINIMUM_BASE_MODULES = 500


def test_base_cli_never_imports_the_harness() -> None:
    """The shipped base package has no dependency edge to its harness client.

    Guarded like its positive sibling below, which already refuses when the
    harness imports nothing. A negative claim needs the same protection more,
    not less: an empty walk produces no crossings and reads exactly like a
    clean boundary.
    """
    assert _BASE_PACKAGE.is_dir(), (
        f"no base package at {_BASE_PACKAGE}; a relocated root walks nothing and this gate "
        "would report the release boundary intact"
    )

    walked = tuple(_BASE_PACKAGE.rglob("*.py"))

    assert len(walked) >= _MINIMUM_BASE_MODULES, (
        f"only {len(walked)} base module(s) were walked; below this an empty crossing set "
        "says nothing about whether the shipped package reaches its harness"
    )

    crossings = {
        path.relative_to(REPO_ROOT): target
        for path in walked
        for target in _import_targets(path)
        if target == "cadrumo_harness" or target.startswith("cadrumo_harness.")
    }
    assert not crossings


def test_the_harness_reaches_the_base_cli_through_its_command_api() -> None:
    """The harness depends inward, and through the boundary meant to carry it.

    Both halves matter. Importing nothing from the base package would mean the
    harness had grown its own copy of the command surface; importing it through
    some module other than the command API would mean the boundary had been
    bypassed rather than used.
    """
    production_imports = {
        target
        for path in _HARNESS_PACKAGE.rglob("*.py")
        if "tests" not in path.parts
        for target in _import_targets(path)
        if target == "cadrumo" or target.startswith("cadrumo.")
    }

    assert production_imports, "the harness imports nothing from the base package"
    assert "cadrumo.entrypoints.cli.command_api" in production_imports


def test_the_harness_evaluation_lane_is_an_assurance_surface() -> None:
    """The lane its sibling names must be able to run and able to fail.

    That sibling asserted only that the file existed. Strip the automatic
    trigger, drop the step that runs the eval, or mark it `continue-on-error`,
    and the harness ships unverified while a presence check stays green.
    """
    _assert_lane_is_an_assurance_surface(_HARNESS_EVAL_WORKFLOW, invocation="src/cadrumo_harness")


def test_the_assurance_gate_reads_what_the_lane_executes(tmp_path: Path) -> None:
    """Teeth, against a copy: prose naming the surface is not the lane running it.

    Built by commenting out the real workflow's eval command rather than by
    inventing a document, so the degraded lane keeps its automatic trigger, its
    job, and its step -- everything a presence check looks at -- and differs
    only in whether the shell executes the line. The undegraded round trip is
    asserted first, so a refusal below is attributable to the comment rather
    than to the rewrite.
    """
    document = yaml.safe_load(_HARNESS_EVAL_WORKFLOW.read_text(encoding="utf-8"))
    intact = tmp_path / "intact.yml"
    intact.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    _assert_lane_is_an_assurance_surface(intact, invocation="src/cadrumo_harness")

    steps = document["jobs"]["agent-harness-eval"]["steps"]
    invoking = next(step for step in steps if "src/cadrumo_harness" in str(step.get("run", "")))
    newline = chr(10)
    invoking["run"] = "# " + str(invoking["run"]).replace(newline, newline + "# ")
    commented = tmp_path / "commented.yml"
    commented.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    # The reading this gate used to make is still satisfied by the degraded lane.
    assert "src/cadrumo_harness" in str(invoking["run"])

    with pytest.raises(AssertionError, match="exercises nothing"):
        _assert_lane_is_an_assurance_surface(commented, invocation="src/cadrumo_harness")


def test_the_harness_evaluation_lane_stays_separate_from_the_release_path() -> None:
    """The harness keeps its own assurance lane and does not ride the release one.

    It ships in the product wheel now, so nothing structural stops its suite
    being folded into the publish path. Keeping it separate is what stops a
    harness failure blocking a product release, and the reverse.
    """
    assert _HARNESS_EVAL_WORKFLOW.is_file()

    publish = (REPO_ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "cadrumo_harness" not in publish, "the publish path runs harness-specific work"
