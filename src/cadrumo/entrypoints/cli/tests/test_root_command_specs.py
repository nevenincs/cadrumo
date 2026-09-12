from __future__ import annotations

import ast
from pathlib import Path

import pytest
from typer.testing import CliRunner

from .._command_target import resolve_deferred_target
from .._root_command_specs import ROOT_COMMAND_SPECS
from ..command_spec import CommandSpecGraph
from ..main import app

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_root_specs_own_the_executable_namespace_and_parameter_contracts() -> None:
    graph = CommandSpecGraph(ROOT_COMMAND_SPECS)

    assert tuple(node.path for node in graph.nodes()) == (
        ("aeat",),
        ("aeat", "app"),
        ("aeat", "app", "tui"),
        ("aeat", "config"),
    )
    root = graph.by_key()["root"]
    assert tuple(parameter.name for parameter in root.parameters) == (
        "language",
        "profile",
        "profile_secrets_stdin",
        "profile_secrets_fd",
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


def test_root_executable_targets_are_public_behavior_only_functions() -> None:
    executable = [spec for spec in ROOT_COMMAND_SPECS if spec.handler is not None]
    assert {
        spec.handler.target.qualname
        for spec in executable
        if spec.handler is not None and spec.handler.target is not None
    } == {
        "app_root",
        "config_root",
        "launch_tui",
        "root_command",
    }
    for spec in executable:
        assert spec.handler is not None
        assert spec.handler.target is not None
        assert callable(resolve_deferred_target(spec.handler.target))

    module_path = Path(__file__).parents[1] / "_root_cli.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {"app_root", "root_command"}
    }
    assert functions.keys() == {"app_root", "root_command"}
    assert all(not node.decorator_list for node in functions.values())
    assert all("typer.Option" not in ast.unparse(node.args) for node in functions.values())


def test_the_live_parser_exposes_only_the_app_tui_launch_seam() -> None:
    """The TUI launch is a leaf under ``app``, never a root request modifier."""
    runner = CliRunner()

    app_help = runner.invoke(app, ["app", "--help"])
    launcher_help = runner.invoke(app, ["app", "tui", "--help"])
    retired_request = runner.invoke(app, ["--tui"])

    assert app_help.exit_code == 0, app_help.output
    assert launcher_help.exit_code == 0, launcher_help.output
    assert retired_request.exit_code != 0
    assert "--tui" in retired_request.output
