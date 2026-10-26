"""Propagate effective workflow events and opt-in gates over actual recipe routes."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

import yaml

from cadrumo.core.directory_scan import scan_directory
from dev._paths import UTF_8

from .lane_recipe_commands import _parameterless_recipes, _recipe_bodies, _recipe_closure
from .workflow_job_gates import job_gate, narrowed_events

#: Where lane declarations live. Anything else is not a lane.
_WORKFLOW_DIR: Final[str] = ".github/workflows"


#: A `gh workflow run <file>.yml` call in a workflow `run:` block. This is a
#: real edge between workflows: a dispatch-only workflow can still be reached
#: automatically by another workflow pressing its button. Missing the edge
#: over-reports the target as manual-only, which is the exact error this whole
#: trigger model exists to avoid making in the other direction.
_GH_WORKFLOW_RUN: Final = re.compile(r"\bgh\s+workflow\s+run\s+(?P<workflow>[\w.-]+\.ya?ml)")


#: A job-level `uses: ./.github/workflows/<file>.yml`, the other edge between
#: workflows: the called workflow runs whenever the calling job does.
_LOCAL_WORKFLOW_CALL: Final = re.compile(r"\./\.github/workflows/(?P<workflow>[\w.-]+\.ya?ml)")


@dataclass(frozen=True, slots=True)
class _RunStep:
    """One ``run:`` command with the reach its own job proves, not its workflow's."""

    events: tuple[str, ...]
    opt_in: bool
    condition: str | None
    command: str


