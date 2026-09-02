"""Production-authored specifications for the executable and namespace roots."""

from __future__ import annotations

from .command_spec import (
    CommandSpec,
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
    TuiCapability,
    ValueContract,
)

_STRING = ValueContract(DeferredTarget("builtins", "str"))
_BOOL = ValueContract(DeferredTarget("builtins", "bool"))
_INT = ValueContract(DeferredTarget("builtins", "int"))
_OUTPUT_LANGUAGE = ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage"))
_OUTPUT_FORMAT = ValueContract(DeferredTarget("cadrumo.core.output_rendering", "OutputFormat"))
_STATE_FREE = ExecutionPolicySpec(
    capabilities=frozenset({"state-free"}),
    side_effects=frozenset({"none"}),
    performance="metadata",
    write_route="none",
)
_ROOT_STATUS = ExecutionPolicySpec(
    capabilities=frozenset({"calculation", "encrypted-facts"}),
    side_effects=frozenset({"none"}),
    performance="compute",
    write_route="none",
)


ROOT_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="root",
        tui_capability=TuiCapability.AVAILABLE,
        parent_key=None,
        token="aeat",  # noqa: S106 - CLI operator token, not a credential
        kind="root",
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
                value=_STRING,
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.root.profile_help"),
            ),
            OptionSpec(
                name="profile_secrets_stdin",
                declarations=("--profile-secrets-stdin",),
                value=_BOOL,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.config.custody.profile_secrets_stdin_help"),
                is_flag=True,
                profile_secret_channel=ProfileSecretChannelKind.STDIN,
            ),
            OptionSpec(
                name="profile_secrets_fd",
                declarations=("--profile-secrets-fd",),
                value=_INT,
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.custody.profile_secrets_fd_help"),
                profile_secret_channel=ProfileSecretChannelKind.FILE_DESCRIPTOR,
            ),
            OptionSpec(
                name="version",
                declarations=("--version", "-V"),
                value=_BOOL,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.version_help"),
                is_flag=True,
                eager=True,
            ),
            OptionSpec(
                name="detail",
                declarations=("--detail",),
                value=_BOOL,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.detail_help"),
                is_flag=True,
                eager=True,
            ),
            OptionSpec(
                name="help_",
                declarations=("--help", "-h"),
                value=_BOOL,
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
                name="tui",
                declarations=("--tui",),
                value=_BOOL,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.tui_help"),
                is_flag=True,
            ),
            OptionSpec(
                name="self_test",
                declarations=("--self-test",),
                value=_BOOL,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.self_test_help"),
                is_flag=True,
            ),
            OptionSpec(
                name="quiet",
                declarations=("--quiet",),
                value=_BOOL,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.quiet_help"),
                is_flag=True,
            ),
            OptionSpec(
                name="verbose",
                declarations=("--verbose",),
                value=_BOOL,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.verbose_help"),
                is_flag=True,
            ),
            OptionSpec(
                name="debug",
                declarations=("--debug",),
                value=_BOOL,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.debug_help"),
                is_flag=True,
            ),
        ),
        policy=_ROOT_STATUS,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._root_cli", "root_command")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._root_payloads", "RootStatusResult"),
            identity="root.status",
        ),
        profile_secret=ProfileSecretSpec(
            fields=(MachineSecretFieldSpec("profile_passphrase"),),
            model=DeferredTarget(
                "cadrumo.entrypoints.cli._profile_authentication_contract",
                "ProfileAuthenticationSecrets",
            ),
        ),
    ),
    CommandSpec(
        key="app",
        parent_key="root",
        token="app",  # noqa: S106 - CLI operator token, not a credential
        kind="group",
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
                value=_BOOL,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.root.app_help_help"),
                is_flag=True,
                eager=True,
            ),
        ),
        policy=_STATE_FREE,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._root_cli", "app_root")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._root_payloads", "AppRootResult"),
            identity="root.app",
        ),
    ),
    CommandSpec(
        key="config",
        parent_key="root",
        token="config",  # noqa: S106 - CLI operator token, not a credential
        kind="group",
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
                value=_BOOL,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.config.workflow_help"),
                is_flag=True,
                eager=True,
            ),
        ),
        policy=_STATE_FREE,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli.config._root_cli", "config_root")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._config_help_payloads", "ConfigRootResult"),
            identity="root.config",
        ),
    ),
)

__all__ = ["ROOT_COMMAND_SPECS"]
