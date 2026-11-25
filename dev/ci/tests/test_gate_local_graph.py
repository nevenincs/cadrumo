"""The concurrent gate runs every population the sequential gate runs, once each.

`just gate-local` hands `dev/ci/gate-local.toml` to the gate runner, and
`just gate-local-sequential` keeps the one-after-another composition. The graph
is the only place the concurrent composition is written, so a population it
drops is dropped from the gate with nothing else to say so. These tests read
the real graph with the runner's own loader and the real justfile with `just`
itself and the repository's recipe readers, and prove:

* every node runs a recipe the justfile declares, and the `gate-local` recipe
  reaches exactly the recipes the graph names;
* the schedule respects the ordering and exclusion the populations need;
* the test recipes the graph reaches are those the sequential gate reaches,
  each as often, except the one harness run the sequential gate repeats, and
  the gate's two-node split of the documentation tests selects exactly the
  tests the one documentation pass selects.
"""

from __future__ import annotations

import json
import os
import shlex
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Final

import pytest

from dev.docs.sequence_build_gate import SEQUENCE_CHECK_SKIP_ENV
from dev.docs.sequences.verdict_cache import SEQUENCE_JOBS_ENV
from dev.packaging.command_execution import run_command
from dev.paths import REPO_ROOT, UTF_8
from dev.test_runs.gate_graph import PREREQUISITE_KIND, GateGraph, GateNode, load_gate_graph
from dev.test_runs.gate_schedule import simulate_schedule

