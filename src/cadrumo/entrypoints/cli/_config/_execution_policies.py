"""Shared, import-light execution declarations for config callbacks.

The presets name semantic execution shapes, not command paths.  Each command
callback still owns its declaration by attaching one of these immutable values
at its registration site.
"""

from __future__ import annotations

import typer

from .._command_policy import CommandExecutionPolicy, CommandWriteRouteScope, command_execution_policy
from .._command_schema import (
    CommandCapability,
    CommandCapabilityClass,
    CommandPerformanceClass,
    CommandSideEffectClass,
)


def _policy(
    capabilities: frozenset[CommandCapability],
    effects: frozenset[CommandSideEffectClass],
    performance: CommandPerformanceClass,
    *,
    write_route: CommandWriteRouteScope = "none",
    destructive: bool = False,
    handoff: bool = False,
) -> CommandExecutionPolicy:
    return CommandExecutionPolicy(
        classification=CommandCapabilityClass(
            capabilities=capabilities,
            side_effects=effects,
            performance=performance,
        ),
        write_route=write_route,
        destructive=destructive,
        handoff=handoff,
    )


STATE_FREE = _policy(frozenset({"state-free"}), frozenset({"none"}), "metadata")
LOCAL_READ = _policy(frozenset({"state-free"}), frozenset({"none"}), "local-io")
PROFILE_READ = _policy(frozenset({"profile-custody"}), frozenset({"none"}), "local-io")
ENCRYPTED_READ = _policy(frozenset({"encrypted-facts"}), frozenset({"none"}), "local-io")
PROFILE_WRITE = _policy(
    frozenset({"profile-custody"}), frozenset({"local-state"}), "local-io", write_route="profile-bound"
)
PROFILE_DESTRUCTIVE = _policy(
    frozenset({"profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    write_route="profile-bound",
    destructive=True,
)
ENCRYPTED_WRITE = _policy(
    frozenset({"encrypted-facts"}), frozenset({"local-state"}), "local-io", write_route="profile-bound"
)
ENCRYPTED_DESTRUCTIVE = _policy(
    frozenset({"encrypted-facts"}),
    frozenset({"local-state"}),
    "local-io",
    write_route="profile-bound",
    destructive=True,
)
BOOTSTRAP_WRITE = _policy(
    frozenset({"profile-custody"}), frozenset({"local-state"}), "local-io", write_route="bootstrap-root"
)
BOOTSTRAP_DESTRUCTIVE = _policy(
    frozenset({"profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    write_route="bootstrap-root",
    destructive=True,
)
GOOGLE_READ = _policy(frozenset({"google", "encrypted-facts"}), frozenset({"google"}), "external-io")
GOOGLE_WRITE = _policy(
    frozenset({"google", "encrypted-facts"}),
    frozenset({"google", "local-state"}),
    "external-io",
    write_route="profile-bound",
)
GOOGLE_DESTRUCTIVE = _policy(
    frozenset({"google", "encrypted-facts"}),
    frozenset({"google", "local-state"}),
    "external-io",
    write_route="profile-bound",
    destructive=True,
)
GOOGLE_HANDOFF = _policy(
    frozenset({"google", "encrypted-facts", "filing"}),
    frozenset({"google", "local-state"}),
    "external-io",
    write_route="profile-bound",
    handoff=True,
)
CALCULATION_READ = _policy(
    frozenset({"calculation", "encrypted-facts"}), frozenset({"none"}), "compute"
)
REGISTRY_READ = _policy(frozenset({"calculation"}), frozenset({"none"}), "compute")
CALCULATION_WRITE = _policy(
    frozenset({"calculation", "encrypted-facts"}),
    frozenset({"local-state"}),
    "compute",
    write_route="profile-bound",
)
GOOGLE_CALCULATION_READ = _policy(
    frozenset({"google", "calculation", "encrypted-facts"}), frozenset({"google"}), "external-io"
)
GOOGLE_CALCULATION_WRITE = _policy(
    frozenset({"google", "calculation", "encrypted-facts"}),
    frozenset({"google", "local-state"}),
    "external-io",
    write_route="profile-bound",
)
GOOGLE_CALCULATION_HANDOFF = _policy(
    frozenset({"google", "calculation", "encrypted-facts", "filing"}),
    frozenset({"google", "local-state"}),
    "external-io",
    write_route="profile-bound",
    handoff=True,
)
NETWORK_WRITE = _policy(frozenset({"network"}), frozenset({"network", "local-state"}), "external-io")
LIVE_PROFILE_WRITE = _policy(
    frozenset({"network", "encrypted-facts"}),
    frozenset({"network", "local-state"}),
    "external-io",
    write_route="profile-bound",
)
BROWSER_CONNECTIVITY = _policy(frozenset({"browser"}), frozenset({"browser"}), "interactive")


def declare_metadata_group(app: typer.Typer) -> None:
    """Attach an explicit state-free policy to a non-executing Typer group."""
    callback = app.callback

    @callback()
    @command_execution_policy(STATE_FREE)
    def _metadata_group() -> None:
        return None


__all__ = [name for name in globals() if name.isupper()]
