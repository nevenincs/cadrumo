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


def _validate_classification(classification: object) -> None:
    """Require the graph-derived capability/effect classification value."""
    if not isinstance(classification, CommandCapabilityClass):
        raise TypeError("command policy classification must be a CommandCapabilityClass")


def _validate_risk_flags(destructive: object, handoff: object, live_write: object) -> None:
    """Require strict booleans for mutation, filing, and live-write judgments."""
    for field_name, value in (
        ("destructive", destructive),
        ("handoff", handoff),
        ("live_write", live_write),
    ):
        if not isinstance(value, bool):
            raise TypeError(f"command policy {field_name} must be a bool")


def _validate_write_route_value(write_route: object) -> None:
    """Require a storage route to use the command graph vocabulary."""
    if not isinstance(write_route, str) or write_route not in _WRITE_ROUTE_SCOPES:
        raise ValueError(f"unknown command write-route scope: {write_route}")


def _validate_write_route_requirements(
    write_route: CommandWriteRouteValue,
    side_effects: frozenset[str],
    capabilities: frozenset[str],
) -> None:
    """Require storage routes to declare local state and profile custody."""
    if write_route == "none":
        return
    if "local-state" not in side_effects:
        raise ValueError("a command write-route scope requires the local-state side effect")
    if "profile-custody" not in capabilities:
        raise ValueError("a command storage write-route scope requires the profile-custody capability")


def _validate_destructive(destructive: bool, side_effects: frozenset[str]) -> None:
    """Require destructive commands to declare a local-state effect."""
    if destructive and "local-state" not in side_effects:
        raise ValueError("a destructive command requires the local-state side effect")


def _validate_handoff(handoff: bool, capabilities: frozenset[str], side_effects: frozenset[str]) -> None:
    """Require filing handoffs to carry filing authority and local-state effects."""
    if handoff and "filing" not in capabilities:
        raise ValueError("a filing handoff requires the filing capability")
    if handoff and "local-state" not in side_effects:
        raise ValueError("a filing handoff requires the local-state side effect")


def _validate_live_write(live_write: bool, capabilities: frozenset[str], side_effects: frozenset[str]) -> None:
    """Require live writes to carry network authority and a network/browser effect."""
    if live_write and "network" not in capabilities:
        raise ValueError("a live write requires the network capability")
    if live_write and not side_effects.intersection({"network", "browser"}):
        raise ValueError("a live write requires a network or browser side effect")


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
        _validate_classification(self.classification)
        _validate_risk_flags(self.destructive, self.handoff, self.live_write)
        _validate_write_route_value(self.write_route)
        effects = self.classification.side_effects
        capabilities = self.classification.expanded_capabilities
        _validate_write_route_requirements(self.write_route, effects, capabilities)
        _validate_destructive(self.destructive, effects)
        _validate_handoff(self.handoff, capabilities, effects)
        _validate_live_write(self.live_write, capabilities, effects)


__all__ = [
    "CommandExecutionPolicy",
]
