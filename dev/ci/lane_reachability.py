"""Analyse declared and CI-invoked lane coverage without silently dropping test populations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from dev._paths import UTF_8

from .lane_configuration import configured_marker_expression, configured_testpaths
from .lane_contracts import DirectoryCoverageReport, Lane, ReachabilityReport, UnreachableTest
from .lane_marker_inventory import expression_selects, marker_sets_in, tracked_test_directories, tracked_test_files
from .lane_recipe_commands import _justfile_lanes, _pytest_invocations, resolved_justfile_text
from .lane_workflow_graph import (
    _WORKFLOW_DIR,
    _workflow_run_steps,
    ci_invoked_recipe_opt_in,
    ci_invoked_recipe_triggers,
    ci_invoked_recipes,
    workflow_triggers,
)


def ci_invoked_lanes(root: Path) -> tuple[Lane, ...]:
    """Return only the lanes CI actually runs.

    The distinction this draws is the whole point. :func:`declared_lanes`
    answers "does the repository declare a lane for this test", and a justfile
    recipe counts — which is correct for its question and dangerously
    reassuring for the one a reader usually means. Two lanes proved that:
    ``just test-integration`` (370 integration-marked modules under ``src/``)
    and ``just test-tooling`` (the canonical ``dev/`` subject aggregate, including the
    deploy-authority tests) were both declared, both healthy, and invoked by no
    workflow at all, so the declared-lane gate reported full coverage over
    tests CI had never once run.

    Every returned lane carries the events that reach it, so a caller can ask
    the weaker-guarantee question underneath: an invoked lane whose every route
    is ``workflow_dispatch`` is wired but fires on no push, and its failure
    cannot fail anything until a person goes looking. See
    :attr:`Lane.is_manual_only`.
    """
    invoked = ci_invoked_recipes(root)
    return tuple(lane for lane in declared_lanes(root) if lane.recipe is None or lane.recipe in invoked)


def declared_lanes(root: Path) -> tuple[Lane, ...]:
    """Return every lane declared by config, recipes, and workflows.

    Triggers are attached HERE rather than only in :func:`ci_invoked_lanes`,
    which keeps the invoked set a strict subset of the declared set -- the
    invariant that says the two models differ by a filter and not by content.
    Attaching them downstream instead made every recipe lane compare unequal
    between the two functions, so the invoked set stopped being a subset at all
    while both models were individually correct. A recipe no workflow reaches
    carries an empty trigger tuple, which is the honest reading: no workflow
    event reaches it, so neither :attr:`Lane.runs_on_change` nor
    :attr:`Lane.is_manual_only` claims anything about it.
    """
    testpaths = configured_testpaths(root)
    recipe_triggers = ci_invoked_recipe_triggers(root)
    default_expression = configured_marker_expression(root)
    lanes: list[Lane] = []

    text = resolved_justfile_text(root)
    if text:
        lanes.extend(_justfile_lanes(text, default_paths=testpaths))

    workflow_dir = root / _WORKFLOW_DIR
    if workflow_dir.is_dir():
        effective = workflow_triggers(root)
        for workflow in scan_directory(workflow_dir, pattern="*.yml"):
            text = workflow.read_text(encoding=UTF_8)
            events = effective.get(f"{_WORKFLOW_DIR}/{workflow.name}", ())
            # Per RUN STEP, not per file: an inline invocation inherits the
            # reach of the job holding it, and reading the whole workflow text
            # would hand a gated job the events that start the run without it.
            for step in _workflow_run_steps(text, events):
                lanes.extend(
                    replace(lane, triggers=step.events, opt_in=step.opt_in)
                    for lane in _pytest_invocations(
                        step.command,
                        source=f"{_WORKFLOW_DIR}/{workflow.name}",
                        default_paths=testpaths,
                    )
                )

    # A pathless invocation inherits both testpaths and the addopts expression.
    opt_in_recipes = ci_invoked_recipe_opt_in(root)
    resolved: list[Lane] = []
    for lane in lanes:
        expression = lane.marker_expression if lane.marker_expression is not None else default_expression
        triggers = lane.triggers if lane.recipe is None else recipe_triggers.get(lane.recipe, ())
        opt_in = lane.opt_in if lane.recipe is None else lane.recipe in opt_in_recipes
        resolved.append(replace(lane, marker_expression=expression, triggers=triggers, opt_in=opt_in))
    return tuple(resolved)


@dataclass
class _ReachabilityCensus:
    """Retain path coverage, parse refusals, and per-test marker findings together."""

    unreachable: list[UnreachableTest]
    unnamed: list[str]
    skipped: list[str]
    analysed: int = 0


def analyse_reachability(
    root: Path,
    *,
    lanes: Iterable[Lane] | None = None,
    files: Iterable[Path] | None = None,
) -> ReachabilityReport:
    """Return every test no declared lane can select, with its corpus size.

    Args:
        root: The repository root the lanes and paths are relative to.
        lanes: Declared lanes; read from ``root`` when omitted.
        files: Repository-relative test modules; working-tree discovery when
            omitted. Injectable so the anti-tautology proofs can drive an
            isolated synthetic tree instead.

    Returns:
        The census.unreachable tests, the number of files successfully census.analysed, and
        the discovered files that could not be read.
    """
    resolved = tuple(lanes) if lanes is not None else declared_lanes(root)
    candidates = tuple(files) if files is not None else tracked_test_files(root)

    census = _ReachabilityCensus([], [], [])

    for path in candidates:
        _analyse_test_path(path, root, resolved, census)

    return ReachabilityReport(
        unreachable=tuple(census.unreachable),
        unnamed=tuple(census.unnamed),
        analysed=census.analysed,
        skipped=tuple(census.skipped),
    )


def analyse_directory_coverage(
    root: Path,
    *,
    lanes: Iterable[Lane] | None = None,
    directories: Iterable[str] | None = None,
) -> DirectoryCoverageReport:
    """Return every test directory no declared lane's path scope sweeps.

    Both sides are derived, neither is restated. The lane scopes come from
    :func:`declared_lanes`, which resolves the justfile through ``just`` itself
    and reads the workflows, so a lane added or narrowed anywhere moves this
    without a second edit. The directory set comes from the discovered tree. A
    hand-maintained list on either side would reproduce the defect the gate
    exists to catch, one level up.

    Args:
        root: The repository root the lanes and directories are relative to.
        lanes: Declared lanes; read from ``root`` when omitted.
        directories: Repository-relative test directories; working-tree
            discovery when omitted. Injectable so the detector proofs can drive
            an isolated synthetic tree instead.

    Returns:
        The unswept directories and the corpus size they were measured against.
    """
    resolved_lanes = tuple(lanes) if lanes is not None else declared_lanes(root)
    candidates = tuple(directories) if directories is not None else tracked_test_directories(root)

    def swept(directory: str) -> bool:
        return any(lane.covers_directory(directory) for lane in resolved_lanes)

    uncovered = tuple(sorted(name for name in candidates if not swept(name)))

    return DirectoryCoverageReport(uncovered=uncovered, analysed=len(candidates))


def _analyse_test_path(path: Path, root: Path, resolved: tuple[Lane, ...], census: _ReachabilityCensus) -> None:
    """Analyse test path."""
    relative = (path.relative_to(root) if path.is_absolute() else path).as_posix()
    covering = [lane for lane in resolved if lane.covers(relative)]

    # The path-level question, asked BEFORE the file is read so it still
    # holds for the two inputs the per-test model is blind to: a module with
    # no test functions, and a discovered file that disappears before it can
    # be read. Both classes are empty today; neither is impossible.
    if not covering:
        census.unnamed.append(relative)

    tests = marker_sets_in(root / relative)
    if tests is None:
        census.skipped.append(relative)
        return
    census.analysed += 1
    for entry in tests:
        if not any(expression_selects(lane.marker_expression, entry.markers) for lane in covering):
            census.unreachable.append(UnreachableTest(path=relative, test=entry.test, markers=entry.markers))
