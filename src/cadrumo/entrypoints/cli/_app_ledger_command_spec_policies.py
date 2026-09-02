"""Shared execution-policy declarations for the ledger CommandSpec subtree."""

from __future__ import annotations

from .command_spec import CommandWriteRoute, ExecutionPolicySpec

_POLICY_1 = ExecutionPolicySpec(
    capabilities=frozenset(("state-free",)),
    side_effects=frozenset(("none",)),
    performance="metadata",
    write_route=CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
    live_write=False,
)
_POLICY_2 = ExecutionPolicySpec(
    capabilities=frozenset(("encrypted-facts", "network")),
    side_effects=frozenset(("local-state", "network")),
    performance="external-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
    live_write=False,
)
_POLICY_3 = ExecutionPolicySpec(
    capabilities=frozenset(("calculation", "encrypted-facts")),
    side_effects=frozenset(("local-state",)),
    performance="compute",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
    live_write=False,
)
_POLICY_4 = ExecutionPolicySpec(
    capabilities=frozenset(("encrypted-facts",)),
    side_effects=frozenset(("local-state",)),
    performance="local-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
    live_write=False,
)
_POLICY_5 = ExecutionPolicySpec(
    capabilities=frozenset(("encrypted-facts",)),
    side_effects=frozenset(("none",)),
    performance="local-io",
    write_route=CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
    live_write=False,
)
_POLICY_6 = ExecutionPolicySpec(
    capabilities=frozenset(("calculation", "encrypted-facts")),
    side_effects=frozenset(("none",)),
    performance="compute",
    write_route=CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
    live_write=False,
)
_POLICY_7 = ExecutionPolicySpec(
    capabilities=frozenset(("calculation", "encrypted-facts", "network")),
    side_effects=frozenset(("local-state", "network")),
    performance="external-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
    live_write=False,
)
_POLICY_8 = ExecutionPolicySpec(
    capabilities=frozenset(("encrypted-facts", "google")),
    side_effects=frozenset(("google", "local-state")),
    performance="external-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
    live_write=False,
)
_POLICY_9 = ExecutionPolicySpec(
    capabilities=frozenset(("encrypted-facts",)),
    side_effects=frozenset(("local-state",)),
    performance="local-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=True,
    handoff=False,
    live_write=False,
)
_POLICY_10 = ExecutionPolicySpec(
    capabilities=frozenset(("encrypted-facts", "filing")),
    side_effects=frozenset(("local-state",)),
    performance="local-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=True,
    live_write=False,
)

__all__ = [
    "_POLICY_1",
    "_POLICY_2",
    "_POLICY_3",
    "_POLICY_4",
    "_POLICY_5",
    "_POLICY_6",
    "_POLICY_7",
    "_POLICY_8",
    "_POLICY_9",
    "_POLICY_10",
]
