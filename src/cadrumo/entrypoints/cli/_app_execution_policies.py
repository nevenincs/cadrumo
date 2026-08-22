"""Import-light execution declarations for the remaining application CLI.

Presets describe execution shapes, never command paths.  Registration modules
attach them directly to their callbacks so the live command tree remains the
only path authority.
"""

from __future__ import annotations

import typer

from ._command_policy import CommandExecutionPolicy, CommandWriteRouteScope, command_execution_policy
from ._command_schema import CommandCapability, CommandCapabilityClass, CommandPerformanceClass, CommandSideEffectClass


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


METADATA = _policy(frozenset({"state-free"}), frozenset({"none"}), "metadata")
REGISTRY_READ = _policy(frozenset({"registry"}), frozenset({"none"}), "compute")
PROFILE_READ = _policy(frozenset({"profile-custody"}), frozenset({"none"}), "local-io")
LOCAL_STORAGE_READ = _policy(frozenset({"local-storage"}), frozenset({"none"}), "local-io")
LOCAL_STORAGE_WRITE = _policy(
    frozenset({"local-storage"}), frozenset({"local-state"}), "local-io"
)
ENCRYPTED_READ = _policy(frozenset({"encrypted-facts"}), frozenset({"none"}), "local-io")
CALCULATION_READ = _policy(
    frozenset({"calculation", "encrypted-facts"}), frozenset({"none"}), "compute"
)
PROFILE_LOCAL_WRITE = _policy(
    frozenset({"profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    write_route="profile-bound",
)
PROFILE_LOCAL_DESTRUCTIVE = _policy(
    frozenset({"profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    write_route="profile-bound",
    destructive=True,
)
LIVE_READ = _policy(
    frozenset({"network", "encrypted-facts"}), frozenset({"network"}), "external-io"
)
LIVE_PROFILE_WRITE = _policy(
    frozenset({"network", "encrypted-facts"}),
    frozenset({"network", "local-state"}),
    "external-io",
    write_route="profile-bound",
)
BROWSER_SUBPROCESS_LIVE_PROFILE_WRITE = _policy(
    frozenset({"browser", "subprocess", "encrypted-facts"}),
    frozenset({"browser", "network", "local-state"}),
    "external-io",
    write_route="profile-bound",
)
QUICKFILE_HANDOFF = _policy(
    frozenset({"calculation", "filing", "encrypted-facts"}),
    frozenset({"local-state"}),
    "compute",
    write_route="profile-bound",
    handoff=True,
)


def declare_metadata_group(app: typer.Typer) -> None:
    """Attach an explicit inert policy to a non-executing Typer group."""
    callback = app.callback

    @callback()
    @command_execution_policy(METADATA)
    def _metadata_group() -> None:
        return None


__all__ = [name for name in globals() if name.isupper()]
