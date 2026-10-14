"""Canonical command graph for runtime-owned authentication doors."""

from __future__ import annotations

from uuid import UUID

import typer

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.output_rendering import OutputFormat
from cadrumo_client.commands.graph import CommandSpecGraph
from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.secret_contracts import MachineSecretFieldSpec, ProfileSecretChannelKind, ProfileSecretSpec
from cadrumo_client.commands.shared_contracts import (
    FLAG_VALUE,
    TEXT_VALUE,
    WHOLE_NUMBER_VALUE,
    DeferredTarget,
    LazyBinding,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from cadrumo_client.commands.spec import CommandSpec, ExecutionPolicySpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind, CommandWriteRoute

from .access_management_specs import RUNTIME_ACCESS_MANAGEMENT_COMMAND_SPECS
from .auth_specs import AUTH_COMMAND_SPECS
from .custody_specs import RUNTIME_CUSTODY_COMMAND_SPECS
from .google_auth_specs import RUNTIME_GOOGLE_AUTH_COMMAND_SPECS
from .recovery_specs import RUNTIME_RECOVERY_COMMAND_SPECS

_PROFILE_SECRET = ProfileSecretSpec(
    fields=(MachineSecretFieldSpec("profile_passphrase"), MachineSecretFieldSpec("api_key")),
    model=DeferredTarget("cadrumo_client.commands.profile_authentication", "ProfileAuthenticationSecrets"),
)

_ROOT_PARAMETERS = (
    OptionSpec(
        name="language",
        declarations=("--language", "--lang"),
        value=ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage", __package__)),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.root.language_help"),
        eager=True,
    ),
    OptionSpec(
        name="profile",
        declarations=("--profile",),
        value=TEXT_VALUE,
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.root.profile_help"),
    ),
    OptionSpec(
        name="profile_secrets_stdin",
        declarations=("--profile-secrets-stdin",),
        value=FLAG_VALUE,
        default=ParameterDefault.value(False),
        help_key=TranslationKey("cli.config.custody.profile_secrets_stdin_help"),
        is_flag=True,
        flag_value=True,
        profile_secret_channel=ProfileSecretChannelKind.STDIN,
    ),
    OptionSpec(
        name="profile_secrets_fd",
        declarations=("--profile-secrets-fd",),
        value=WHOLE_NUMBER_VALUE,
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.config.custody.profile_secrets_fd_help"),
        profile_secret_channel=ProfileSecretChannelKind.FILE_DESCRIPTOR,
    ),
    OptionSpec(
        name="profile_auth_method",
        declarations=("--profile-auth-method",),
        value=ValueContract(DeferredTarget("builtins", "str"), choices=("password", "api-key")),
        default=ParameterDefault.value("password"),
        help_key=TranslationKey("cli.config.custody.profile_auth_method_help"),
    ),
    OptionSpec(
        name="profile_credential_ref",
        declarations=("--profile-credential-ref",),
        value=ValueContract(DeferredTarget("uuid", "UUID")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.config.custody.profile_credential_ref_help"),
    ),
    OptionSpec(
        name="format_",
        declarations=("--format",),
        value=ValueContract(DeferredTarget("cadrumo.core.output_rendering", "OutputFormat", __package__)),
        default=ParameterDefault.value("text"),
        help_key=TranslationKey("cli.root.format_help"),
    ),
    OptionSpec(
        name="quiet",
        declarations=("--quiet",),
        value=FLAG_VALUE,
        default=ParameterDefault.value(False),
        help_key=TranslationKey("cli.root.quiet_help"),
        is_flag=True,
        flag_value=True,
    ),
    OptionSpec(
        name="verbose",
        declarations=("--verbose",),
        value=FLAG_VALUE,
        default=ParameterDefault.value(False),
        help_key=TranslationKey("cli.root.verbose_help"),
        is_flag=True,
        flag_value=True,
    ),
    OptionSpec(
        name="debug",
        declarations=("--debug",),
        value=FLAG_VALUE,
        default=ParameterDefault.value(False),
        help_key=TranslationKey("cli.root.debug_help"),
        is_flag=True,
        flag_value=True,
    ),
)

_STATE_FREE = ExecutionPolicySpec(
    capabilities=frozenset({"state-free"}),
    side_effects=frozenset({"none"}),
    performance="metadata",
    write_route=CommandWriteRoute.NONE,
)


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
    policy=_STATE_FREE,
    handler=LazyBinding.available(DeferredTarget(".command_specs", "runtime_root_callback", __package__)),
    result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    profile_secret=_PROFILE_SECRET,
)

_CONFIG = CommandSpec(
    "config",
    "root",
    "config",
    kind=CommandNodeKind.GROUP,
    help_key=TranslationKey("cli.config.help"),
    short_help_key=None,
    invocation=InvocationSpec(no_args_is_help=True),
    parameters=(),
    policy=_STATE_FREE,
    handler=None,
    result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
)

_PROFILE = CommandSpec(
    "config_profile",
    "config",
    "profile",
    kind=CommandNodeKind.GROUP,
    help_key=TranslationKey("cli.config.profile.help"),
    short_help_key=None,
    invocation=InvocationSpec(no_args_is_help=True),
    parameters=(),
    policy=_STATE_FREE,
    handler=None,
    result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
)

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
    )
)

__all__ = ["RUNTIME_COMMAND_GRAPH"]
