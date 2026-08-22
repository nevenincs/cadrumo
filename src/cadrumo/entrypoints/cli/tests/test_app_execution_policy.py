"""Live-tree gates for the S51 application command partition."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
import typer
from typer.testing import CliRunner

from .. import app
from .._app_execution_policies import (
    BROWSER_SUBPROCESS_LIVE_PROFILE_WRITE,
    ENCRYPTED_READ,
    LIVE_PROFILE_WRITE,
    LOCAL_STORAGE_READ,
    METADATA,
    PROFILE_LOCAL_DESTRUCTIVE,
    QUICKFILE_HANDOFF,
)
from .._command_policy import command_execution_policy
from .._command_suggestions import CadrumoTyperGroup, LiveCommandNode, walk_live_command_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FAMILIES = frozenset({"live", "diagnostics", "maintenance", "review", "overview", "registry", "quickfile"})


def _nodes() -> tuple[LiveCommandNode, ...]:
    return tuple(
        node
        for node in walk_live_command_tree(app)
        if len(node.path) >= 3 and node.path[:2] == ("aeat", "app") and node.path[2] in _FAMILIES
    )


def test_exact_remaining_app_partition_is_live_derived_and_fully_classified() -> None:
    nodes = _nodes()

    assert {node.path[2] for node in nodes} == _FAMILIES
    assert len({node.path for node in nodes}) == len(nodes)
    assert all(node.execution_policy is not None for node in nodes)


def test_remaining_app_policy_gate_bites_for_external_unclassified_node() -> None:
    probe = typer.Typer(name="remaining-app-negative", cls=CadrumoTyperGroup)

    @probe.callback()
    @command_execution_policy(METADATA)
    def root() -> None:
        return None

    @probe.command("missing")
    def missing() -> None:
        return None

    node = next(node for node in walk_live_command_tree(probe) if node.path[-1] == "missing")
    assert node.execution_policy is None


def test_maximum_effect_and_risk_judgments_are_not_downgraded() -> None:
    by_path = {node.path: node.execution_policy for node in _nodes()}

    assert by_path[("aeat", "app", "live", "expedientes", "pull")] == LIVE_PROFILE_WRITE
    assert by_path[("aeat", "app", "live", "expedientes", "list")] == ENCRYPTED_READ
    assert by_path[("aeat", "app", "live", "iva-wallet", "pull-evidence")] == (
        BROWSER_SUBPROCESS_LIVE_PROFILE_WRITE
    )
    assert by_path[("aeat", "app", "live", "portals", "list")] == METADATA
    assert by_path[("aeat", "app", "diagnostics", "runs")] == LOCAL_STORAGE_READ
    assert by_path[("aeat", "app", "maintenance", "reconcile")] == PROFILE_LOCAL_DESTRUCTIVE
    assert by_path[("aeat", "app", "quickfile")] == QUICKFILE_HANDOFF

    probe = typer.Typer(name="remaining-app-downgrade", cls=CadrumoTyperGroup)

    @probe.callback()
    @command_execution_policy(METADATA)
    def root() -> None:
        return None

    @probe.command("pull")
    @command_execution_policy(ENCRYPTED_READ)
    def pull() -> None:
        return None

    policy = next(node.execution_policy for node in walk_live_command_tree(probe) if node.path[-1] == "pull")
    with pytest.raises(AssertionError):
        assert policy is not None and {"network", "encrypted-facts"} <= policy.classification.expanded_capabilities


def test_policy_presets_import_without_application_or_registry_graphs() -> None:
    code = """
import json, sys
import cadrumo.entrypoints.cli
before = set(sys.modules)
import cadrumo.entrypoints.cli._app_execution_policies
loaded = set(sys.modules) - before
print(json.dumps(sorted(name for name in loaded if name.startswith('cadrumo.application') or name.startswith('cadrumo.domain.registry'))))
"""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and in-tree code.
        [sys.executable, "-I", "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == []


def test_remaining_group_help_and_executable_quickfile_behavior_survive() -> None:
    runner = CliRunner()
    for args in (("app", "live", "--help"), ("app", "diagnostics", "--help"), ("app", "registry", "--help")):
        result = runner.invoke(app, list(args))
        assert result.exit_code == 0, result.output
        assert "Usage:" in result.output

    result = runner.invoke(app, ["app", "quickfile", "--help"])
    assert result.exit_code == 0, result.output
    assert "--modelo" in result.output
