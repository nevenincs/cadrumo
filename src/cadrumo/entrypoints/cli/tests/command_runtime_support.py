"""Compile focused command surfaces for command-graph behavior tests."""

from __future__ import annotations

from functools import cache

import typer

from cadrumo.entrypoints.cli.command_lifecycle import dispatch_cli_behavior
from cadrumo_client.commands.compiler import build_command_app
from cadrumo_client.commands.graph import CommandSpecGraph


@cache
def build_command_subtree(graph: CommandSpecGraph, key: str) -> typer.Typer:
    """Compile one declared subtree for focused command behavior assertions."""
    graph.spec(key)
    return build_command_app(graph, root_key=key, dispatcher=dispatch_cli_behavior)
