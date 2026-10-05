"""Compile focused command surfaces for command-graph behavior tests."""

from __future__ import annotations

from functools import cache

import typer

from .._command_runtime import _node_app
from ..command_graph import CommandSpecGraph


@cache
def build_command_subtree(graph: CommandSpecGraph, key: str) -> typer.Typer:
    """Compile one declared subtree for focused command behavior assertions."""
    graph.spec(key)
    return _node_app(graph, key)
