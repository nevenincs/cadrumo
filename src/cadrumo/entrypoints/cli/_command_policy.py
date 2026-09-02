"""Import-light immutable execution-policy value facade.

Executable policy authority lives in the command graph.  This module retains
only the validated public value type used by graph consumers while the graph
transition completes; it does not attach metadata to behavior callables.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._command_schema import CommandCapabilityClass
from .command_spec import CommandWriteRouteValue

"""Storage route a state-mutating callback is permitted to use."""

_WRITE_ROUTE_SCOPES = frozenset({"none", "profile-bound", "bootstrap-root"})


@dataclass(frozen=True, slots=True)
class CommandExecutionPolicy:
    """Validated immutable execution declaration projected from a command graph."""

    classification: CommandCapabilityClass
    write_route: CommandWriteRouteValue
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


__all__ = [
    "CommandExecutionPolicy",
]
