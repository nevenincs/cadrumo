"""Authored CommandSpec declarations for the live expedientes service."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._app_live_command_spec_support import _key
from ._command_spec import (
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

LIVE_EXPEDIENTES_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_live_expedientes",
        parent_key="app_live",
        token="expedientes",
        kind="group",
        help_key=_key("cli.app.live.expedientes.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True, context_parameter=None),
        parameters=(),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["state-free"]),
            side_effects=frozenset(["none"]),
            performance="metadata",
            write_route="none",
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="app_live_expedientes_pull",
        parent_key="app_live_expedientes",
        token="pull",
        kind="leaf",
        help_key=_key("cli.app.live.expedientes.pull_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="modelos",
                declarations=("--modelo",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(()),
                help_key=_key("cli.app.live.filed.pull_modelo_help"),
                multiple=True,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
            OptionSpec(
                name="year",
                declarations=("--year",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.value(None),
                help_key=_key("cli.app.live.year_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=2000, maximum=2099),
            ),
            OptionSpec(
                name="year_from",
                declarations=("--from-year",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.value(None),
                help_key=_key("cli.app.live.from_year_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=2000, maximum=2099),
            ),
            OptionSpec(
                name="year_to",
                declarations=("--to-year",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.value(None),
                help_key=_key("cli.app.live.to_year_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=2000, maximum=2099),
            ),
        ),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts", "network"]),
            side_effects=frozenset(["local-state", "network"]),
            performance="external-io",
            write_route="profile-bound",
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_expedientes_cli", "expedientes_pull")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_payloads", "ExpedientesCaptureResult"),
            identity="app.live.expedientes.pull",
        ),
    ),
    CommandSpec(
        key="app_live_expedientes_list",
        parent_key="app_live_expedientes",
        token="list",
        kind="leaf",
        help_key=_key("cli.app.live.expedientes.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts"]),
            side_effects=frozenset(["none"]),
            performance="local-io",
            write_route="none",
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_expedientes_cli", "expedientes_list")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_payloads", "ExpedientesListResult"),
            identity="app.live.expedientes.list",
        ),
    ),
    CommandSpec(
        key="app_live_expedientes_view",
        parent_key="app_live_expedientes",
        token="view",
        kind="leaf",
        help_key=_key("cli.app.live.expedientes.view_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="snapshot_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.expedientes.snapshot_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts"]),
            side_effects=frozenset(["none"]),
            performance="local-io",
            write_route="none",
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_expedientes_cli", "expedientes_show")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_payloads", "ExpedientesViewResult"),
            identity="app.live.expedientes.view",
        ),
    ),
    CommandSpec(
        key="app_live_expedientes_latest",
        parent_key="app_live_expedientes",
        token="latest",
        kind="leaf",
        help_key=_key("cli.app.live.expedientes.latest_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts"]),
            side_effects=frozenset(["none"]),
            performance="local-io",
            write_route="none",
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_expedientes_cli", "expedientes_latest")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_payloads", "ExpedientesLatestResult"),
            identity="app.live.expedientes.latest",
        ),
    ),
)

__all__ = ["LIVE_EXPEDIENTES_COMMAND_SPECS"]
