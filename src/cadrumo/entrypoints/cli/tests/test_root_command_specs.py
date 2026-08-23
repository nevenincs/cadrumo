from __future__ import annotations

import pytest

from .._command_spec import CommandSpecGraph
from .._root_command_specs import ROOT_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_root_specs_own_the_executable_namespace_and_parameter_contracts() -> None:
    graph = CommandSpecGraph(ROOT_COMMAND_SPECS)

    assert tuple(node.path for node in graph.nodes()) == (
        ("aeat",),
        ("aeat", "app"),
        ("aeat", "config"),
    )
    root = graph.by_key()["root"]
    assert tuple(parameter.name for parameter in root.parameters) == (
        "language",
        "profile",
        "version",
        "detail",
        "help_",
        "format_",
        "quiet",
        "verbose",
        "debug",
    )
    assert root.invocation.add_completion is True
    assert graph.by_schema_identity() == {
        "root.app": graph.by_key()["app"],
        "root.config": graph.by_key()["config"],
        "root.status": root,
    }
