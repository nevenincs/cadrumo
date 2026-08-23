"""Demand-loaded configuration command surface."""

from __future__ import annotations

from .._command_runtime import build_command_subtree
from .._command_spec import CommandSpecGraph
from .._root_command_specs import ROOT_COMMAND_SPECS
from ._command_specs import CONFIG_COMMAND_SPECS

CONFIG_COMMAND_GRAPH = CommandSpecGraph((*ROOT_COMMAND_SPECS, *CONFIG_COMMAND_SPECS))
app = build_command_subtree(CONFIG_COMMAND_GRAPH, "config")

__all__ = ["CONFIG_COMMAND_GRAPH", "app"]
