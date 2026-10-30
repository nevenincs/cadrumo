"""Executable command syntax derived from the production command graphs."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import TYPE_CHECKING

from cadrumo_client.commands.shared_contracts import BindingState

if TYPE_CHECKING:
    from cadrumo_client.commands.graph import CommandSpecGraph


def _command_graphs() -> tuple[CommandSpecGraph, ...]:
    """Load spec authorities only when needed, without resolving their handlers."""
    from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
    from cadrumo_runtime.commands.command_specs import RUNTIME_COMMAND_GRAPH

    return COMMAND_GRAPH, RUNTIME_COMMAND_GRAPH


@lru_cache(maxsize=1)
def executable_command_paths() -> frozenset[tuple[str, ...]]:
    """Cache complete implemented leaf paths for one audit process."""
    return frozenset(
        node.path
        for graph in _command_graphs()
        for node in graph.nodes()
        if node.spec.kind == "leaf" and node.spec.handler is not None and node.spec.handler.state is BindingState.TARGET
    )


@lru_cache(maxsize=1)
def _compile_command_paths(paths: frozenset[tuple[str, ...]]) -> re.Pattern[str]:
    """Match horizontal command spacing and refuse partial word/hyphen matches."""
    alternatives = [
        r"[ \t]+".join(re.escape(token) for token in path) for path in sorted(paths, key=lambda p: (-len(p), p))
    ]
    if not alternatives:
        return re.compile(r"(?!)")
    return re.compile(r"(?<![\w-])(?:" + "|".join(alternatives) + r")(?![\w-])")


def command_path_pattern() -> re.Pattern[str]:
    """Return exact executable path syntax; arguments and prose remain separate."""
    return _compile_command_paths(executable_command_paths())
