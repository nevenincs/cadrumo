"""Tests for the HITL confirmation tiers and the never-expose-live-write rail."""

from __future__ import annotations

import pytest

from ....application.operator_surface import OperatorMutability
from .._annotations import McpAnnotations, annotations_for_command
from .._hitl import ConfirmationPolicy, confirmation_for_tool
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _decision(command_key: str) -> ConfirmationPolicy:
    by_key = {d.command_key: d for d in build_tool_descriptors()}
    descriptor = by_key[command_key]
    return confirmation_for_tool(command_key=command_key, annotations=descriptor.annotations)


def test_read_only_tools_auto_approve() -> None:
    assert _decision("overview.status") is ConfirmationPolicy.AUTO_APPROVE
    assert _decision("contract") is ConfirmationPolicy.AUTO_APPROVE
    assert _decision("registry.inspect") is ConfirmationPolicy.AUTO_APPROVE


def test_non_destructive_local_mutation_auto_approves() -> None:
    assert _decision("ledger.add") is ConfirmationPolicy.AUTO_APPROVE
    assert _decision("modelo.work.calculate") is ConfirmationPolicy.AUTO_APPROVE


def test_destructive_and_handoff_require_confirmation() -> None:
    assert _decision("ledger.remove") is ConfirmationPolicy.CONFIRM
    assert _decision("ledger.reset") is ConfirmationPolicy.CONFIRM
    assert _decision("modelo.export") is ConfirmationPolicy.CONFIRM
    assert _decision("modelo.work.file") is ConfirmationPolicy.CONFIRM


def test_no_exposed_tool_is_a_forbidden_live_write() -> None:
    # The live AEAT tree is read-only and live submission is permanently
    # forbidden, so no exposed tool may resolve to a BLOCK decision.
    for descriptor in build_tool_descriptors():
        decision = confirmation_for_tool(command_key=descriptor.command_key, annotations=descriptor.annotations)
        assert decision is not ConfirmationPolicy.BLOCK, descriptor.command_key


def test_a_hypothetical_live_write_would_be_blocked() -> None:
    # Defensive: if a live-write verb ever entered the command set, the gate
    # blocks it outright. This proves the BLOCK rail is real, not vacuous.
    annotations: McpAnnotations = annotations_for_command(
        command_key="modelo.work.submit",
        mutability=OperatorMutability.LOCAL_STATE_MUTATING,
        title="aeat app modelo work submit",
    )
    assert confirmation_for_tool(command_key="modelo.work.submit", annotations=annotations) is ConfirmationPolicy.BLOCK
