"""Shared execution-policy declarations for the ledger CommandSpec subtree."""

from __future__ import annotations

from cadrumo_client.commands.spec import ExecutionPolicySpec
from cadrumo_client.contracts.command_ports import CommandWriteRoute

POLICY_1 = ExecutionPolicySpec(
    capabilities=frozenset(("state-free",)),
    side_effects=frozenset(("none",)),
    performance="metadata",
    write_route=CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
    live_write=False,
)
POLICY_2 = ExecutionPolicySpec(
    capabilities=frozenset(("encrypted-facts", "network")),
    side_effects=frozenset(("local-state", "network")),
    performance="external-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
    live_write=False,
)
POLICY_3 = ExecutionPolicySpec(
    capabilities=frozenset(("calculation", "encrypted-facts")),
    side_effects=frozenset(("local-state",)),
    performance="compute",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
    live_write=False,
)
POLICY_4 = ExecutionPolicySpec(
    capabilities=frozenset(("encrypted-facts",)),
    side_effects=frozenset(("local-state",)),
    performance="local-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
    live_write=False,
)
POLICY_5 = ExecutionPolicySpec(
    capabilities=frozenset(("encrypted-facts",)),
    side_effects=frozenset(("none",)),
    performance="local-io",
    write_route=CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
    live_write=False,
)
POLICY_6 = ExecutionPolicySpec(
    capabilities=frozenset(("calculation", "encrypted-facts")),
    side_effects=frozenset(("none",)),
    performance="compute",
    write_route=CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
    live_write=False,
)
POLICY_7 = ExecutionPolicySpec(
    capabilities=frozenset(("calculation", "encrypted-facts", "network")),
    side_effects=frozenset(("local-state", "network")),
    performance="external-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
    live_write=False,
)
POLICY_9 = ExecutionPolicySpec(
    capabilities=frozenset(("encrypted-facts",)),
    side_effects=frozenset(("local-state",)),
    performance="local-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=True,
    handoff=False,
    live_write=False,
)
POLICY_10 = ExecutionPolicySpec(
    capabilities=frozenset(("encrypted-facts", "filing")),
    side_effects=frozenset(("local-state",)),
    performance="local-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=True,
    live_write=False,
)

__all__ = [
    "POLICY_1",
    "POLICY_2",
    "POLICY_3",
    "POLICY_4",
    "POLICY_5",
    "POLICY_6",
    "POLICY_7",
    "POLICY_9",
    "POLICY_10",
]
