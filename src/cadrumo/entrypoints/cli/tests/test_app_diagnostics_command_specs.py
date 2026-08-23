"""Independent contract tests for diagnostics CommandSpec authority."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from .._app_diagnostics_command_specs import DIAGNOSTICS_COMMAND_SPECS
from .._command_runtime import build_command_subtree, resolve_deferred_target
from .._command_spec import CommandSpecGraph, SchemaState
from .._root_command_specs import ROOT_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _graph() -> CommandSpecGraph:
    return CommandSpecGraph((*ROOT_COMMAND_SPECS, *DIAGNOSTICS_COMMAND_SPECS))


def test_diagnostics_specs_match_the_independent_operator_path_set() -> None:
    expected = {
        ("aeat", "app", "diagnostics"),
        ("aeat", "app", "diagnostics", "errors"),
        ("aeat", "app", "diagnostics", "latency"),
        ("aeat", "app", "diagnostics", "llm-usage"),
        ("aeat", "app", "diagnostics", "run-health"),
        ("aeat", "app", "diagnostics", "runs"),
        ("aeat", "app", "diagnostics", "telemetry"),
        ("aeat", "app", "diagnostics", "telemetry", "flush"),
        ("aeat", "app", "diagnostics", "telemetry", "status"),
    }

    actual = {node.path for node in _graph().nodes() if node.path[1:3] == ("app", "diagnostics")}

    assert actual == expected


def test_diagnostics_leaf_targets_and_schemas_are_public_and_resolvable() -> None:
    leaves = [spec for spec in DIAGNOSTICS_COMMAND_SPECS if spec.kind == "leaf"]
    assert len(leaves) == 7
    for spec in leaves:
        assert spec.handler is not None
        assert spec.handler.target is not None
        assert resolve_deferred_target(spec.handler.target)
        assert spec.result_schema.state is SchemaState.TARGET
        assert spec.result_schema.target is not None
        assert resolve_deferred_target(spec.result_schema.target)


def test_diagnostics_runtime_compiles_representative_nested_help() -> None:
    app = build_command_subtree(_graph(), "app_diagnostics")

    runs = CliRunner().invoke(app, ["runs", "--help"])
    flush = CliRunner().invoke(app, ["telemetry", "flush", "--help"])

    assert runs.exit_code == 0, runs.output
    assert "--limit" in runs.output
    assert flush.exit_code == 0, flush.output
    assert "--dry-run / --no-dry-run" in flush.output
    assert "--acknowledge-remote-telemetry" in flush.output
