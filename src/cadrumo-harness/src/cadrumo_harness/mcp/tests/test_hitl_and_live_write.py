"""Tests for the HITL confirmation tiers and the never-expose-live-write rail."""

from __future__ import annotations

import pytest

from .._command_policy import CommandPolicyProjection
from .._hitl import ConfirmationPolicy, confirmation_for_policy, confirmation_for_tool
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _decision(command_key: str) -> ConfirmationPolicy:
    return confirmation_for_tool(command_key=command_key)


def test_read_only_tools_auto_approve() -> None:
    assert _decision("overview.status") is ConfirmationPolicy.AUTO_APPROVE
    assert _decision("registry.inspect") is ConfirmationPolicy.AUTO_APPROVE
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
    # Defensive: if an attached callback policy ever declares live_write, the
    # gate blocks it outright. This proves the
    # BLOCK rail is real, not vacuous.
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


def test_an_unclassified_key_is_refused_not_auto_approved() -> None:
    # The permissive classification default makes an unknown key classify
    # all-false, which without grounding reaches AUTO_APPROVE - a future caller
    # passing an unvalidated key would silently auto-approve a mutation. The gate
    # grounds its auto-approve path against the live descriptor set, so a key that
    # names no exposed command is refused rather than auto-approved.
    bogus_key = "totally.bogus.unclassified.key"
    assert bogus_key not in {descriptor.command_key for descriptor in build_tool_descriptors()}
    with pytest.raises(LookupError):
        confirmation_for_tool(command_key=bogus_key)


def test_grounding_still_auto_approves_real_exposed_commands() -> None:
    # Counterpart to the refusal above: the grounding must not refuse a genuine
    # exposed command whose classification is auto-approve. Real read and
    # non-destructive-mutation descriptors still auto-approve, so the refusal is
    # scoped to unclassified keys, not the whole auto-approve tier.
    for command_key in ("registry.inspect", "overview.status", "ledger.add"):
        assert command_key in {descriptor.command_key for descriptor in build_tool_descriptors()}
        assert confirmation_for_tool(command_key=command_key) is ConfirmationPolicy.AUTO_APPROVE
