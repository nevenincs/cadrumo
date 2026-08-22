"""Focused contract tests for callback-attached command execution policy."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from .._command_policy import (
    CommandExecutionPolicy,
    CommandWriteRouteScope,
    command_execution_policy,
    execution_policy_for,
)
from .._command_schema import CommandCapability, CommandCapabilityClass, CommandSideEffectClass

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


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


def test_decorator_preserves_identity_and_rejects_a_second_policy() -> None:
    safe = CommandExecutionPolicy(
        classification=_classification(capabilities=frozenset({"state-free"}), side_effects=frozenset({"none"})),
        write_route="none",
    )
    mutating = CommandExecutionPolicy(
        classification=_classification(
            capabilities=frozenset({"profile-custody"}),
            side_effects=frozenset({"local-state"}),
        ),
        write_route="bootstrap-root",
    )

    def callback() -> None:
        pass

    decorated = command_execution_policy(safe)(callback)
    assert decorated is callback
    assert execution_policy_for(callback) is safe
    assert command_execution_policy(safe)(callback) is callback
    with pytest.raises(ValueError, match="different execution policy"):
        command_execution_policy(mutating)(callback)


def test_absence_and_corrupt_metadata_do_not_become_safe_defaults() -> None:
    def absent() -> None:
        pass

    assert execution_policy_for(absent) is None
    setattr(absent, "__cadrumo_command_execution_policy__", "not-a-policy")  # noqa: B010
    with pytest.raises(TypeError, match="invalid execution-policy metadata"):
        execution_policy_for(absent)
