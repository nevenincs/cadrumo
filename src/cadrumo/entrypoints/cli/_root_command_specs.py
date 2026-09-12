"""Production-authored specifications for the executable and namespace roots."""

from __future__ import annotations

from .command_spec import (
    FLAG_VALUE,
    TEXT_VALUE,
    WHOLE_NUMBER_VALUE,
    CommandNodeKind,
    CommandSpec,
    CommandWriteRoute,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    MachineSecretFieldSpec,
    OptionSpec,
    ParameterDefault,
    ProfileSecretChannelKind,
    ProfileSecretSpec,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

_OUTPUT_LANGUAGE = ValueContract(DeferredTarget("...core.external_constants", "OutputLanguage", __package__))
_OUTPUT_FORMAT = ValueContract(DeferredTarget("...core.output_rendering", "OutputFormat", __package__))
_STATE_FREE = ExecutionPolicySpec(
    capabilities=frozenset({"state-free"}),
    side_effects=frozenset({"none"}),
    performance="metadata",
    write_route=CommandWriteRoute.NONE,
)
_ROOT_STATUS = ExecutionPolicySpec(
    capabilities=frozenset({"calculation", "encrypted-facts"}),
    side_effects=frozenset({"none"}),
    performance="compute",
    write_route=CommandWriteRoute.NONE,
)


ROOT_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="root",
        parent_key=None,
        token="aeat",  # noqa: S106 - CLI operator token, not a credential
        kind=CommandNodeKind.ROOT,
        help_key=TranslationKey("cli.root.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(
            invoke_without_command=True,
            add_help_option=False,
            add_completion=True,
            context_parameter="ctx",
            terminal_behavior="introspection",
        ),
        parameters=(
            OptionSpec(
                name="language",
                declarations=("--language", "--lang"),
                value=_OUTPUT_LANGUAGE,
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
                name="version",
                declarations=("--version", "-V"),
                value=FLAG_VALUE,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.version_help"),
                is_flag=True,
                eager=True,
            ),
            OptionSpec(
                name="detail",
                declarations=("--detail",),
                value=FLAG_VALUE,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.detail_help"),
                is_flag=True,
                eager=True,
            ),
            OptionSpec(
                name="help_",
                declarations=("--help", "-h"),
                value=FLAG_VALUE,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.help_help"),
                is_flag=True,
                eager=True,
            ),
            OptionSpec(
                name="format_",
                declarations=("--format",),
                value=_OUTPUT_FORMAT,
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
            ),
            OptionSpec(
                name="verbose",
                declarations=("--verbose",),
                value=FLAG_VALUE,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.verbose_help"),
                is_flag=True,
            ),
            OptionSpec(
                name="debug",
                declarations=("--debug",),
                value=FLAG_VALUE,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.debug_help"),
                is_flag=True,
            ),
        ),
        policy=_ROOT_STATUS,
        handler=LazyBinding.available(DeferredTarget("._root_cli", "root_command", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._root_payloads", "RootStatusResult", __package__),
            identity="root.status",
        ),
        profile_secret=ProfileSecretSpec(
            fields=(MachineSecretFieldSpec("profile_passphrase"),),
            model=DeferredTarget(
                "._profile_authentication_contract",
                "ProfileAuthenticationSecrets",
                __package__,
            ),
        ),
    ),
    CommandSpec(
        key="app",
        parent_key="root",
        token="app",  # noqa: S106 - CLI operator token, not a credential
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.root.app_app_help"),
        short_help_key=None,
        invocation=InvocationSpec(
            invoke_without_command=True,
            add_help_option=False,
            context_parameter="ctx",
            terminal_behavior="introspection",
        ),
        parameters=(
            OptionSpec(
                name="help_",
                declarations=("--help", "-h"),
                value=FLAG_VALUE,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.app_help_help"),
                is_flag=True,
                eager=True,
            ),
        ),
        policy=_STATE_FREE,
        handler=LazyBinding.available(DeferredTarget("._root_cli", "app_root", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._root_payloads", "AppRootResult", __package__),
            identity="root.app",
        ),
    ),
    CommandSpec(
        key="app_tui",
        parent_key="app",
        token="tui",  # noqa: S106 - command token, not a credential
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.root.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter=None),
        parameters=(),
        policy=_STATE_FREE,
        handler=LazyBinding.available(DeferredTarget(".tui_launcher", "launch_tui", __package__)),
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="config",
        parent_key="root",
        token="config",  # noqa: S106 - CLI operator token, not a credential
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.config.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(
            invoke_without_command=True,
            add_help_option=False,
            add_completion=True,
            context_parameter="ctx",
            terminal_behavior="introspection",
        ),
        parameters=(
            OptionSpec(
                name="help_",
                declarations=("--help", "-h"),
                value=FLAG_VALUE,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.config.workflow_help"),
                is_flag=True,
                eager=True,
            ),
        ),
        policy=_STATE_FREE,
        handler=LazyBinding.available(DeferredTarget(".config.root_cli", "config_root", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._config_help_payloads", "ConfigRootResult", __package__),
            identity="root.config",
        ),
    ),
)

__all__ = ["ROOT_COMMAND_SPECS"]
