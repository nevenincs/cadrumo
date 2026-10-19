"""Import-light execution policies owned by the config command specifications."""

from __future__ import annotations

from cadrumo_client.commands.shared_contracts import (
    ResultSchemaSpec,
    SchemaState,
    translation_key,
)
from cadrumo_client.commands.spec import CommandSpec, ExecutionPolicySpec, InvocationSpec
from cadrumo_client.contracts.command_ports import (
    Capability,
    CommandNodeKind,
    CommandWriteRoute,
    CommandWriteRouteValue,
    PerformanceClass,
    SideEffect,
)


def _policy(
    capabilities: frozenset[Capability],
    side_effects: frozenset[SideEffect],
    performance: PerformanceClass,
    *,
    write_route: CommandWriteRouteValue = CommandWriteRoute.NONE,
    destructive: bool = False,
    handoff: bool = False,
) -> ExecutionPolicySpec:
    return ExecutionPolicySpec(
        capabilities=capabilities,
        side_effects=side_effects,
        performance=performance,
        write_route=write_route,
        destructive=destructive,
        handoff=handoff,
    )


STATE_FREE = _policy(frozenset({"state-free"}), frozenset({"none"}), "metadata")
PROFILE_READ = _policy(frozenset({"profile-custody"}), frozenset({"none"}), "local-io")
ENCRYPTED_READ = _policy(frozenset({"encrypted-facts"}), frozenset({"none"}), "local-io")
PROFILE_DESTRUCTIVE = _policy(
    frozenset({"profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=True,
)
ENCRYPTED_WRITE = _policy(
    frozenset({"encrypted-facts", "profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
)
ENCRYPTED_DESTRUCTIVE = _policy(
    frozenset({"encrypted-facts", "profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=True,
)
BOOTSTRAP_WRITE = _policy(
    frozenset({"profile-custody"}), frozenset({"local-state"}), "local-io", write_route=CommandWriteRoute.BOOTSTRAP_ROOT
)
BOOTSTRAP_DESTRUCTIVE = _policy(
    frozenset({"profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    write_route=CommandWriteRoute.BOOTSTRAP_ROOT,
    destructive=True,
)
GOOGLE_READ = _policy(frozenset({"google", "encrypted-facts"}), frozenset({"google"}), "external-io")
GOOGLE_WRITE = _policy(
    frozenset({"google", "encrypted-facts", "profile-custody"}),
    frozenset({"google", "local-state"}),
    "external-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
)
GOOGLE_DESTRUCTIVE = _policy(
    frozenset({"google", "encrypted-facts", "profile-custody"}),
    frozenset({"google", "local-state"}),
    "external-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=True,
)
# Opens an AEAT session for the active profile through the Sede browser client.
AEAT_SESSION_WRITE = _policy(
    frozenset({"aeat", "encrypted-facts", "profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
)


__all__ = [
    "AEAT_SESSION_WRITE",
    "BOOTSTRAP_DESTRUCTIVE",
    "BOOTSTRAP_WRITE",
    "ENCRYPTED_DESTRUCTIVE",
    "ENCRYPTED_READ",
    "ENCRYPTED_WRITE",
    "GOOGLE_DESTRUCTIVE",
    "GOOGLE_READ",
    "GOOGLE_WRITE",
    "PROFILE_DESTRUCTIVE",
    "PROFILE_READ",
    "STATE_FREE",
]


def state_free_group_spec(key: str, parent: str, token: str, help_key: str) -> CommandSpec:
    """Return the spec for a state-free group command.

    A group command carries no parameters, no handler and no result schema: it
    exists to hold subcommands and print help. Two config spec modules each built
    that same eleven-field construction, so two places decided what a group is.
    """
    return CommandSpec(
        key=key,
        parent_key=parent,
        token=token,
        kind=CommandNodeKind.GROUP,
        help_key=translation_key(help_key),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    )
