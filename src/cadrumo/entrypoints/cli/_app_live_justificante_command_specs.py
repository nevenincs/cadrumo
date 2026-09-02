"""Authored CommandSpec declarations for the live justificante service."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._app_live_command_spec_support import _key
from .command_spec import (
    ArgumentSpec,
    CommandSpec,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
)

LIVE_JUSTIFICANTE_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_live_justificante",
        parent_key="app_live",
        token="justificante",
        kind="group",
        help_key=_key("cli.app.live.justificante.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True, context_parameter=None),
        parameters=(),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["state-free"]),
            side_effects=frozenset(["none"]),
            performance="metadata",
            write_route=CommandWriteRoute.NONE,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="app_live_justificante_pull",
        parent_key="app_live_justificante",
        token="pull",
        kind="leaf",
        help_key=_key("cli.app.live.justificante.pull_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="modelo",
                declarations=("--modelo",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.modelo_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
            OptionSpec(
                name="year",
                declarations=("--year",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.year_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=2000, maximum=2099),
            ),
            OptionSpec(
                name="period",
                declarations=("--period",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.period_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts", "network"]),
            side_effects=frozenset(["local-state", "network"]),
            performance="external-io",
            write_route=CommandWriteRoute.PROFILE_BOUND,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_justificante_cli", "justificante_pull")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._app_live_justificante_payloads", "JustificanteCaptureResult"
            ),
            identity="app.live.justificante.pull",
        ),
    ),
    CommandSpec(
        key="app_live_justificante_list",
        parent_key="app_live_justificante",
        token="list",
        kind="leaf",
        help_key=_key("cli.app.live.justificante.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts"]),
            side_effects=frozenset(["none"]),
            performance="local-io",
            write_route=CommandWriteRoute.NONE,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_justificante_cli", "justificante_list")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_justificante_payloads", "JustificanteListResult"),
            identity="app.live.justificante.list",
        ),
    ),
    CommandSpec(
        key="app_live_justificante_view",
        parent_key="app_live_justificante",
        token="view",
        kind="leaf",
        help_key=_key("cli.app.live.justificante.view_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="snapshot_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.justificante.snapshot_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts"]),
            side_effects=frozenset(["none"]),
            performance="local-io",
            write_route=CommandWriteRoute.NONE,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_justificante_cli", "justificante_view")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_justificante_payloads", "JustificanteViewResult"),
            identity="app.live.justificante.view",
        ),
    ),
)

__all__ = ["LIVE_JUSTIFICANTE_COMMAND_SPECS"]
