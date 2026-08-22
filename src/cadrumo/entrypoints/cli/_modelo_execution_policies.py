"""Import-light execution declarations shared by modelo callbacks.

The immutable values describe authority/effect shapes, never command paths.
Each live callback remains the authoritative owner by attaching one preset at
its registration site.
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
CRYPTO_READ = _policy(frozenset({"crypto"}), frozenset({"none"}), "local-io")
CRYPTO_FACT_FILE_WRITE = _policy(frozenset({"crypto", "encrypted-facts"}), frozenset({"local-state"}), "local-io")
REGISTRY_READ = _policy(frozenset({"registry"}), frozenset({"none"}), "compute")
MODEL_READ = _policy(frozenset({"encrypted-facts"}), frozenset({"none"}), "local-io")
MODEL_WRITE = _policy(
    frozenset({"encrypted-facts"}),
    frozenset({"local-state"}),
    "local-io",
    write_route="profile-bound",
)
MODEL_DESTRUCTIVE = _policy(
    frozenset({"encrypted-facts"}),
    frozenset({"local-state"}),
    "local-io",
    write_route="profile-bound",
    destructive=True,
)
REGISTRY_MODEL_READ = _policy(frozenset({"registry", "encrypted-facts"}), frozenset({"none"}), "local-io")
REGISTRY_MODEL_WRITE = _policy(
    frozenset({"registry", "encrypted-facts"}),
    frozenset({"local-state"}),
    "local-io",
    write_route="profile-bound",
)
CALCULATION_READ = _policy(frozenset({"calculation", "encrypted-facts"}), frozenset({"none"}), "compute")
CALCULATION_WRITE = _policy(
    frozenset({"calculation", "encrypted-facts"}),
    frozenset({"local-state"}),
    "compute",
    write_route="profile-bound",
)
MODEL_HANDOFF = _policy(
    frozenset({"encrypted-facts", "filing"}),
    frozenset({"local-state"}),
    "compute",
    write_route="profile-bound",
    handoff=True,
)
CRYPTO_PROFILE_WRITE = _policy(
    frozenset({"crypto", "encrypted-facts"}),
    frozenset({"local-state"}),
    "local-io",
    write_route="profile-bound",
)
BROWSER_MODEL_WRITE = _policy(
    frozenset({"browser", "registry", "encrypted-facts"}),
    frozenset({"browser", "network", "local-state"}),
    "external-io",
    write_route="profile-bound",
)
INTERACTIVE_MODEL_WRITE = _policy(
    frozenset({"calculation", "encrypted-facts"}),
    frozenset({"local-state"}),
    "interactive",
    write_route="profile-bound",
)


def declare_metadata_group(app: typer.Typer) -> None:
    """Attach an explicit inert policy to a non-executing modelo group."""
    callback = app.callback

    @callback()
    @command_execution_policy(METADATA)
    def _metadata_group() -> None:
        return None


__all__ = [name for name in globals() if name.isupper()]