def _workflow_run_steps(text: str, events: tuple[str, ...]) -> tuple[_RunStep, ...]:
    """Return every ``run:`` command in a workflow, attributed to its job's reach.

    Read from the parsed document rather than the raw file, for the same reason
    :func:`_pytest_invocations` refuses to treat every ``-m`` as a marker flag:
    the word "just" is ordinary English, and these workflows use it that way in
    step names and comments ("Ensure just is available", "provision just
    natively"). Scanning raw text harvested `is`, `uses`, and `natively` as
    recipe names -- three recipes that do not exist -- which is harmless only
    until one of those words happens to BE a recipe name, at which point an
    unreached lane reads as reached.

    ATTRIBUTION IS PER JOB because reach is. A workflow's ``on:`` block starts
    the run; a job-level ``if:`` decides which jobs the run then executes, and
    handing every job the workflow's whole event set gives a gated lane reach it
    does not have. See :mod:`dev.ci.workflow_job_gates` for what a guard is
    allowed to prove and what it is refused.
    """
    document = yaml.load(text, Loader=yaml.CSafeLoader)
    if not isinstance(document, dict):
        return ()
    steps: list[_RunStep] = []
    for name, job in (document.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        gate = job_gate(document, str(name), events)
        condition = job.get("if")
        for step in job.get("steps") or []:
            if isinstance(step, dict) and "run" in step:
                steps.append(
                    _RunStep(
                        events=gate.events,
                        opt_in=gate.is_opt_in,
                        condition=None if condition is None else str(condition),
                        command=str(step["run"]),
                    ),
                )
    return tuple(steps)


def _dispatch_edges(text: str) -> tuple[tuple[str, str | None], ...]:
    """Return each ``gh workflow run`` target with the guard on the pressing job.

    The guard travels with the edge rather than being applied here, because the
    events on the dispatching side are still growing when this is read: the
    fixpoint in :func:`workflow_triggers` narrows against whatever that side
    holds at the moment it propagates.

    A dispatching job that is additionally OPT-IN (a ``workflow_dispatch`` input
    defaulting false) would press the button only when a person ticks the box,
    so the target's inherited event would be weaker still. No such edge exists
    in this tree, and an unexercised model of one would be a claim rather than a
    measurement, so the edge carries the event narrowing only.
    """
    edges: list[tuple[str, str | None]] = []
    for step in _workflow_run_steps(text, ()):
        for match in _GH_WORKFLOW_RUN.finditer(step.command):
            edges.append((match.group("workflow"), step.condition))
    document = yaml.load(text, Loader=yaml.CSafeLoader)
    jobs = document.get("jobs") if isinstance(document, dict) else None
    for job in (jobs or {}).values():
        # A job calling a reusable workflow of this repository runs it exactly
        # when the calling job runs, under the calling job's guard.
        uses = job.get("uses") if isinstance(job, dict) else None
        if isinstance(uses, str) and (called := _LOCAL_WORKFLOW_CALL.fullmatch(uses)) is not None:
            condition = job.get("if")
            edges.append((called.group("workflow"), None if condition is None else str(condition)))
    return tuple(edges)


def _workflow_events(text: str) -> tuple[str, ...]:
    """Return the event names in a workflow's ``on:`` block.

    ``on`` is a YAML 1.1 boolean, so a safe-loaded workflow carries its trigger
    block under the key ``True`` and NEVER under the string ``"on"``. Reading
    ``document["on"]`` returns nothing for every workflow in this repository,
    which would report each one as fired by no event at all -- and a
    silently-empty trigger set is exactly the state this function exists to
    detect, so the naive spelling would have hidden the finding while looking
    like it made it.
    """
    document = yaml.load(text, Loader=yaml.CSafeLoader)
    if not isinstance(document, dict):
        return ()
    block = document.get("on", document.get(True))
    if isinstance(block, str):
        return (block,)
    if isinstance(block, list):
        return tuple(sorted(str(item) for item in block))
    if isinstance(block, dict):
        return tuple(sorted(str(key) for key in block))
    return ()


def workflow_triggers(root: Path) -> Mapping[str, tuple[str, ...]]:
    """Return each workflow's EFFECTIVE events, keyed by repository-relative path.

    Effective, not declared, and the difference is a whole workflow. A workflow
    whose ``on:`` block is ``workflow_dispatch`` alone still runs on every push
    that another workflow reacts to by pressing its button with
    ``gh workflow run``. Reading only the ``on:`` block reports such a target as
    manual-only, and everything it gates as unreached-in-practice, when a push
    to the paths the dispatching workflow watches runs it every time.

    Events therefore propagate along dispatch edges until nothing new is added.
    A dispatched workflow gains the dispatcher's events because it is reached
    exactly when the dispatcher is; it keeps its own ``workflow_dispatch`` too,
    which remains true. It gains only the events that reach the PRESSING JOB,
    not the dispatcher's whole ``on:`` block: a button pressed from a job that
    a push cannot start is not pressed by that push.
    """
    workflow_dir = root / _WORKFLOW_DIR
    if not workflow_dir.is_dir():
        return MappingProxyType(dict[str, tuple[str, ...]]())

    events: dict[str, set[str]] = {}
    dispatches: dict[str, tuple[tuple[str, str | None], ...]] = {}
    for workflow in scan_directory(workflow_dir, pattern="*.yml"):
        text = workflow.read_text(encoding=UTF_8)
        events[workflow.name] = set(_workflow_events(text))
        dispatches[workflow.name] = _dispatch_edges(text)

    changed = True
    while changed:
        changed = False
        for name, edges in dispatches.items():
            for target, condition in edges:
                if target not in events:
                    # A dispatch of a workflow this directory does not hold is
                    # reported by neither widening nor narrowing anything: an
                    # invented entry would claim a lane source that is not here.
                    continue
                pressed = set(narrowed_events(condition, tuple(sorted(events[name]))))
                if not pressed <= events[target]:
                    events[target] |= pressed
                    changed = True

    return MappingProxyType(
        {f"{_WORKFLOW_DIR}/{name}": tuple(sorted(found)) for name, found in events.items()},
    )


def ci_invoked_recipe_triggers(root: Path) -> Mapping[str, tuple[str, ...]]:
    """Return every CI-invoked recipe mapped to the events that reach it.

    A recipe is CI-invoked when a workflow ``run:`` names it, or when a
    CI-invoked recipe's own body names it. The transitive step matters: the
    recipes workflows call are increasingly thin wrappers, and stopping at the
    first hop would report a delegated lane as unreached.

    Events accumulate along that same closure, per STEP rather than per
    workflow. A recipe reached from two routes carries both event sets, so it
    counts as automatic when EITHER route is -- the union is what keeps a lane
    that a dispatch-only workflow merely also names from reading as manual. But
    the union must be taken over what reaches each invoking JOB, not over the
    workflow's whole ``on:`` block. The case that proved it has since been
    deleted -- a recipe invoked once, from a job guarded to
    ``workflow_dispatch`` inside a workflow that also fires on push, which
    the workflow-level union reported as push-triggered when no push had
    ever run it. The distinction outlives the example.
    """
    justfile = root / "justfile"
    justfile_text = justfile.read_text(encoding=UTF_8) if justfile.exists() else ""
    bodies = _recipe_bodies(justfile_text)
    parameterless = _parameterless_recipes(justfile_text)

    workflow_dir = root / _WORKFLOW_DIR
    if not workflow_dir.is_dir():
        return MappingProxyType(dict[str, tuple[str, ...]]())

    effective = workflow_triggers(root)
    accumulated: dict[str, set[str]] = {}
    for workflow in scan_directory(workflow_dir, pattern="*.yml"):
        text = workflow.read_text(encoding=UTF_8)
        events = effective.get(f"{_WORKFLOW_DIR}/{workflow.name}", ())
        for step in _workflow_run_steps(text, events):
            reached = _recipe_closure(step.command, bodies, parameterless)
            for name in reached:
                accumulated.setdefault(name, set()).update(step.events)
    return MappingProxyType({name: tuple(sorted(events)) for name, events in accumulated.items()})


def ci_invoked_recipe_opt_in(root: Path) -> frozenset[str]:
    """Return the CI-invoked recipes EVERY route to which is behind an opt-in flag.

    A recipe here is wired, and its reaching events are real, and it still does
    not run when one of those events fires: every job that invokes it also
    requires a ``workflow_dispatch`` input whose declared default is falsy, so
    the workflow starts, the job is skipped, and the run is green.

    This is a strictly separate fact from :attr:`Lane.is_manual_only` and must
    not be folded into it. Manual-only says a person has to start the run;
    opt-in says starting the run the ordinary way is still not enough. A lane
    carrying both is reached by nothing a person does by default, which is the
    weakest state short of being invoked by no workflow at all -- and the two
    weakenings are individually documented and jointly unremarked, which is
    exactly why the union has to be computed rather than read.
    """
    justfile = root / "justfile"
    justfile_text = justfile.read_text(encoding=UTF_8) if justfile.exists() else ""
    bodies = _recipe_bodies(justfile_text)
    parameterless = _parameterless_recipes(justfile_text)

    workflow_dir = root / _WORKFLOW_DIR
    if not workflow_dir.is_dir():
        return frozenset[str]()

    routed: dict[str, set[bool]] = {}
    for workflow in scan_directory(workflow_dir, pattern="*.yml"):
        text = workflow.read_text(encoding=UTF_8)
        for step in _workflow_run_steps(text, ()):
            reached = _recipe_closure(step.command, bodies, parameterless)
            for name in reached:
                routed.setdefault(name, set()).add(step.opt_in)
    return frozenset(name for name, states in routed.items() if states == {True})


def ci_invoked_recipes(root: Path) -> frozenset[str]:
    """Return every justfile recipe a workflow reaches, transitively."""
    return frozenset(ci_invoked_recipe_triggers(root))
