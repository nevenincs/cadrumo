"""Independent contract tests for quickfile CommandSpec authority."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from .._app_quickfile_command_specs import QUICKFILE_COMMAND_SPECS
from .._command_runtime import build_command_subtree, resolve_deferred_target
from .._root_command_specs import ROOT_COMMAND_SPECS
from ..command_spec import CommandSpecGraph

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_quickfile_is_one_executable_group_with_resolvable_targets() -> None:
    spec = QUICKFILE_COMMAND_SPECS[0]
    assert len(QUICKFILE_COMMAND_SPECS) == 1
    assert spec.kind == "group" and spec.invocation.invoke_without_command
    assert spec.handler is not None and spec.handler.target is not None
    assert resolve_deferred_target(spec.handler.target)
    assert spec.result_schema.target is not None
    assert resolve_deferred_target(spec.result_schema.target)


def test_quickfile_runtime_preserves_required_repeatable_and_election_options() -> None:
    graph = CommandSpecGraph((*ROOT_COMMAND_SPECS, *QUICKFILE_COMMAND_SPECS))
    result = CliRunner().invoke(build_command_subtree(graph, "app_quickfile"), ["--help"])

    assert result.exit_code == 0, result.output
    assert "--modelo" in result.output and "[required]" in result.output
    assert "--casilla" in result.output and "--binding" in result.output
    assert "--refund-election <compensar|devolver>" in result.output
