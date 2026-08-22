"""Import-light execution declarations shared by ledger callbacks.

The values describe reusable execution shapes rather than command paths.  A
callback remains the authority for its own declaration by attaching one of
these immutable presets at its registration site.
"""

from __future__ import annotations

import typer

from ._command_policy import CommandExecutionPolicy, command_execution_policy
from ._command_schema import CommandCapability, CommandCapabilityClass, CommandPerformanceClass, CommandSideEffectClass


def _policy(
    capabilities: frozenset[CommandCapability],
    effects: frozenset[CommandSideEffectClass],
    performance: CommandPerformanceClass,
    *,
    destructive: bool = False,
    handoff: bool = False,
) -> CommandExecutionPolicy:
    return CommandExecutionPolicy(
        classification=CommandCapabilityClass(
            capabilities=capabilities,
            side_effects=effects,
            performance=performance,
        ),
        write_route="profile-bound" if "local-state" in effects else "none",
        destructive=destructive,
        handoff=handoff,
    )


METADATA = _policy(frozenset({"state-free"}), frozenset({"none"}), "metadata")
LEDGER_READ = _policy(frozenset({"encrypted-facts"}), frozenset({"none"}), "local-io")
LEDGER_WRITE = _policy(frozenset({"encrypted-facts"}), frozenset({"local-state"}), "local-io")
LEDGER_DESTRUCTIVE = _policy(frozenset({"encrypted-facts"}), frozenset({"local-state"}), "local-io", destructive=True)
LEDGER_COMPUTE_READ = _policy(frozenset({"calculation", "encrypted-facts"}), frozenset({"none"}), "compute")
LEDGER_COMPUTE_WRITE = _policy(frozenset({"calculation", "encrypted-facts"}), frozenset({"local-state"}), "compute")
LEDGER_NETWORK_WRITE = _policy(
    frozenset({"network", "encrypted-facts"}), frozenset({"network", "local-state"}), "external-io"
)
LEDGER_NETWORK_COMPUTE_WRITE = _policy(
    frozenset({"network", "calculation", "encrypted-facts"}),
    frozenset({"network", "local-state"}),
    "external-io",
)
LEDGER_GOOGLE_WRITE = _policy(
    frozenset({"google", "encrypted-facts"}), frozenset({"google", "local-state"}), "external-io"
)
LEDGER_HANDOFF = _policy(
    frozenset({"filing", "encrypted-facts"}),
    frozenset({"local-state"}),
    "local-io",
    handoff=True,
)


def declare_metadata_group(app: typer.Typer) -> None:
    """Give a non-executing ledger group an explicit inert callback."""
    callback = app.callback

    @callback()
    @command_execution_policy(METADATA)
    def _metadata_group() -> None:
        return None


__all__ = [name for name in globals() if name.isupper()]
