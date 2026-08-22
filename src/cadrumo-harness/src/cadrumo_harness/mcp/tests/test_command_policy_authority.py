"""Deletion and live-authority gates for MCP command execution policy."""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
from pathlib import Path

import pytest
import typer

from cadrumo.entrypoints.cli import cli_path_for_command_key, command_execution_policy_for_cli_path
from cadrumo.entrypoints.cli._command_suggestions import execution_policy_for_cli_path

from .._command_policy import CommandPolicyProjection, policy_projection_is_coherent, project_command_policy
from .._hitl import ConfirmationPolicy, confirmation_for_policy
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_every_exposed_descriptor_carries_its_live_policy_projection() -> None:
    descriptors = build_tool_descriptors()
    assert descriptors
    for descriptor in descriptors:
        assert cli_path_for_command_key(descriptor.command_key) == descriptor.verb_schema.cli_path
        assert policy_projection_is_coherent(descriptor.execution_policy)
        assert descriptor.annotations.destructive_hint is descriptor.execution_policy.destructive
        assert descriptor.annotations.read_only_hint is descriptor.execution_policy.read_only


def test_unknown_and_unclassified_paths_fail_closed() -> None:
    planted = typer.Typer(name="planted")

    @planted.callback()
    def root() -> None:
        pass

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


def test_policy_projection_is_invariant_under_key_rename() -> None:
    raw = command_execution_policy_for_cli_path(("app", "live", "expedientes", "pull"))
    original = project_command_policy("app.live.expedientes.pull", raw)
    renamed = project_command_policy("renamed.alias.without.path.semantics", raw)
    assert original.model_copy(update={"command_key": renamed.command_key}) == renamed


def test_descriptor_policy_consumption_imports_nothing() -> None:
    script = """
import json
import sys
from cadrumo_harness.mcp._hitl import confirmation_for_policy
from cadrumo_harness.mcp._tools import build_tool_descriptors
descriptors = build_tool_descriptors()
target = next(item for item in descriptors if item.command_key == 'config.profile.list')
before = set(sys.modules)
confirmation_for_policy(target.execution_policy)
print(json.dumps(sorted(set(sys.modules) - before)))
"""
    result = subprocess.run(  # noqa: S603 - fixed interpreter and literal probe
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


def test_key_to_path_projection_contains_identity_only() -> None:
    source = inspect.getsource(cli_path_for_command_key)
    forbidden_policy_fields = ("destructive", "handoff", "live_write", "capabilities", "side_effects")
    assert all(field not in source for field in forbidden_policy_fields)
