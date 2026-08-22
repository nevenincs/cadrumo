"""Import-light execution policy attached to CLI callbacks.

The callback is the command's executable authority.  Policy metadata therefore
lives on that callable rather than in a command-path table: aliases and lazy
materialisation retain the same declaration, while an unannotated callback is
truthfully visible as unclassified.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeVar, cast

from ._command_schema import CommandCapabilityClass

CommandWriteRouteScope = Literal["none", "profile-bound", "bootstrap-root"]
"""Storage route a state-mutating callback is permitted to use."""

_POLICY_ATTRIBUTE = "__cadrumo_command_execution_policy__"
_WRITE_ROUTE_SCOPES = frozenset({"none", "profile-bound", "bootstrap-root"})


@dataclass(frozen=True, slots=True)
class CommandExecutionPolicy:
    """Complete execution declaration owned by one command callback.

    False risk values are meaningful only because the record itself is
    explicitly attached.  Absence is represented by ``None`` at census time;
    it is never coerced into an apparently safe policy.
    """

    classification: CommandCapabilityClass
    write_route: CommandWriteRouteScope
    destructive: bool = False
    handoff: bool = False
    live_write: bool = False

    def __post_init__(self) -> None:
        """Reject policies whose judgments contradict execution effects."""
        if not isinstance(self.classification, CommandCapabilityClass):
            raise TypeError("command policy classification must be a CommandCapabilityClass")
        for field_name in ("destructive", "handoff", "live_write"):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"command policy {field_name} must be a bool")
        if not isinstance(self.write_route, str) or self.write_route not in _WRITE_ROUTE_SCOPES:
            raise ValueError(f"unknown command write-route scope: {self.write_route}")
        effects = self.classification.side_effects
        capabilities = self.classification.expanded_capabilities
        mutates_local_state = "local-state" in effects
        if self.write_route != "none" and not mutates_local_state:
            raise ValueError("a command write-route scope requires the local-state side effect")
        if self.write_route != "none" and "profile-custody" not in capabilities:
            raise ValueError("a command storage write-route scope requires the profile-custody capability")
        if self.destructive and not mutates_local_state:
            raise ValueError("a destructive command requires the local-state side effect")
        if self.handoff and "filing" not in capabilities:
            raise ValueError("a filing handoff requires the filing capability")
        if self.handoff and not mutates_local_state:
            raise ValueError("a filing handoff requires the local-state side effect")
        if self.live_write and "network" not in capabilities:
            raise ValueError("a live write requires the network capability")
        if self.live_write and "network" not in effects and "browser" not in effects:
            raise ValueError("a live write requires a network or browser side effect")


_Callback = TypeVar("_Callback", bound=Callable[..., object])


def command_execution_policy(policy: CommandExecutionPolicy) -> Callable[[_Callback], _Callback]:
    """Attach ``policy`` to a Typer command or group callback.

    Typer registration decorators retain the callback object until Click
    materialisation, so this decorator is order-independent: it may appear
    immediately above or below ``@app.command`` / ``@app.callback``.  The
    callable is returned unchanged, preserving handler identity and signature.

    Reapplying the same immutable policy is idempotent.  A different policy on
    the same callback is a contradictory declaration and fails at import time.
    """
    if not isinstance(policy, CommandExecutionPolicy):
        raise TypeError("command execution policy must be a CommandExecutionPolicy")

    def attach(callback: _Callback) -> _Callback:
        existing = getattr(callback, _POLICY_ATTRIBUTE, None)
        if existing is not None and existing != policy:
            raise ValueError("command callback already has a different execution policy")
        setattr(callback, _POLICY_ATTRIBUTE, policy)
        return callback

    return attach


def execution_policy_for(callback: object | None) -> CommandExecutionPolicy | None:
    """Return directly attached callback policy, preserving honest absence."""
    if callback is None:
        return None
    policy = getattr(callback, _POLICY_ATTRIBUTE, None)
    if policy is None:
        return None
    if not isinstance(policy, CommandExecutionPolicy):
        raise TypeError("command callback carries invalid execution-policy metadata")
    return cast(CommandExecutionPolicy, policy)


__all__ = [
    "CommandExecutionPolicy",
    "CommandWriteRouteScope",
    "command_execution_policy",
    "execution_policy_for",
]
