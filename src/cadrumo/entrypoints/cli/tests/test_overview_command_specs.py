"""Independent contract tests for overview CommandSpec authority."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from .._command_runtime import build_command_subtree, resolve_deferred_target
from .._overview_command_specs import OVERVIEW_COMMAND_SPECS
from .._root_command_specs import ROOT_COMMAND_SPECS
from ..command_spec import CommandSpecGraph, SchemaState

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _graph() -> CommandSpecGraph:
    return CommandSpecGraph((*ROOT_COMMAND_SPECS, *OVERVIEW_COMMAND_SPECS))


def test_overview_specs_match_the_independent_operator_path_set() -> None:
    expected_tokens = {"agenda", "backlog", "calendar", "explain", "pipeline", "prepare", "status"}
    nodes = [node for node in _graph().nodes() if node.path[1:3] == ("app", "overview")]

    assert len(nodes) == 8
    assert {node.path[-1] for node in nodes if node.spec.kind == "leaf"} == expected_tokens


def test_overview_leaf_targets_and_schemas_are_public_and_resolvable() -> None:
    leaves = [spec for spec in OVERVIEW_COMMAND_SPECS if spec.kind == "leaf"]
    for spec in leaves:
        assert spec.handler is not None and spec.handler.target is not None
        assert resolve_deferred_target(spec.handler.target)
        assert spec.result_schema.state is SchemaState.TARGET
        assert spec.result_schema.target is not None
        assert resolve_deferred_target(spec.result_schema.target)


def test_overview_runtime_compiles_required_and_aliased_options() -> None:
    app = build_command_subtree(_graph(), "app_overview")

    calendar = CliRunner().invoke(app, ["calendar", "--help"])
    explain = CliRunner().invoke(app, ["explain", "--help"])

    assert calendar.exit_code == 0, calendar.output
    assert "--from" in calendar.output and "[required]" in calendar.output
    assert "--output-language, --language" in calendar.output
    assert explain.exit_code == 0, explain.output
    assert "{modelo}" in explain.output