from ..lane_contracts import Lane
from ..lane_marker_inventory import expression_selects, marker_sets_in, tracked_test_files
from ..lane_recipe_commands import (
    justfile_lanes,
    parameterless_recipes,
    recipe_bodies,
    recipes_invoked_by,
    resolve_just_executable,
    resolved_justfile_text,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_GRAPH: Final = REPO_ROOT / "dev" / "ci" / "gate-local.toml"
_CONCURRENT_RECIPE: Final = "gate-local"
_SEQUENTIAL_RECIPE: Final = "gate-local-sequential"
_HARNESS_RECIPE: Final = "test-pytest-harness"
_NO_DEPS: Final = "--no-deps"

#: Gate-only recipes that together run one public pass, so the long strict
#: documentation build is in front of one test file rather than all of them.
_DOCS_RECIPE: Final = "docs-check-tests"
_GATE_DOCS_SPLIT: Final = ("_gate-docs-tests", "_gate-docs-strict-build-test")


@cache
def _graph() -> GateGraph:
    return load_gate_graph(_GRAPH)


@cache
def _justfile_text() -> str:
    return (REPO_ROOT / "justfile").read_text(encoding=UTF_8)


@cache
def _dump() -> dict[str, tuple[str, ...]]:
    """Return every recipe `just` declares, mapped to the dependencies `just` itself reads."""
    completed = run_command([resolve_just_executable(), "--dump", "--dump-format", "json"], cwd=REPO_ROOT)
    recipes = json.loads(completed.stdout)["recipes"]
    assert isinstance(recipes, dict)
    return {
        str(name): tuple(str(dependency["recipe"]) for dependency in entry["dependencies"])
        for name, entry in recipes.items()
    }


def _dependencies(recipe: str) -> tuple[str, ...]:
    dependencies = _dump().get(recipe)
    assert dependencies is not None, f"`just` declares no recipe {recipe}"
    return dependencies


@cache
def _test_recipes() -> frozenset[str]:
    """Return every recipe whose own body runs pytest, read by the lane reader."""
    lanes = justfile_lanes(resolved_justfile_text(REPO_ROOT), default_paths=())
    return frozenset(lane.recipe for lane in lanes if lane.recipe is not None)


def _node_recipe(node: GateNode) -> tuple[str, bool]:
    """Return the recipe a node's `just` command runs and whether its dependencies run too."""
    command = list(node.command)
    assert command[0] == "just", f"node {node.name} does not run a just recipe: {command}"
    options = [part for part in command[1:] if part.startswith("-")]
    positional = [part for part in command[1:] if not part.startswith("-")]
    assert set(options) <= {_NO_DEPS}, f"node {node.name} passes an option the readers do not model: {options}"
    assert len(positional) == 1, f"node {node.name} must name exactly one recipe: {command}"
    return positional[0], _NO_DEPS not in options


def _invocation_tests(
    recipe: str, *, with_dependencies: bool = True, callers: frozenset[str] = frozenset()
) -> Counter[str]:
    """Count the test recipes one `just <recipe>` invocation runs.

    Within one invocation `just` runs each dependency once, so dependencies
    close as a set. A `just` call in a body starts a new invocation, so its
    test recipes add up: that is where a repeated population shows.
    """
    assert recipe not in callers, f"recipe calls cycle through {recipe}"
    bodies = recipe_bodies(_justfile_text())
    parameterless = parameterless_recipes(_justfile_text())
    running = {recipe}
    frontier = [recipe] if with_dependencies else []
    while frontier:
        for dependency in _dependencies(frontier.pop()):
            if dependency not in running:
                running.add(dependency)
                frontier.append(dependency)
    counted: Counter[str] = Counter(name for name in running if name in _test_recipes())
    for name in sorted(running):
        for called in sorted(recipes_invoked_by(bodies.get(name, ""), parameterless)):
            counted += _invocation_tests(called, callers=callers | {recipe})
    return counted


def _graph_tests(graph: GateGraph) -> Counter[str]:
    """Count the graph's test recipes, reading the documentation split as the pass it replaces."""
    counted: Counter[str] = Counter()
    for node in graph.nodes:
        recipe, with_dependencies = _node_recipe(node)
        counted += _invocation_tests(recipe, with_dependencies=with_dependencies)
    if all(counted[name] == 1 for name in _GATE_DOCS_SPLIT):
        for name in _GATE_DOCS_SPLIT:
            del counted[name]
        counted[_DOCS_RECIPE] += 1
    return counted


def _lanes_of(recipe: str) -> list[Lane]:
    lanes = [
        lane for lane in justfile_lanes(resolved_justfile_text(REPO_ROOT), default_paths=()) if lane.recipe == recipe
    ]
    assert lanes, f"{recipe} runs no pytest lane"
    return lanes


def _selects(lanes: list[Lane], relative: str, markers: frozenset[str]) -> bool:
    return any(lane.covers(relative) and expression_selects(lane.marker_expression, markers) for lane in lanes)


def _budget() -> int:
    """Return the recipe's default budget, read from `just` with no override in force."""
    environment = {key: value for key, value in os.environ.items() if key != "CADRUMO_GATE_BUDGET"}
    completed = run_command(
        [resolve_just_executable(), "--evaluate", "gate_budget"], cwd=REPO_ROOT, environment=environment
    )
    return int(completed.stdout.strip())


@cache
def _waves() -> dict[str, int]:
    waves = simulate_schedule(_graph(), _budget())
    return {node.name: index for index, wave in enumerate(waves) for node in wave}


def test_every_node_runs_a_declared_recipe() -> None:
    declared = set(_dump())
    for node in _graph().nodes:
        recipe, _ = _node_recipe(node)
        assert recipe in declared, f"node {node.name} runs `just {recipe}`, which the justfile does not declare"


def test_the_gate_recipe_reaches_exactly_the_recipes_of_its_graph() -> None:
    """The reachability reader follows `gate-local` into the graph, and only there."""
    body = recipe_bodies(_justfile_text())[_CONCURRENT_RECIPE]
    named = {_node_recipe(node)[0] for node in _graph().nodes}

    assert recipes_invoked_by(body, parameterless_recipes(_justfile_text())) == named
    assert len(named) == len(_graph().nodes), "two nodes run the same recipe"


def test_the_graph_runs_each_sequential_test_population_once_and_the_harness_once() -> None:
    """The coverage proof: no population lost, none added, the repeated harness run removed."""
    sequential = _invocation_tests(_SEQUENTIAL_RECIPE)
    concurrent = _graph_tests(_graph())

    assert len(sequential) >= 10, f"the sequential gate reached almost no test recipe: {sorted(sequential)}"
    assert sequential[_HARNESS_RECIPE] == 2, "the sequential gate no longer repeats the harness"
    assert concurrent - sequential == Counter(), "the graph runs test populations the sequential gate does not"
    assert sequential - concurrent == Counter({_HARNESS_RECIPE: 1})
    assert set(concurrent.values()) == {1}, f"the graph runs a test population twice: {concurrent}"


def test_the_gate_documentation_split_selects_exactly_the_documentation_pass() -> None:
    """Every test the public documentation pass selects is selected by exactly one gate node."""
    whole = _lanes_of(_DOCS_RECIPE)
    parts = [_lanes_of(name) for name in _GATE_DOCS_SPLIT]
    selected = [0 for _ in parts]
    for path in tracked_test_files(REPO_ROOT):
        relative = path.as_posix()
        if not relative.startswith("dev/docs/"):
            continue
        tests = marker_sets_in(REPO_ROOT / relative)
        assert tests is not None, f"test markers could not be read: {relative}"
        for entry in tests:
            hits = [_selects(lanes, relative, entry.markers) for lanes in parts]
            assert _selects(whole, relative, entry.markers) == any(hits), f"{relative}::{entry.test}"
            assert sum(hits) <= 1, f"both gate documentation nodes select {relative}::{entry.test}"
            selected = [count + hit for count, hit in zip(selected, hits, strict=True)]
    assert all(selected), (
        f"a gate documentation node selects nothing: {dict(zip(_GATE_DOCS_SPLIT, selected, strict=True))}"
    )


def test_prerequisites_precede_every_node_that_needs_them() -> None:
    graph = _graph()
    waves = _waves()
    required = {
        "authority": (
            "check-code",
            "check-registry",
            "fixtures-check",
            "registry-collect",
            "registry-load",
            "registry-seed",
            "registry-calculations",
            "registry-conformance",
            "docs-build",
            "docs-tests",
            "docs-strict-build-test",
            "harness",
            "unit",
            "integration-parallel",
            "integration-serial",
        ),
        "desktop-frontend-setup": ("registry-conformance", "registry-seed", "check-code"),
        "registry-collect": ("registry-calculations", "registry-conformance"),
        "registry-load": ("registry-calculations", "registry-conformance"),
        "registry-seed": ("registry-conformance",),
    }
    assert "docs-build" in graph.node("docs-strict-build-test").after
    waiting = sorted(node.name for node in graph.nodes if "docs-build" in node.after)
    assert waiting == ["docs-strict-build-test"], f"only the strict-build test may wait on the long build: {waiting}"
    for prerequisite, dependents in required.items():
        assert graph.node(prerequisite).kind == PREREQUISITE_KIND, f"{prerequisite} must block its dependents"
        for dependent in dependents:
            assert prerequisite in graph.node(dependent).after, f"{dependent} does not follow {prerequisite}"
            assert waves[prerequisite] < waves[dependent]


def test_writers_of_shared_output_never_run_together() -> None:
    graph = _graph()
    holders = {
        "fixtures": {"registry-seed", "check-code", "fixtures-check"},
        "cmake": {"check-code"},
        "docs-output": {"docs-build", "ci-contracts-parallel"},
        "distributions": {"build-distributions"},
    }
    for resource, nodes in holders.items():
        declared = {node.name for node in graph.nodes if resource in node.exclusive}
        assert declared == nodes, f"{resource} is held by {sorted(declared)}, not {sorted(nodes)}"
    waves = _waves()
    for resource in holders:
        sharing = [node for node in graph.nodes if resource in node.exclusive]
        assert len({waves[node.name] for node in sharing}) == len(sharing), f"{resource} holders share a wave"
    # The deployment contracts rebuild the single page the documentation tests read whole.
    assert waves["docs-build"] < waves["docs-strict-build-test"] < waves["ci-contracts-parallel"]
    assert waves["docs-tests"] < waves["ci-contracts-parallel"]


def test_the_documentation_build_leaves_the_sequence_corpus_to_the_harness() -> None:
    graph = _graph()
    harness_nodes = [node for node in graph.nodes if _node_recipe(node)[0] == _HARNESS_RECIPE]
    assert [node.name for node in harness_nodes] == ["harness"]
    harness = harness_nodes[0]
    assert dict(harness.env).get(SEQUENCE_JOBS_ENV) == str(harness.weight), "the corpus pool is not the node's weight"
    assert dict(graph.node("docs-build").env).get(SEQUENCE_CHECK_SKIP_ENV) == "1"
    for name in ("docs-tests", "docs-strict-build-test"):
        docs_recipe, with_dependencies = _node_recipe(graph.node(name))
        assert _HARNESS_RECIPE not in _invocation_tests(docs_recipe, with_dependencies=with_dependencies)


def test_the_cpu_budget_node_runs_last_and_alone() -> None:
    graph = _graph()
    waves = simulate_schedule(graph, _budget())
    perf = graph.node("ci-perf")

    assert perf.alone
    assert graph.nodes[-1] is perf, "the alone node must be declared last so nothing is held behind it"
    assert waves[-1] == (perf,)
    assert sum(len(wave) for wave in waves) == len(graph.nodes), "a node never started in the dry run"


def test_the_coverage_proof_detects_a_dropped_population(tmp_path: Path) -> None:
    """Teeth: a graph missing one node, read through the same helpers, fails the comparison."""
    dropped = "integration-serial"
    text = _GRAPH.read_text(encoding=UTF_8)
    block = f'[[node]]\nname = "{dropped}"\n'
    start = text.index(block)
    end = text.index("[[node]]", start + len(block))
    shrunk = tmp_path / "gate-local.toml"
    shrunk.write_text(text[:start] + text[end:], encoding=UTF_8)

    reduced = _graph_tests(load_gate_graph(shrunk))

    missing = _invocation_tests(_SEQUENTIAL_RECIPE) - reduced
    assert missing == Counter({_HARNESS_RECIPE: 1, "test-integration-serial": 1})
    assert shlex.join(_graph().node(dropped).command) == "just test-integration-serial"
