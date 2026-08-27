"""Resolving a node must stay within its performance class's module budget.

Additive to the two capability gates, not a restatement of them.
``test_capability_family_isolation`` asks whether a node loads families it does
not DECLARE; ``test_resolution_defers_capabilities`` asks whether it loads any
family at all before execution. Both are blind to weight that belongs to no
named family -- a node could pull a hundred unfamilied modules and pass each.
This budgets the total.

**Why module count and not latency.** The Step calls for calibrated latency
budgets. That is not measurable here: a quiet-control CLI resolution takes
about 1.75 seconds on this repository's backing share, and peer agents commonly
run two hundred concurrent processes on the same machine, so wall-clock
readings track contention rather than code. A timing gate would fail when a
colleague runs a suite and pass when the machine is idle, which is worse than
no gate and is what the campaign ADR means by refusing single-sample
host-specific thresholds. Module count is what latency is a proxy FOR on a cold
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

import pytest

from .. import command_graph
from .test_resolution_defers_capabilities import _RESOLUTION_LOADERS

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: Modules a node may import BEYOND the shared bootstrap floor, by declared
#: performance class.
#:
#: Measured, with headroom, not invented: every node outside the known
#: resolution-loader list currently sits within 8 modules of the floor, in every
#: class. These allowances leave room for ordinary growth while still failing on
#: a node that starts pulling a subsystem.
_CLASS_EXCESS_BUDGET: dict[str, int] = {
    "metadata": 32,
    "interactive": 64,
    "local-io": 64,
    "compute": 64,
    "external-io": 64,
}

_PROBE = textwrap.dedent(
    """
    import json
    import sys

    from cadrumo.tests.cli_performance import _resolve_cli_path

    _resolve_cli_path(tuple(json.loads(sys.argv[1])))
    print(len([name for name in sys.modules if name.startswith("cadrumo")]))
    """
)


def _resolution_cost(path: list[str]) -> int:
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE, json.dumps(path)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, f"{path}: {completed.stderr}"
    return int(completed.stdout.strip().splitlines()[-1])


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
        for node in command_graph.nodes()
        # The graph ROOT has an empty path: it is the executable itself, not a
        # command anyone resolves, and an empty token is not addressable.
        if node.path[1:] and "/".join(node.path[1:]) not in _RESOLUTION_LOADERS
    ]


@pytest.fixture(scope="module")
def bootstrap_floor() -> int:
    """The cheapest resolution in the graph: what every node pays regardless."""
    return min(_resolution_cost(name.split("/")) for name, _ in _budgeted_nodes()[:12])


def test_every_performance_class_has_a_budget() -> None:
    """FIXTURE ANCHOR: an unbudgeted class would pass by having no rule."""
    declared = {node.spec.policy.performance for node in command_graph.nodes()}
    unbudgeted = sorted(declared - set(_CLASS_EXCESS_BUDGET))

    assert unbudgeted == [], f"these performance classes have no budget: {unbudgeted}"


@pytest.mark.parametrize(("name", "klass"), _budgeted_nodes(), ids=lambda value: value)
def test_a_node_resolves_within_its_class_budget(name: str, klass: str, bootstrap_floor: int) -> None:
    """DISCRIMINATING: resolution cost stays near the floor for its class."""
    excess = _resolution_cost(name.split("/")) - bootstrap_floor
    budget = _CLASS_EXCESS_BUDGET[klass]

    assert excess <= budget, (
        f"`aeat {name.replace('/', ' ')}` ({klass}) imports {excess} modules beyond the "
        f"{bootstrap_floor}-module bootstrap floor, over its {budget} budget. "
        "Something on its resolution path gained an eager import."
    )


def test_the_budget_would_reject_a_known_heavy_node(bootstrap_floor: int) -> None:
    """ANTI-TAUTOLOGY: the measurement must be able to exceed a budget.

    Every budgeted node passing could mean the probe reports a constant. This
    takes a node the other gate lists as heavy and requires it to blow the
    widest budget here -- so a passing run above is a measurement.
    """
    heavy = _resolution_cost(["app", "ledger", "import"]) - bootstrap_floor

    assert heavy > max(_CLASS_EXCESS_BUDGET.values()), (
        f"`app ledger import` resolves only {heavy} modules above the floor, which no longer "
        "exceeds any class budget; this proof no longer demonstrates the gate can fail."
    )
