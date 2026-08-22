"""Deletion and live-authority gates for MCP command execution policy."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest
import typer

from cadrumo.entrypoints.cli._command_suggestions import execution_policy_for_cli_path

from .._command_policy import CommandPolicyProjection, command_policy, policy_projection_is_coherent
from .._hitl import ConfirmationPolicy, confirmation_for_policy
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_every_exposed_descriptor_carries_its_live_policy_projection() -> None:
    descriptors = build_tool_descriptors()
    assert descriptors
    for descriptor in descriptors:
        assert descriptor.execution_policy is command_policy(descriptor.command_key)
        assert policy_projection_is_coherent(descriptor.execution_policy)
        assert descriptor.annotations.destructive_hint is descriptor.execution_policy.destructive
        assert descriptor.annotations.read_only_hint is descriptor.execution_policy.read_only


def test_unknown_and_unclassified_paths_fail_closed() -> None:
    with pytest.raises(LookupError):
        command_policy("planted.absent.command")

    planted = typer.Typer(name="planted")

    @planted.command("missing")
    def missing() -> None:
        pass

    with pytest.raises(LookupError, match="no execution policy"):
        execution_policy_for_cli_path(planted, ("missing",))


def test_live_write_detector_bites_on_a_planted_policy() -> None:
    planted = CommandPolicyProjection(
        command_key="planted.live.submit",
        read_only=False,
        destructive=False,
        idempotent=False,
        handoff=False,
        live_write=True,
        open_world=True,
    )
    assert confirmation_for_policy(planted) is ConfirmationPolicy.BLOCK


def test_targeted_config_resolution_does_not_import_app_sibling_families() -> None:
    script = """
import json
import sys
from cadrumo_harness.mcp._command_policy import command_policy
command_policy('config.profile.list')
blocked = (
    'cadrumo.entrypoints.cli._ledger',
    'cadrumo.entrypoints.cli._modelo',
    'cadrumo.entrypoints.cli._app_live',
)
print(json.dumps([name for name in blocked if name in sys.modules]))
"""
    result = subprocess.run(  # noqa: S603 - fixed interpreter and in-repo literal probe
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "[]"


def test_legacy_keyed_policy_authority_is_physically_absent() -> None:
    repository = Path(__file__).resolve().parents[6]
    old_module = repository / "src" / "cadrumo" / "application" / "operator_surface" / ("_risk" + "_table.py")
    assert not old_module.exists()

    banned = (
        "COMMAND" + "_RISK",
        "CommandRisk" + "Declaration",
        "declared" + "_risk",
        "application.operator_surface." + "_risk_table",
    )
    roots = (repository / "src" / "cadrumo", repository / "src" / "cadrumo-harness" / "src")
    offenders: list[str] = []
    for root in roots:
        for source in root.rglob("*.py"):
            if source == Path(__file__):
                continue
            text = source.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(source))
            strings = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
            if any(token in text or any(token in value for value in strings) for token in banned):
                offenders.append(str(source.relative_to(repository)))
    assert offenders == []
