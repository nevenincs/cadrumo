"""Focused contracts for immutable command execution-policy values."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import cast

import pytest

from .._command_policy import (
    CommandExecutionPolicy,
    CommandWriteRouteScope,
)
from .._command_schema import CommandCapability, CommandCapabilityClass, CommandSideEffectClass

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_callback_policy_attachment_authority_is_physically_absent() -> None:
    cli_root = Path(__file__).parents[1]
    policy_source = (cli_root / "_command_policy.py").read_text(encoding="utf-8")
    suggestions_source = (cli_root / "_command_suggestions.py").read_text(encoding="utf-8")
    forbidden = {"command_execution_policy", "execution_policy_for"}
    violations: list[str] = []
    for path in sorted(cli_root.rglob("*.py")):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in forbidden:
                violations.append(f"{path}:{node.lineno}: function {node.name}")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    if alias.name in forbidden:
                        violations.append(f"{path}:{node.lineno}: import {alias.name}")
            if isinstance(node, ast.Constant) and node.value == "__cadrumo_command_execution_policy__":
                violations.append(f"{path}:{node.lineno}: callback attribute")
    assert violations == []
    assert "execution_policy_for" not in suggestions_source
    assert "callback-attached" not in policy_source


def _classification(
    *,
    capabilities: frozenset[str],
    side_effects: frozenset[str],
) -> CommandCapabilityClass:
    return CommandCapabilityClass(
        capabilities=cast("frozenset[CommandCapability]", capabilities),
        side_effects=cast("frozenset[CommandSideEffectClass]", side_effects),
        performance="metadata",
    )


def test_policy_is_immutable_and_preserves_explicit_safe_judgments() -> None:
    policy = CommandExecutionPolicy(
        classification=_classification(capabilities=frozenset({"state-free"}), side_effects=frozenset({"none"})),
        write_route="none",
    )

    assert not policy.destructive
    assert not policy.handoff
    assert not policy.live_write
    with pytest.raises(FrozenInstanceError):
        policy.destructive = True  # ty: ignore[invalid-assignment]


@pytest.mark.parametrize(
    ("capabilities", "effects", "write_route", "destructive", "handoff", "live_write", "message"),
    [
        ({"state-free"}, {"none"}, "elsewhere", False, False, False, "unknown"),
        ({"state-free"}, {"none"}, "profile-bound", False, False, False, "write-route"),
        ({"registry"}, {"local-state"}, "bootstrap-root", False, False, False, "profile-custody"),
        ({"profile-custody"}, {"none"}, "none", True, False, False, "destructive"),
        ({"registry"}, {"local-state"}, "none", False, True, False, "handoff"),
        ({"filing"}, {"none"}, "none", False, True, False, "local-state"),
        ({"network"}, {"none"}, "none", False, False, True, "side effect"),
    ],
)
def test_policy_rejects_contradictory_execution_judgments(
    capabilities: set[str],
    effects: set[str],
    write_route: str,
    destructive: bool,
    handoff: bool,
    live_write: bool,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CommandExecutionPolicy(
            classification=_classification(
                capabilities=frozenset(capabilities),
                side_effects=frozenset(effects),
            ),
            write_route=cast("CommandWriteRouteScope", write_route),
            destructive=destructive,
            handoff=handoff,
            live_write=live_write,
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"classification": "not-a-classification"}, "CommandCapabilityClass"),
        ({"destructive": 1}, "destructive must be a bool"),
        ({"handoff": "false"}, "handoff must be a bool"),
        ({"live_write": None}, "live_write must be a bool"),
    ],
)
def test_policy_rejects_runtime_type_coercion(overrides: dict[str, object], message: str) -> None:
    values: dict[str, object] = {
        "classification": _classification(
            capabilities=frozenset({"state-free"}),
            side_effects=frozenset({"none"}),
        ),
        "write_route": "none",
    }
    values.update(overrides)
    with pytest.raises(TypeError, match=message):
        CommandExecutionPolicy(**values)  # ty: ignore[invalid-argument-type]
