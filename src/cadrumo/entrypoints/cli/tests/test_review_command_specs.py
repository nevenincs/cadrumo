"""Independent contract tests for review CommandSpec authority."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from .._command_runtime import build_command_subtree, resolve_deferred_target
from .._review_command_specs import REVIEW_COMMAND_SPECS
from .._root_command_specs import ROOT_COMMAND_SPECS
from ..command_spec import CommandSpecGraph

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _graph() -> CommandSpecGraph:
    return CommandSpecGraph((*ROOT_COMMAND_SPECS, *REVIEW_COMMAND_SPECS))


def test_review_specs_are_the_exact_three_node_surface() -> None:
    nodes = [node for node in _graph().nodes() if node.path[1:3] == ("app", "review")]

    assert {node.path for node in nodes} == {
        ("aeat", "app", "review"),
        ("aeat", "app", "review", "queue"),
        ("aeat", "app", "review", "view"),
    }
    for spec in REVIEW_COMMAND_SPECS[1:]:
        assert spec.handler is not None and spec.handler.target is not None
        assert resolve_deferred_target(spec.handler.target)
        assert spec.result_schema.target is not None
        assert resolve_deferred_target(spec.result_schema.target)


def test_review_runtime_preserves_repeated_filters_state_and_view_argument() -> None:
    app = build_command_subtree(_graph(), "app_review")

    queue = CliRunner().invoke(app, ["queue", "--help"])
    view = CliRunner().invoke(app, ["view", "--help"])

    assert queue.exit_code == 0, queue.output
    assert "--kind" in queue.output and "--source-kind" in queue.output
    assert "--state pending|all" in queue.output
    assert view.exit_code == 0, view.output
    assert "item_id" in view.output
