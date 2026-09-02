"""Authored CommandSpec declarations for the live borrador service."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ...core.modelo import Modelo
from ._app_live_command_spec_support import _key
from .command_spec import (
    ArgumentSpec,
    CommandNodeKind,
    CommandSpec,
    CommandWriteRoute,
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

LIVE_BORRADOR_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_live_borrador",
        parent_key="app_live",
        token="borrador",
        kind=CommandNodeKind.GROUP,
        help_key=_key("cli.app.live.borrador.app_help"),
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
        key="app_live_borrador_100",
        parent_key="app_live_borrador",
        token=Modelo.M100.value,
        kind=CommandNodeKind.GROUP,
        help_key=_key("cli.app.live.borrador.modelo_100_help"),
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
        key="app_live_borrador_100_list",
        parent_key="app_live_borrador_100",
        token="list",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.borrador.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="state",
                declarations=("--state",),
                value=ValueContract(DeferredTarget("cadrumo.application.live.snapshot_base", "SnapshotStateFilter")),
                default=ParameterDefault.value("active"),
                help_key=_key("cli.app.live.borrador.state_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
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
            DeferredTarget("cadrumo.entrypoints.cli._app_live_borrador_cli", "borrador_100_list")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_borrador_payloads", "Borrador100ListResult"),
            identity="app.live.borrador.100.list",
        ),
    ),
    CommandSpec(
        key="app_live_borrador_100_view",
        parent_key="app_live_borrador_100",
        token="view",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.borrador.view_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="snapshot_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.borrador.snapshot_id_help"),
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
            DeferredTarget("cadrumo.entrypoints.cli._app_live_borrador_cli", "borrador_100_show")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_borrador_payloads", "Borrador100ViewResult"),
            identity="app.live.borrador.100.view",
        ),
    ),
    CommandSpec(
        key="app_live_borrador_100_latest",
        parent_key="app_live_borrador_100",
        token="latest",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.borrador.latest_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="filing_year",
                declarations=("--filing-year",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.borrador.filing_year_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=2000, maximum=2099),
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
            DeferredTarget("cadrumo.entrypoints.cli._app_live_borrador_cli", "borrador_100_latest")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_borrador_payloads", "Borrador100LatestResult"),
            identity="app.live.borrador.100.latest",
        ),
    ),
)

__all__ = ["LIVE_BORRADOR_COMMAND_SPECS"]
