"""Authored CommandSpec declarations for the live portals service."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._app_live_command_spec_support import _key
from .command_spec import (
    ArgumentSpec,
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

LIVE_PORTALS_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_live_portals",
        parent_key="app_live",
        token="portals",
        kind="group",
        help_key=_key("cli.app.live.portals.app_help"),
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
        key="app_live_portals_list",
        parent_key="app_live_portals",
        token="list",
        kind="leaf",
        help_key=_key("cli.app.live.portals.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="category",
                declarations=("--category",),
                value=ValueContract(DeferredTarget("cadrumo.domain.portals.categories", "PortalCategory")),
                default=ParameterDefault.value(None),
                help_key=_key("cli.app.live.portals.category_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
            OptionSpec(
                name="modelo",
                declarations=("--modelo",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=_key("cli.app.live.portals.modelo_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["state-free"]),
            side_effects=frozenset(["none"]),
            performance="metadata",
            write_route=CommandWriteRoute.NONE,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_portals_cli", "portals_list")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_portals_payloads", "PortalsListResult"),
            identity="app.live.portals.list",
        ),
    ),
    CommandSpec(
        key="app_live_portals_view",
        parent_key="app_live_portals",
        token="view",
        kind="leaf",
        help_key=_key("cli.app.live.portals.view_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="portal_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.portals.portal_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["state-free"]),
            side_effects=frozenset(["none"]),
            performance="metadata",
            write_route=CommandWriteRoute.NONE,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_portals_cli", "portals_show")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_portals_payloads", "PortalsViewResult"),
            identity="app.live.portals.view",
        ),
    ),
)

__all__ = ["LIVE_PORTALS_COMMAND_SPECS"]
