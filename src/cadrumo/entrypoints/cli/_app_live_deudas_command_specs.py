"""Authored CommandSpec declarations for the live deudas service."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._app_live_command_spec_support import (
    _ENCRYPTED_LOCAL_READ_POLICY,
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
        kind=CommandNodeKind.GROUP,
        help_key=_key("cli.app.live.deudas.app_help"),
        short_help_key=None,
        invocation=_METADATA_GROUP_INVOCATION,
        parameters=(),
        policy=_METADATA_POLICY,
        handler=None,
        result_schema=NO_RESULT_SCHEMA,
    ),
    CommandSpec(
        key="app_live_deudas_list",
        parent_key="app_live_deudas",
        token="list",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.deudas.list_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_deudas_cli", "deudas_list")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_deudas_payloads", "DeudasListResult"),
            identity="app.live.deudas.list",
        ),
    ),
    CommandSpec(
        key="app_live_deudas_view",
        parent_key="app_live_deudas",
        token="view",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.deudas.view_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            ArgumentSpec(
                name="snapshot_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.deudas.snapshot_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_deudas_cli", "deudas_view")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_deudas_payloads", "DeudasViewResult"),
            identity="app.live.deudas.view",
        ),
    ),
    CommandSpec(
        key="app_live_deudas_latest",
        parent_key="app_live_deudas",
        token="latest",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.deudas.latest_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_live_deudas_cli", "deudas_latest")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_deudas_payloads", "DeudasLatestResult"),
            identity="app.live.deudas.latest",
        ),
    ),
)

__all__ = ["LIVE_DEUDAS_COMMAND_SPECS"]
