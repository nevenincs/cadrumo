"""Canonical command graph for runtime-owned authentication doors."""

from __future__ import annotations

from uuid import UUID

import typer

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.output_rendering import OutputFormat
from cadrumo_client.commands.execution_policies import STATE_FREE, state_free_group_spec
from cadrumo_client.commands.graph import CommandSpecGraph
from cadrumo_client.commands.language_options import ROOT_LANGUAGE_OPTION
from cadrumo_client.commands.root_options import (
    ROOT_OUTPUT_OPTIONS,
    ROOT_PROFILE_OPTIONS,
    profile_authentication_secret,
)
from cadrumo_client.commands.shared_contracts import (
    DeferredTarget,
    LazyBinding,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
)
from cadrumo_client.commands.spec import CommandSpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind
from cadrumo_runtime.commands.command_targets import resolve_deferred_target

from .access_management_specs import RUNTIME_ACCESS_MANAGEMENT_COMMAND_SPECS
from .auth_specs import AUTH_COMMAND_SPECS
from .custody_specs import RUNTIME_CUSTODY_COMMAND_SPECS
from .google_auth_specs import RUNTIME_GOOGLE_AUTH_COMMAND_SPECS
from .recovery_specs import RUNTIME_RECOVERY_COMMAND_SPECS

_PROFILE_SECRET = profile_authentication_secret("cadrumo_runtime.host.windows_secret_bootstrap")

_ROOT_PARAMETERS = (ROOT_LANGUAGE_OPTION, *ROOT_PROFILE_OPTIONS, *ROOT_OUTPUT_OPTIONS)


def runtime_root_callback(
    ctx: typer.Context,
    language: OutputLanguage | None = None,
    profile: str | None = None,
    profile_secrets_stdin: bool = False,
    profile_secrets_fd: int | None = None,
    profile_auth_method: str = "password",
    profile_credential_ref: UUID | None = None,
    format_: OutputFormat = OutputFormat.TEXT,
    quiet: bool = False,
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Bind typed root output, language, profile and authentication context."""
    from .profile_admission import bind_runtime_root_context

    bind_runtime_root_context(
        ctx,
        language=language,
        profile=profile,
        profile_secrets_stdin=profile_secrets_stdin,
        profile_secrets_fd=profile_secrets_fd,
        profile_auth_method=profile_auth_method,
        profile_credential_ref=profile_credential_ref,
        format_=format_,
        quiet=quiet,
        verbose=verbose,
        debug=debug,
    )


_ROOT = CommandSpec(
    "root",
    None,
    "cadrumo-runtime",
    kind=CommandNodeKind.ROOT,
    help_key=TranslationKey("cli.config.auth.help"),
    short_help_key=None,
    invocation=InvocationSpec(
        invoke_without_command=True,
        no_args_is_help=True,
        add_completion=False,
        context_parameter="ctx",
        terminal_behavior="executable",
    ),
    parameters=_ROOT_PARAMETERS,
    policy=STATE_FREE,
    handler=LazyBinding.available(DeferredTarget(".command_specs", "runtime_root_callback", __package__)),
    result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    profile_secret=_PROFILE_SECRET,
)

_CONFIG = state_free_group_spec("config", "root", "config", "cli.config.help")

_PROFILE = state_free_group_spec("config_profile", "config", "profile", "cli.config.profile.help")

RUNTIME_COMMAND_GRAPH = CommandSpecGraph(
    (
        _ROOT,
        _CONFIG,
        _PROFILE,
        *AUTH_COMMAND_SPECS,
        *RUNTIME_CUSTODY_COMMAND_SPECS,
        *RUNTIME_GOOGLE_AUTH_COMMAND_SPECS,
        *RUNTIME_ACCESS_MANAGEMENT_COMMAND_SPECS,
        *RUNTIME_RECOVERY_COMMAND_SPECS,
    ),
    resolver=resolve_deferred_target,
)

__all__ = ["RUNTIME_COMMAND_GRAPH"]
