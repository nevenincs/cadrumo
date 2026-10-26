"""Production-authored specifications for the executable and namespace roots."""

from __future__ import annotations

from cadrumo_client.commands.execution_policies import CALCULATION_READ, STATE_FREE
from cadrumo_client.commands.language_options import ROOT_LANGUAGE_OPTION
from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.root_options import (
    ROOT_OUTPUT_OPTIONS,
    ROOT_PROFILE_OPTIONS,
    profile_authentication_secret,
)
from cadrumo_client.commands.shared_contracts import (
    FLAG_VALUE,
    DeferredTarget,
    LazyBinding,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
)
from cadrumo_client.commands.spec import CommandSpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind

ROOT_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "root",
        None,
        "aeat",
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
            ROOT_LANGUAGE_OPTION,
            *ROOT_PROFILE_OPTIONS,
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
            *ROOT_OUTPUT_OPTIONS,
        ),
        policy=CALCULATION_READ,
        handler=LazyBinding.available(DeferredTarget(".root_commands", "root_command", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".root_results", "RootStatusResult", __package__),
            identity="root.status",
        ),
        profile_secret=profile_authentication_secret("cadrumo_runtime.host.frontend.cli.windows_secret_bootstrap"),
    ),
    CommandSpec(
        "app",
        "root",
        "app",
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
        policy=STATE_FREE,
        handler=LazyBinding.available(DeferredTarget(".root_commands", "app_root", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".root_results", "AppRootResult", __package__),
            identity="root.app",
        ),
    ),
    CommandSpec(
        "app_tui",
        "app",
        "tui",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.root.app_tui_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(),
        policy=STATE_FREE,
        handler=LazyBinding.available(DeferredTarget(".tui_request", "launch_tui", __package__)),
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "config",
        "root",
        "config",
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
        policy=STATE_FREE,
        handler=LazyBinding.available(DeferredTarget(".config.root_cli", "config_root", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".config_help_results", "ConfigRootResult", __package__),
            identity="root.config",
        ),
    ),
)

__all__ = ["ROOT_COMMAND_SPECS"]
