"""Composed Typer subtree for the ``config`` command family.

The graph and the sub-app are DEFINITIONS, not re-exports, so they live in a
module rather than in the package initializer.  A package namespace is inert
here: building a command subtree at import time is an initialization side
effect, and it ran whenever anything touched the package for any reason.

The root command tree declares the ``config`` group itself, so nothing outside
this package composes the subtree; it is kept because the lazy command tree
loads a family on demand and this is where that family is assembled.
"""

from __future__ import annotations

from .._command_runtime import build_command_subtree
from .._command_spec import CommandSpecGraph
from .._root_command_specs import ROOT_COMMAND_SPECS
from ._command_specs import CONFIG_COMMAND_SPECS

CONFIG_COMMAND_GRAPH = CommandSpecGraph((*ROOT_COMMAND_SPECS, *CONFIG_COMMAND_SPECS))
app = build_command_subtree(CONFIG_COMMAND_GRAPH, "config")

__all__ = ["CONFIG_COMMAND_GRAPH", "app"]
