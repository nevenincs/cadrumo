"""Authored CommandSpec declarations for the live portals service."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._app_live_command_spec_support import (
    _LEAF_INVOCATION,
    _METADATA_GROUP_INVOCATION,
    _METADATA_POLICY,
    NO_RESULT_SCHEMA,
    _key,
)
from .command_spec import (
    ArgumentSpec,
    CommandNodeKind,
    CommandSpec,
    DeferredTarget,
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
        kind=CommandNodeKind.GROUP,
        help_key=_key("cli.app.live.portals.app_help"),
        short_help_key=None,
        invocation=_METADATA_GROUP_INVOCATION,
        parameters=(),
        policy=_METADATA_POLICY,
        handler=None,
        result_schema=NO_RESULT_SCHEMA,
    ),
    CommandSpec(
        key="app_live_portals_list",
        parent_key="app_live_portals",
        token="list",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.portals.list_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
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
        policy=_METADATA_POLICY,
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
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.portals.view_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            ArgumentSpec(
                name="portal_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.portals.portal_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=_METADATA_POLICY,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_portals_cli", "portals_show")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_portals_payloads", "PortalsViewResult"),
            identity="app.live.portals.view",
        ),
    ),
)

__all__ = ["LIVE_PORTALS_COMMAND_SPECS"]
