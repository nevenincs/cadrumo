"""The declared shape of a concurrent gate: nodes, ordering edges and shared resources.

A gate is a set of independent measurements with a few real dependencies
between them. The composition is data the caller supplies (a TOML or JSON
file), so the runner holds no list of populations and cannot drift from the
recipe that owns them. This module only parses and checks that data.

File schema (TOML shown; JSON carries the same keys)::

    schema = "cadrumo-gate-graph/v1"

    [[node]]
    name = "authority"                 # unique; also the log and report directory name
    kind = "prerequisite"              # see NODE_KINDS
    command = ["just", "publish-authority"]
    weight = 1                         # budget slots the node occupies while it runs
    exclusive = ["authority-store"]    # resources no two running nodes may share
    after = []                         # nodes that must finish before this one starts
    alone = false                      # true: runs with nothing else running
    workers = 4                        # pytest kinds only; defaults to weight
    env = { NAME = "value" }           # extra child environment

``after`` is an ordering edge. A dependent still runs when an ordinary node it
follows fails; it does not run when a ``prerequisite`` it follows fails or when
a node it follows did not run.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from dev.paths import UTF_8

GRAPH_SCHEMA: Final = "cadrumo-gate-graph/v1"

PREREQUISITE_KIND: Final = "prerequisite"

#: Kinds whose child receives its worker count through ``CADRUMO_PYTEST_WORKERS``.
PYTEST_KINDS: Final = frozenset({"pytest-parallel", "pytest-serial"})

NODE_KINDS: Final = frozenset({"static", "build", "command", PREREQUISITE_KIND, *PYTEST_KINDS})

_NAME: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_ENV_NAME: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NODE_KEYS: Final = frozenset({"name", "kind", "command", "weight", "after", "exclusive", "alone", "workers", "env"})

#: Child variables the runner itself owns; a node declaring one would silently lose it.
RUNNER_ENV_NAMES: Final = frozenset({"CADRUMO_CI_REPORTS_DIR", "CADRUMO_CI_REPORT_NAME", "CADRUMO_PYTEST_WORKERS"})


class GateGraphError(ValueError):
    """The graph file or a selection over it is not a runnable gate."""


@dataclass(frozen=True)
class GateNode:
    """One measurement of the gate."""

    name: str
    kind: str
    command: tuple[str, ...]
    weight: int = 1
    after: tuple[str, ...] = ()
    exclusive: tuple[str, ...] = ()
    alone: bool = False
    workers: int | None = None
    env: tuple[tuple[str, str], ...] = field(default=())

    @property
    def pytest_workers(self) -> int | None:
        """Return the worker count a pytest node passes to its child, ``None`` for other kinds."""
        if self.kind not in PYTEST_KINDS:
            return None
        return self.weight if self.workers is None else self.workers


@dataclass(frozen=True)
class GateGraph:
    """Nodes in declared order; the order is the scheduling priority."""

    nodes: tuple[GateNode, ...]

    def node(self, name: str) -> GateNode:
        """Return the node called ``name``."""
        for node in self.nodes:
            if node.name == name:
                return node
        raise KeyError(name)

    def select(self, only: tuple[str, ...]) -> GateGraph:
        """Return the named nodes plus every prerequisite they transitively follow.

        A partial run still needs the prerequisites its nodes depend on, but no
        other population; ordering edges to unselected nodes are dropped.
        """
        if not only:
            return self
        known = {node.name for node in self.nodes}
        if unknown := sorted(set(only) - known):
            raise GateGraphError(f"--only names unknown nodes: {', '.join(unknown)}")
        chosen = set(only)
        frontier = list(only)
        while frontier:
            for dependency in self.node(frontier.pop()).after:
                if dependency not in chosen and self.node(dependency).kind == PREREQUISITE_KIND:
                    chosen.add(dependency)
                    frontier.append(dependency)
        kept = tuple(
            GateNode(
                name=node.name,
                kind=node.kind,
                command=node.command,
                weight=node.weight,
                after=tuple(dependency for dependency in node.after if dependency in chosen),
                exclusive=node.exclusive,
                alone=node.alone,
                workers=node.workers,
                env=node.env,
            )
            for node in self.nodes
            if node.name in chosen
        )
        return GateGraph(kept)

    def check_budget(self, budget: int) -> None:
        """Refuse a budget below one or below any node's weight, which could never start."""
        if budget < 1:
            raise GateGraphError(f"budget must be at least 1, got {budget}")
        if oversized := [node.name for node in self.nodes if node.weight > budget]:
            raise GateGraphError(f"nodes weigh more than the budget of {budget}: {', '.join(oversized)}")


