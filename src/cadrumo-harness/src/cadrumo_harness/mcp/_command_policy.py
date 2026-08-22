"""MCP projections of callback-attached CLI execution policy.

The CLI callback is the sole command-risk authority. This module resolves a
registry schema key to its declared CLI path, asks the live Click tree for the
policy attached to that callback, and projects only the fields MCP needs.
"""

from __future__ import annotations

from functools import cache

from pydantic import BaseModel, ConfigDict

from cadrumo.entrypoints.cli import cli_path_for_command_key, command_execution_policy_for_cli_path
from cadrumo.entrypoints.cli._command_policy import CommandExecutionPolicy

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class CommandPolicyProjection(BaseModel):
    """SDK-independent MCP view of one live callback's execution policy."""

    model_config = _STRICT_FROZEN

    command_key: str
    read_only: bool
    destructive: bool
    idempotent: bool
    handoff: bool
    live_write: bool
    open_world: bool


@cache
def command_policy(command_key: str) -> CommandPolicyProjection:
    """Resolve ``command_key`` to its live callback policy or fail closed."""
    cli_path = cli_path_for_command_key(command_key)
    raw_policy = command_execution_policy_for_cli_path(cli_path)
    if not isinstance(raw_policy, CommandExecutionPolicy):
        raise TypeError("CLI policy resolver returned an invalid policy")
    effects = raw_policy.classification.side_effects
    read_only = effects == frozenset({"none"})
    return CommandPolicyProjection(
        command_key=command_key,
        read_only=read_only,
        destructive=raw_policy.destructive,
        idempotent=read_only,
        handoff=raw_policy.handoff,
        live_write=raw_policy.live_write,
        open_world=bool(effects.intersection({"network", "browser", "google"})),
    )


def policy_projection_is_coherent(policy: CommandPolicyProjection) -> bool:
    """Return whether MCP-facing policy axes are mutually consistent."""
    if policy.read_only and policy.destructive:
        return False
    if policy.read_only and not policy.idempotent:
        return False
    return not (policy.read_only and policy.live_write)


__all__ = ["CommandPolicyProjection", "command_policy", "policy_projection_is_coherent"]
