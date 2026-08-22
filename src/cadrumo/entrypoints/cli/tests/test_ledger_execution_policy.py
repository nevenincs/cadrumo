"""Live-tree execution-policy gates for the complete ledger subtree."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
import typer
from typer.testing import CliRunner

from ....tests import REPO_ROOT
from .. import app
from .._command_policy import CommandExecutionPolicy, command_execution_policy
from .._command_suggestions import CadrumoTyperGroup, walk_live_command_tree
from .._ledger_execution_policies import LEDGER_WRITE

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _ledger_nodes():
    return tuple(
        node
        for node in walk_live_command_tree(app)
        if len(node.path) > 2 and node.path[:3] == ("aeat", "app", "ledger")
    )


def _assert_network_profile_write(policy: CommandExecutionPolicy | None) -> None:
    assert policy is not None
    assert {"network", "encrypted-facts"} <= policy.classification.expanded_capabilities
    assert policy.classification.side_effects == frozenset({"network", "local-state"})
    assert policy.write_route == "profile-bound"


def test_every_live_ledger_node_owns_an_execution_policy() -> None:
    nodes = _ledger_nodes()

    assert nodes
    assert len({node.path for node in nodes}) == len(nodes)
    assert all(node.execution_policy is not None for node in nodes)


def test_ledger_policy_gate_bites_for_an_external_unclassified_node() -> None:
    probe = typer.Typer(name="ledger-policy-negative", cls=CadrumoTyperGroup)

    @probe.command("missing")
    def missing() -> None:
        return None

    @probe.command("sibling")
    def sibling() -> None:
        return None

    missing_node = next(
        node for node in walk_live_command_tree(probe) if node.path == ("ledger-policy-negative", "missing")
    )
    assert missing_node.execution_policy is None


def test_ledger_risk_and_route_judgments_live_on_callbacks() -> None:
    by_path = {node.path: node for node in _ledger_nodes()}

    for suffix in (
        ("evidence", "remove"),
        ("invoice", "remove"),
        ("merge",),
        ("remove",),
        ("reset",),
        ("stash",),
    ):
        policy = by_path[("aeat", "app", "ledger", *suffix)].execution_policy
        assert policy is not None and policy.destructive
        assert policy.write_route == "profile-bound"

    export = by_path[("aeat", "app", "ledger", "export")].execution_policy
    assert export is not None and export.handoff
    assert "filing" in export.classification.expanded_capabilities
    assert export.write_route == "profile-bound"

    participation = by_path[("aeat", "app", "ledger", "participation")].execution_policy
    assert participation is not None
    assert "encrypted-facts" in participation.classification.expanded_capabilities
    assert participation.classification.side_effects == frozenset({"none"})

    for suffix in (("classify",), ("split",)):
        conditional = by_path[("aeat", "app", "ledger", *suffix)].execution_policy
        assert conditional is not None
        assert {"network", "calculation", "encrypted-facts"} <= conditional.classification.expanded_capabilities
        assert conditional.classification.side_effects == frozenset({"network", "local-state"})

    for suffix in (
        ("add",),
        ("import",),
        ("invoice", "add"),
        ("invoice", "import"),
        ("invoice", "wizard"),
        ("evidence", "confirm"),
        ("evidence", "consent", "rederive"),
    ):
        conditional = by_path[("aeat", "app", "ledger", *suffix)].execution_policy
        _assert_network_profile_write(conditional)

    doclink = by_path[("aeat", "app", "ledger", "doclink")].execution_policy
    assert doclink is not None
    assert {"google", "network", "encrypted-facts"} <= doclink.classification.expanded_capabilities
    assert doclink.classification.side_effects == frozenset({"google", "local-state"})
    assert doclink.write_route == "profile-bound"


def test_network_maximum_gate_bites_for_an_external_downgraded_callback() -> None:
    probe = typer.Typer(name="ledger-network-downgrade", cls=CadrumoTyperGroup)

    @probe.command("downgraded")
    @command_execution_policy(LEDGER_WRITE)
    def downgraded() -> None:
        return None

    @probe.command("sibling")
    @command_execution_policy(LEDGER_WRITE)
    def sibling() -> None:
        return None

    downgraded_node = next(
        node for node in walk_live_command_tree(probe) if node.path == ("ledger-network-downgrade", "downgraded")
    )
    with pytest.raises(AssertionError):
        _assert_network_profile_write(downgraded_node.execution_policy)


def test_ledger_group_callbacks_preserve_runner_help_and_bare_invocation() -> None:
    runner = CliRunner()

    for args in (
        ("app", "ledger", "--help"),
        ("app", "ledger", "evidence", "--help"),
        ("app", "ledger", "inventory", "movement", "--help"),
    ):
        result = runner.invoke(app, list(args))
        assert result.exit_code == 0, result.output
        assert "Usage:" in result.output

    bare = runner.invoke(app, ["app", "ledger", "evidence"])
    assert bare.exit_code == 2, bare.output
    assert "Usage:" in bare.output

    executable = runner.invoke(app, ["app", "ledger", "participation"])
    assert executable.exit_code == 0, executable.output
    assert "Usage:" in executable.output


def test_ledger_group_help_survives_a_real_process() -> None:
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    env.update({"CADRUMO_OUTPUT_LANGUAGE": "en", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    code = (
        'import sys; sys.argv=["aeat","app","ledger","evidence","--help"]; '
        "from cadrumo.entrypoints.cli import main; main()"
    )

    completed = subprocess.run(  # noqa: S603 - fixed interpreter and in-tree command arguments.
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=120.0,
    )

    output = f"{completed.stdout}\n{completed.stderr}"
    assert completed.returncode == 0, output
    assert "Usage:" in output
    assert "Traceback" not in output