def load_gate_graph(path: Path) -> GateGraph:
    """Read and check a gate graph from a ``.toml`` or ``.json`` file."""
    text = path.read_text(encoding=UTF_8)
    try:
        if path.suffix == ".toml":
            document: object = tomllib.loads(text)
        elif path.suffix == ".json":
            document = json.loads(text)
        else:
            raise GateGraphError(f"gate graph must be a .toml or .json file: {path}")
    except (tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        raise GateGraphError(f"gate graph {path} does not parse: {exc}") from exc
    return parse_gate_graph(document)


def parse_gate_graph(document: object) -> GateGraph:
    """Check a decoded graph document and return the typed graph."""
    if not isinstance(document, dict):
        raise GateGraphError("gate graph must be a table")
    if document.get("schema") != GRAPH_SCHEMA:
        raise GateGraphError(f"gate graph schema must be {GRAPH_SCHEMA!r}")
    if unknown := sorted(set(document) - {"schema", "node"}):
        raise GateGraphError(f"gate graph has unknown keys: {', '.join(unknown)}")
    raw_nodes = document.get("node")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise GateGraphError("gate graph declares no nodes")
    nodes = tuple(_parse_node(raw, index) for index, raw in enumerate(raw_nodes))
    names = [node.name for node in nodes]
    if duplicates := sorted({name for name in names if names.count(name) > 1}):
        raise GateGraphError(f"node names repeat: {', '.join(duplicates)}")
    for node in nodes:
        if missing := sorted(set(node.after) - set(names)):
            raise GateGraphError(f"node {node.name} follows unknown nodes: {', '.join(missing)}")
        if node.name in node.after:
            raise GateGraphError(f"node {node.name} follows itself")
    _refuse_cycles(nodes)
    return GateGraph(nodes)


def _parse_node(raw: object, index: int) -> GateNode:
    if not isinstance(raw, dict):
        raise GateGraphError(f"node #{index} must be a table")
    if unknown := sorted(set(raw) - _NODE_KEYS):
        raise GateGraphError(f"node #{index} has unknown keys: {', '.join(unknown)}")
    name = raw.get("name")
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise GateGraphError(f"node #{index} needs a name of letters, digits, '.', '_' or '-'")
    kind = raw.get("kind")
    if kind not in NODE_KINDS:
        raise GateGraphError(f"node {name} kind must be one of {', '.join(sorted(NODE_KINDS))}")
    command = raw.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
        raise GateGraphError(f"node {name} command must be a non-empty list of non-empty strings")
    weight = raw.get("weight", 1)
    if not _is_int(weight) or weight < 1:
        raise GateGraphError(f"node {name} weight must be an integer of at least 1")
    workers = raw.get("workers")
    if workers is not None:
        if kind not in PYTEST_KINDS:
            raise GateGraphError(f"node {name} declares workers but is not a pytest node")
        if not _is_int(workers) or workers < 0:
            raise GateGraphError(f"node {name} workers must be a non-negative integer")
    alone = raw.get("alone", False)
    if not isinstance(alone, bool):
        raise GateGraphError(f"node {name} alone must be true or false")
    return GateNode(
        name=name,
        kind=kind,
        command=tuple(command),
        weight=weight,
        after=_names(raw.get("after", []), name, "after"),
        exclusive=_names(raw.get("exclusive", []), name, "exclusive"),
        alone=alone,
        workers=workers,
        env=_environment(raw.get("env", {}), name),
    )


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _names(value: object, node: str, key: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise GateGraphError(f"node {node} {key} must be a list of names")
    names: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise GateGraphError(f"node {node} {key} must be a list of names")
        names.append(item)
    if len(set(names)) != len(names):
        raise GateGraphError(f"node {node} {key} repeats a name")
    return tuple(names)


def _environment(value: object, node: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, dict):
        raise GateGraphError(f"node {node} env must be a table of strings")
    pairs: list[tuple[str, str]] = []
    for key, item in value.items():
        if not isinstance(key, str) or not _ENV_NAME.fullmatch(key) or not isinstance(item, str):
            raise GateGraphError(f"node {node} env must map variable names to strings")
        if key in RUNNER_ENV_NAMES:
            raise GateGraphError(f"node {node} env sets {key}, which the runner owns")
        pairs.append((key, item))
    return tuple(sorted(pairs))


def _refuse_cycles(nodes: tuple[GateNode, ...]) -> None:
    edges = {node.name: node.after for node in nodes}
    state: dict[str, int] = {}

    def visit(name: str, trail: tuple[str, ...]) -> None:
        if state.get(name) == 2:
            return
        if state.get(name) == 1:
            cycle = (*trail[trail.index(name) :], name)
            raise GateGraphError(f"after edges form a cycle: {' -> '.join(cycle)}")
        state[name] = 1
        for dependency in edges[name]:
            visit(dependency, (*trail, name))
        state[name] = 2

    for node in nodes:
        visit(node.name, ())
