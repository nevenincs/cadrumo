"""Live-tree gates for config-owned execution declarations."""

from __future__ import annotations

import pytest
import typer
from typer.testing import CliRunner

from ... import app
from ..._command_suggestions import CadrumoTyperGroup, walk_live_command_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _config_nodes():
    return tuple(node for node in walk_live_command_tree(app) if len(node.path) > 1 and node.path[1] == "config")


def test_every_live_config_node_owns_an_execution_policy() -> None:
    nodes = _config_nodes()

    assert nodes
    assert len({node.path for node in nodes}) == len(nodes)
    assert all(node.execution_policy is not None for node in nodes)


def test_config_policy_gate_bites_for_an_external_unclassified_node() -> None:
    probe = typer.Typer(name="policy-negative", cls=CadrumoTyperGroup)

    @probe.command("missing")
    def missing() -> None:
        return None

    @probe.command("sibling")
    def sibling() -> None:
        return None

    nodes = walk_live_command_tree(probe)

    missing_node = next(node for node in nodes if node.path == ("policy-negative", "missing"))
    assert missing_node.execution_policy is None


def test_metadata_group_callbacks_preserve_help_and_leaf_dispatch() -> None:
    runner = CliRunner()

    for args in (("config", "auth", "--help"), ("config", "profile", "--help"), ("config", "storage", "--help")):
        result = runner.invoke(app, list(args))
        assert result.exit_code == 0, result.output
        assert "Usage:" in result.output

    result = runner.invoke(app, ["config", "profile", "list", "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output

    for args in (("config", "auth"), ("config", "profile"), ("config", "storage"), ("config", "google", "sync")):
        result = runner.invoke(app, list(args))
        assert result.exit_code == 2, result.output
        assert "Usage:" in result.output


def test_representative_config_nodes_declare_specialised_authorities() -> None:
    by_path = {node.path: node for node in _config_nodes()}

    preflight = by_path[("aeat", "config", "profile", "preflight")].execution_policy
    registry_repair = by_path[("aeat", "config", "repair", "integrity", "registry")].execution_policy
    connectivity = by_path[("aeat", "config", "repair", "connectivity")].execution_policy
    calc_export = by_path[("aeat", "config", "google", "sync", "calc", "export")].execution_policy
    assert preflight is not None and {"registry", "calculation"} <= preflight.classification.expanded_capabilities
    assert registry_repair is not None and {"registry", "calculation"} <= (
        registry_repair.classification.expanded_capabilities
    )
    assert "encrypted-facts" not in registry_repair.classification.expanded_capabilities
    assert registry_repair.classification.side_effects == frozenset({"none"})
    assert registry_repair.write_route == "none"
    assert connectivity is not None and {"network", "browser"} <= connectivity.classification.expanded_capabilities
    assert calc_export is not None and {"google", "calculation", "filing"} <= (
        calc_export.classification.expanded_capabilities
    )
    assert calc_export.handoff
