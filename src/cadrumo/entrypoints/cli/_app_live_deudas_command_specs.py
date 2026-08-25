"""Authored CommandSpec declarations for the live deudas service."""

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
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
)

LIVE_DEUDAS_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_live_deudas",
        parent_key="app_live",
        token="deudas",
        kind="group",
        help_key=_key("cli.app.live.deudas.app_help"),
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
        key="app_live_deudas_list",
        parent_key="app_live_deudas",
        token="list",
        kind="leaf",
        help_key=_key("cli.app.live.deudas.list_help"),
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
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_deudas_cli", "deudas_list")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_payloads", "DeudasListResult"),
            identity="app.live.deudas.list",
        ),
    ),
    CommandSpec(
        key="app_live_deudas_view",
        parent_key="app_live_deudas",
        token="view",
        kind="leaf",
        help_key=_key("cli.app.live.deudas.view_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="snapshot_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.deudas.snapshot_id_help"),
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
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_deudas_cli", "deudas_view")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_payloads", "DeudasViewResult"),
            identity="app.live.deudas.view",
        ),
    ),
    CommandSpec(
        key="app_live_deudas_latest",
        parent_key="app_live_deudas",
        token="latest",
        kind="leaf",
        help_key=_key("cli.app.live.deudas.latest_help"),
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
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_deudas_cli", "deudas_latest")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_payloads", "DeudasLatestResult"),
            identity="app.live.deudas.latest",
        ),
    ),
)

__all__ = ["LIVE_DEUDAS_COMMAND_SPECS"]
