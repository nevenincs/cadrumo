"""Independent contract tests for registry CommandSpec authority."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from .._command_runtime import build_command_subtree, resolve_deferred_target
from .._registry_command_specs import REGISTRY_COMMAND_SPECS
from .._root_command_specs import ROOT_COMMAND_SPECS
from ..command_spec import CommandSpecGraph

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _graph() -> CommandSpecGraph:
    return CommandSpecGraph((*ROOT_COMMAND_SPECS, *REGISTRY_COMMAND_SPECS))


#: Every command path the ``app registry`` family exposes, as the exact set.
#:
#: Enumerated rather than counted: a bare count cannot tell a removed command
#: from a renamed one, and it says nothing about WHICH surface is exposed. This
#: set fails loudly in both directions -- a command silently added to the
#: product surface, and one silently dropped from it.
_REGISTRY_COMMAND_PATHS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("aeat", "app", "registry"),
        ("aeat", "app", "registry", "citations"),
        ("aeat", "app", "registry", "citations", "list"),
        ("aeat", "app", "registry", "citations", "verify"),
        ("aeat", "app", "registry", "citations", "view"),
        ("aeat", "app", "registry", "diff-revisions"),
        ("aeat", "app", "registry", "inspect"),
        ("aeat", "app", "registry", "manuals"),
        ("aeat", "app", "registry", "manuals", "list"),
        ("aeat", "app", "registry", "manuals", "rules"),
        ("aeat", "app", "registry", "manuals", "verify"),
        ("aeat", "app", "registry", "manuals", "view"),
        ("aeat", "app", "registry", "verify"),
        ("aeat", "app", "registry", "verify-filed-state"),
    },
)


def test_registry_specs_are_the_exact_declared_node_surface() -> None:
    nodes = [node for node in _graph().nodes() if node.path[1:3] == ("app", "registry")]
    assert {tuple(node.path) for node in nodes} == _REGISTRY_COMMAND_PATHS
    assert {node.path[-1] for node in nodes if node.spec.kind == "group"} == {
        "registry",
        "citations",
        "manuals",
    }
    for spec in REGISTRY_COMMAND_SPECS:
        if spec.handler is None:
            continue
        assert spec.handler.target is not None
        assert resolve_deferred_target(spec.handler.target)
        assert spec.result_schema.target is not None
        assert resolve_deferred_target(spec.result_schema.target)


def test_registry_runtime_preserves_nested_and_repeated_contracts() -> None:
    app = build_command_subtree(_graph(), "app_registry")

    filed = CliRunner().invoke(app, ["verify-filed-state", "--help"])
    manual = CliRunner().invoke(app, ["manuals", "view", "--help"])

    assert filed.exit_code == 0, filed.output
    assert "--source-observation" in filed.output and "--casilla" in filed.output
    assert manual.exit_code == 0, manual.output
    assert "--manual <renta|iva|sociedades>" in manual.output
