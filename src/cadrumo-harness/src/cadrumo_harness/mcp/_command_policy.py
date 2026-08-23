"""MCP projections of immutable, CommandSpec-owned execution policy."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from cadrumo.entrypoints.cli.command_api import CommandExecutionPolicy

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class CommandPolicyProjection(BaseModel):
    """SDK-independent MCP view of one spec-owned execution policy."""

    model_config = _STRICT_FROZEN

    command_key: str
    read_only: bool
    destructive: bool
    idempotent: bool
    handoff: bool
    live_write: bool
    open_world: bool


def project_command_policy(command_key: str, raw_policy: CommandExecutionPolicy) -> CommandPolicyProjection:
    """Project one already-resolved CommandSpec policy for MCP consumers."""
    if not isinstance(raw_policy, CommandExecutionPolicy):
        raise TypeError("CLI policy resolver returned an invalid policy")
    classification = raw_policy.classification
    effects = classification.side_effects
    read_only = effects == frozenset({"none"})
    return CommandPolicyProjection(
        command_key=command_key,
        read_only=read_only,
        destructive=raw_policy.destructive,
        idempotent=read_only,
        handoff=raw_policy.handoff,
        live_write=raw_policy.live_write,
        open_world="network" in classification.expanded_capabilities,
    )


def command_policy(command_key: str) -> CommandPolicyProjection:
    """Return policy from the already materialised live MCP descriptor set.

    This convenience is for descriptor-oriented inspection and tests. It never
    resolves a CLI path or carries a second policy map; unknown keys fail.
    Runtime gates receive ``descriptor.execution_policy`` directly.
    """
    from ._tools import build_tool_descriptors

    descriptor = next(
        (item for item in build_tool_descriptors() if item.command_key == command_key),
        None,
    )
    if descriptor is None:
        raise LookupError(f"no live MCP descriptor for command key {command_key!r}")
    return descriptor.execution_policy


def policy_projection_is_coherent(policy: CommandPolicyProjection) -> bool:
    """Return whether MCP-facing policy axes are mutually consistent."""
    if policy.read_only and policy.destructive:
        return False
    if policy.read_only and not policy.idempotent:
        return False
    return not (policy.read_only and policy.live_write)


__all__ = [
    "CommandPolicyProjection",
    "command_policy",
    "policy_projection_is_coherent",
    "project_command_policy",
]
