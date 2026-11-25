"""Which gate nodes may start now: the scheduling policy, free of processes.

The real runner and the dry run drive the same policy, so a printed schedule
is the order the runner would follow if every node took equal time.

Rules, in priority order of the declared node list:

- A node starts only after every node it follows has finished.
- A node does not run when a prerequisite it follows did not pass, or when any
  node it follows did not run. It is reported as not run with those names.
- The weights of running nodes never sum above the budget. A lighter node
  later in the list may start while a heavier earlier one waits for room.
- Two running nodes never share an exclusive resource name.
- An ``alone`` node starts only when nothing runs, and nothing starts beside
  it. Once it is ready no further node starts, so it cannot be starved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from .gate_graph import PREREQUISITE_KIND

if TYPE_CHECKING:
    from .gate_graph import GateGraph, GateNode

PASSED: Final = "passed"
FAILED: Final = "failed"
NOT_RUN: Final = "not_run"


class GateSchedule:
    """The run state of one gate: pending, running and finished nodes."""

    def __init__(self, graph: GateGraph, budget: int) -> None:
        graph.check_budget(budget)
        self._graph = graph
        self._budget = budget
        self._pending: list[GateNode] = list(graph.nodes)
        self._running: dict[str, GateNode] = {}
        self.verdicts: dict[str, str] = {}

    @property
    def running_weight(self) -> int:
        """Return the budget slots running nodes occupy."""
        return sum(node.weight for node in self._running.values())

    @property
    def done(self) -> bool:
        """Return whether every node has a verdict."""
        return not self._pending and not self._running

    def blocked(self) -> list[tuple[GateNode, tuple[str, ...]]]:
        """Settle and return pending nodes that can no longer run, each with the names that block it."""
        settled: list[tuple[GateNode, tuple[str, ...]]] = []
        changed = True
        while changed:
            changed = False
            for node in list(self._pending):
                causes = tuple(dependency for dependency in node.after if self._blocks(dependency))
                if causes:
                    self._pending.remove(node)
                    self.verdicts[node.name] = NOT_RUN
                    settled.append((node, causes))
                    changed = True
        return settled

    def startable(self) -> tuple[GateNode, ...]:
        """Return the nodes that may start now, in priority order, without starting them."""
        if any(node.alone for node in self._running.values()):
            return ()
        used = self.running_weight
        held = {resource for node in self._running.values() for resource in node.exclusive}
        chosen: list[GateNode] = []
        for node in self._pending:
            if not all(dependency in self.verdicts for dependency in node.after):
                continue
            if node.alone:
                if not self._running and not chosen:
                    chosen.append(node)
                break
            if used + node.weight <= self._budget and held.isdisjoint(node.exclusive):
                chosen.append(node)
                used += node.weight
                held.update(node.exclusive)
        return tuple(chosen)

    def start(self, node: GateNode) -> None:
        """Move ``node`` from pending to running."""
        self._pending.remove(node)
        self._running[node.name] = node

    def finish(self, name: str, verdict: str) -> None:
        """Record a running node's verdict."""
        del self._running[name]
        self.verdicts[name] = verdict

    def abandon(self) -> tuple[GateNode, ...]:
        """Mark every pending node not run and return them, for an interrupted gate."""
        abandoned = tuple(self._pending)
        self._pending.clear()
        for node in abandoned:
            self.verdicts[node.name] = NOT_RUN
        return abandoned

    def _blocks(self, dependency: str) -> bool:
        verdict = self.verdicts.get(dependency)
        if verdict is None:
            return False
        if verdict == NOT_RUN:
            return True
        return verdict != PASSED and self._graph.node(dependency).kind == PREREQUISITE_KIND


def simulate_schedule(graph: GateGraph, budget: int) -> tuple[tuple[GateNode, ...], ...]:
    """Return the start waves the policy produces when every node takes one equal step and passes."""
    schedule = GateSchedule(graph, budget)
    waves: list[tuple[GateNode, ...]] = []
    while True:
        schedule.blocked()
        if schedule.done:
            break
        wave = schedule.startable()
        if not wave:
            raise RuntimeError("gate schedule cannot make progress")
        for node in wave:
            schedule.start(node)
        waves.append(wave)
        for node in wave:
            schedule.finish(node.name, PASSED)
    return tuple(waves)
