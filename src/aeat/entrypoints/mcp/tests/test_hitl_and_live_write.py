"""Tests for the HITL confirmation tiers and the never-expose-live-write rail."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

import pytest

from ....application.operator_surface import COMMAND_RISK, CommandRiskDeclaration
from .._hitl import ConfirmationPolicy, confirmation_for_tool
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _decision(command_key: str) -> ConfirmationPolicy:
    return confirmation_for_tool(command_key=command_key)


@contextlib.contextmanager
def _declared_live_write(command_key: str) -> Iterator[None]:
    """Declare ``command_key`` a live-write in the risk table for the test body.

    A live-write BLOCK now fires from the DECLARED risk table, not a leaf-name
    heuristic (ADR ``mcp-protocol-hardening`` H3): no real command declares
    ``live_write`` (never-submit is enforced as "no such tool exists"), so a test
    that exercises the defensive BLOCK branch must supply a declared live-write
    row and restore the table after - test data, not a mocked behaviour.
    """
    previous = COMMAND_RISK.get(command_key)
    COMMAND_RISK[command_key] = CommandRiskDeclaration(live_write=True)
    try:
        yield
    finally:
        if previous is None:
            COMMAND_RISK.pop(command_key, None)
        else:
            COMMAND_RISK[command_key] = previous


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
        decision = confirmation_for_tool(command_key=descriptor.command_key)
        assert decision is not ConfirmationPolicy.BLOCK, descriptor.command_key


def test_a_hypothetical_live_write_would_be_blocked() -> None:
    # Defensive: if a live-write verb ever entered the command set - declared
    # live_write in the risk table - the gate blocks it outright. This proves the
    # BLOCK rail is real, not vacuous.
    with _declared_live_write("modelo.work.submit"):
        assert confirmation_for_tool(command_key="modelo.work.submit") is ConfirmationPolicy.BLOCK
