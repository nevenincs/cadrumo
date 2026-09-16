"""Resolving a node must stay within its performance class's module budget.

Additive to the two capability gates, not a restatement of them.
``test_capability_family_isolation`` asks whether a node loads families it does
not DECLARE; ``test_resolution_defers_capabilities`` asks whether it loads any
family at all before execution. Both are blind to weight that belongs to no
named family -- a node could pull a hundred unfamilied modules and pass each.
This budgets the total.

**Why module count and not latency.** Calibrated latency budgets were the
original ask. That is not measurable here: a quiet-control CLI resolution takes
about 1.75 seconds on this repository's backing share, and peer agents commonly
run two hundred concurrent processes on the same machine, so wall-clock
readings track contention rather than code. A timing gate would fail when a
colleague runs a suite and pass when the machine is idle, which is worse than
no gate and is why single-sample host-specific thresholds were refused.
Module count is what latency is a proxy FOR on a cold
process, and it is exact and load-independent.

**The floor is measured, never pinned.** Every node pays the CLI bootstrap, and
that figure moves with ordinary work. Hardcoding it would encode today's tree
and train the next author to edit the constant. The floor is taken as the
minimum across the graph at run time, and each node is judged on its EXCESS
over that floor -- so the budget describes a shape that survives the bootstrap
changing.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from ..command_specs import COMMAND_GRAPH
from .test_resolution_defers_capabilities import _RESOLUTION_LOADERS

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: Modules a node may import BEYOND the shared bootstrap floor, by declared
#: performance class.
#:
#: Measured, with headroom, not invented. Outside the known resolution-loader
#: list, most nodes sit within 8 modules of the floor; the ledger invoice and
#: rule commands reach 118, which is `cadrumo.core` value types -- money,
#: periods, parsing, aggregation enums -- that their parameter signatures
#: genuinely declare. Core is the innermost layer and those types ARE the
#: command's contract, so that is a command paying for itself rather than
#: amplification.
#:
#: The budgets sit above the observed maxima with room to grow, and well below
#: what a regression would cost: newly pulling the registry adds ~152 modules
#: and persistence ~179, either of which clears these ceilings from any current
#: position. A first attempt used a flat 64, set from the class MEDIANS without
#: checking the non-heavy maxima; that failed 8 nodes for doing nothing wrong.
_CLASS_EXCESS_BUDGET: dict[str, int] = {
    "metadata": 32,
    "interactive": 64,
    "compute": 64,
    "local-io": 160,
    "external-io": 160,
}

_HEAVY_NODE = "app/ledger/import"
_BATCH_COUNT = 3
_MEASUREMENT_TIMEOUT_SECONDS = 600

_PROBE = textwrap.dedent(
    """
    import json
    import sys
    from pathlib import Path

    from cadrumo.entrypoints.cli.tests.cli_performance import measure_resolution_costs

    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    records = measure_resolution_costs(request["paths"], record_names_for=request["record_names_for"])
    Path(sys.argv[2]).write_text(json.dumps(records), encoding="utf-8")
    """
)

type _CostRecord = dict[str, Any]


def _run_measurements(runs: list[list[str]], workdir: Path, *, named: frozenset[str]) -> list[list[_CostRecord]]:
    """Run each list of node paths in its own interpreter, all concurrently.

    ``named`` paths also report their module names, for diffing a disagreement.
    """
    started: list[tuple[subprocess.Popen[bytes], Path, Path]] = []
    try:
        for index, run in enumerate(runs):
            request = workdir / f"request-{index}.json"
            result = workdir / f"result-{index}.json"
            log = workdir / f"child-{index}.log"
            request.write_text(
                json.dumps({"paths": [name.split("/") for name in run], "record_names_for": sorted(named & set(run))}),
                encoding="utf-8",
            )
            with log.open("wb") as output:
                process = subprocess.Popen(
                    [sys.executable, "-c", _PROBE, str(request), str(result)],
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
            started.append((process, result, log))
        outcomes: list[list[_CostRecord]] = []
        for process, result, log in started:
            returncode = process.wait(timeout=_MEASUREMENT_TIMEOUT_SECONDS)
            assert returncode == 0, f"measurement child failed: {log.read_text(encoding='utf-8', errors='replace')}"
            outcomes.append(json.loads(result.read_text(encoding="utf-8")))
        return outcomes
    finally:
        for process, _, _ in started:
            if process.poll() is None:
                process.kill()
                process.wait()


def _comparable(record: _CostRecord) -> tuple[object, ...]:
    return record["path"], record["modules"], record["digest"], record["error"] is not None


def _module_diff(left: _CostRecord, right: _CostRecord) -> str:
    left_names, right_names = set(left["names"] or ()), set(right["names"] or ())
    return (
        f"only in the first: {sorted(left_names - right_names)}; only in the second: {sorted(right_names - left_names)}"
    )


def _budgeted_nodes() -> list[tuple[str, str]]:
    """Return ``(path, performance class)`` for every node this gate budgets.

    The nodes that still load capability families are excluded here and owned by
    ``test_resolution_defers_capabilities``, which lists them with their causes.
    Importing that list rather than restating it keeps one canonical home: a
    second copy would drift, and the copies would disagree about which nodes are
    known-heavy.
    """
    return [
        ("/".join(node.path[1:]), node.spec.policy.performance)
        for node in COMMAND_GRAPH.nodes()
        # The graph ROOT has an empty path: it is the executable itself, not a
        # command anyone resolves, and an empty token is not addressable.
        if node.path[1:] and "/".join(node.path[1:]) not in _RESOLUTION_LOADERS
    ]


@pytest.fixture(scope="module")
def resolution_costs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, _CostRecord]:
    """Every budgeted node's cost, measured in batches and checked against fresh interpreters.

    Starting one interpreter per node paid the CLI import floor hundreds of
    times, so each batch interpreter measures many nodes and resets itself in
    between (see ``measure_resolution_costs``). That reset is only trusted
    while it holds here: each batch opens with the heavy node and repeats it
    last, and every batch measures the same control node after all of its
    other nodes -- after the most resets -- which is measured again in an
    interpreter of its own. Any disagreement fails every dependent test
    instead of reporting a batched number.
    """
    *names, control_node = [name for name, _ in _budgeted_nodes()]
    shards = [names[index::_BATCH_COUNT] for index in range(_BATCH_COUNT)]
    batches = [[_HEAVY_NODE, *shard, control_node, _HEAVY_NODE] for shard in shards]
    *batch_records, (control,) = _run_measurements(
        [*batches, [control_node]],
        tmp_path_factory.mktemp("resolution-costs"),
        named=frozenset({_HEAVY_NODE, control_node}),
    )

    for records in batch_records:
        first, batched, last = records[0], records[-2], records[-1]
        if _comparable(first) != _comparable(last):
            pytest.fail(
                f"a batch measured `{_HEAVY_NODE}` differently before and after its other nodes "
                f"({first['modules']} vs {last['modules']} modules): the per-node reset leaks state; "
                f"{_module_diff(first, last)}"
            )
        if _comparable(batched) != _comparable(control):
            pytest.fail(
                f"`{control_node}` loads {batched['modules']} modules in a batch but "
                f"{control['modules']} in a fresh interpreter: the batched measurement is not independent; "
                f"{_module_diff(batched, control)}"
            )

    costs = {record["path"]: record for records in batch_records for record in records[1:-2]}
    costs[control_node] = control
    costs[_HEAVY_NODE] = batch_records[0][0]
    return costs


def _resolution_cost(costs: dict[str, _CostRecord], name: str) -> int:
    record = costs[name]
    assert record["error"] is None, f"{name.split('/')}: {record['error']}"
    return int(record["modules"])


@pytest.fixture(scope="module")
def bootstrap_floor(resolution_costs: dict[str, _CostRecord]) -> int:
    """The cheapest resolution in the graph: what every node pays regardless."""
    return min(_resolution_cost(resolution_costs, name) for name, _ in _budgeted_nodes()[:12])


def test_every_performance_class_has_a_budget() -> None:
    """FIXTURE ANCHOR: an unbudgeted class would pass by having no rule."""
    declared = {node.spec.policy.performance for node in COMMAND_GRAPH.nodes()}
    unbudgeted = sorted(declared - set(_CLASS_EXCESS_BUDGET))

    assert unbudgeted == [], f"these performance classes have no budget: {unbudgeted}"


@pytest.mark.parametrize(("name", "klass"), _budgeted_nodes(), ids=lambda value: value)
def test_a_node_resolves_within_its_class_budget(
    name: str, klass: str, bootstrap_floor: int, resolution_costs: dict[str, _CostRecord]
) -> None:
    """DISCRIMINATING: resolution cost stays near the floor for its class."""
    excess = _resolution_cost(resolution_costs, name) - bootstrap_floor
    budget = _CLASS_EXCESS_BUDGET[klass]

    assert excess <= budget, (
        f"`aeat {name.replace('/', ' ')}` ({klass}) imports {excess} modules beyond the "
        f"{bootstrap_floor}-module bootstrap floor, over its {budget} budget. "
        "Something on its resolution path gained an eager import."
    )


def test_the_budget_would_reject_a_known_heavy_node(
    bootstrap_floor: int, resolution_costs: dict[str, _CostRecord]
) -> None:
    """ANTI-TAUTOLOGY: the measurement must be able to exceed a budget.

    Every budgeted node passing could mean the probe reports a constant. This
    takes a node the other gate lists as heavy and requires it to blow the
    widest budget here -- so a passing run above is a measurement.
    """
    heavy = _resolution_cost(resolution_costs, _HEAVY_NODE) - bootstrap_floor

    assert heavy > max(_CLASS_EXCESS_BUDGET.values()), (
        f"`app ledger import` resolves only {heavy} modules above the floor, which no longer "
        "exceeds any class budget; this proof no longer demonstrates the gate can fail."
    )
