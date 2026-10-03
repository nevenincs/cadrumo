"""Import-light command authority for installed runtime management."""

from __future__ import annotations

from cadrumo.application.operator_surface.command_ports import CommandNodeKind, CommandWriteRoute

from ._command_parameter_contracts import OptionSpec
from ._command_shared_contracts import (
    DeferredTarget,
    LazyBinding,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
    translation_key,
)
from .command_spec import CommandSpec, ExecutionPolicySpec, InvocationSpec

_PROFILE_FREE_READ = ExecutionPolicySpec(
    frozenset({"state-free"}), frozenset({"none"}), "local-io", CommandWriteRoute.NONE
)
_RUNTIME_WRITE = ExecutionPolicySpec(
    frozenset({"local-storage", "subprocess"}),
    frozenset({"local-state"}),
    "local-io",
    CommandWriteRoute.NONE,
)

APP_RUNTIME_COMMAND_SPECS = (
    CommandSpec(
        "app_runtime",
        "app",
        "runtime",
        kind=CommandNodeKind.GROUP,
        help_key=translation_key("cli.app.runtime.help"),
        short_help_key=None,
        invocation=InvocationSpec(
            invoke_without_command=True,
            no_args_is_help=True,
            context_parameter="ctx",
            terminal_behavior="introspection",
        ),
        parameters=(),
        policy=_PROFILE_FREE_READ,
        handler=LazyBinding.available(DeferredTarget(".app_runtime", "runtime_root", __package__)),
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "app_runtime_status",
        "app_runtime",
        "status",
        kind=CommandNodeKind.LEAF,
        help_key=translation_key("cli.app.runtime.status.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=_PROFILE_FREE_READ,
        handler=LazyBinding.available(DeferredTarget(".app_runtime", "runtime_status", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(".app_runtime_payloads", "RuntimeStatusResult", __package__),
            identity="app.runtime.status",
        ),
    ),
    *(
        CommandSpec(
            f"app_runtime_{action}",
            "app_runtime",
            action,
            kind=CommandNodeKind.LEAF,
            help_key=help_key,
            short_help_key=None,
            invocation=InvocationSpec(context_parameter="ctx"),
            parameters=(),
            policy=_RUNTIME_WRITE,
            handler=LazyBinding.available(DeferredTarget(".app_runtime", f"runtime_{action}", __package__)),
            result_schema=ResultSchemaSpec(
                SchemaState.TARGET,
                DeferredTarget(
                    ".app_runtime_payloads",
                    "RuntimeStatusResult" if action == "start" else "RuntimeManagerConfigResult",
                    __package__,
                ),
                identity=f"app.runtime.{action}",
            ),
        )
        for action, help_key in (
            ("start", translation_key("cli.app.runtime.start.help")),
            ("enable", translation_key("cli.app.runtime.enable.help")),
            ("disable", translation_key("cli.app.runtime.disable.help")),
        )
    ),
    CommandSpec(
        "app_runtime_stop",
        "app_runtime",
        "stop",
        kind=CommandNodeKind.LEAF,
        help_key=translation_key("cli.app.runtime.stop.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="acknowledge_all_profiles_and_work",
                declarations=("--acknowledge-all-profiles-and-work",),
                value=ValueContract(DeferredTarget("builtins", "bool")),
                default=ParameterDefault.value(False),
                help_key=translation_key("cli.app.runtime.stop.acknowledge_help"),
                is_flag=True,
                flag_value=True,
            ),
        ),
        policy=_RUNTIME_WRITE,
        handler=LazyBinding.available(DeferredTarget(".app_runtime", "runtime_stop", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(".app_runtime_payloads", "RuntimeStopResult", __package__),
            identity="app.runtime.stop",
        ),
    ),
)

__all__ = ["APP_RUNTIME_COMMAND_SPECS"]
