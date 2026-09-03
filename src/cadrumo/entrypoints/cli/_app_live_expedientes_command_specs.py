"""Authored CommandSpec declarations for the live expedientes service."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._app_live_command_spec_support import (
    _ENCRYPTED_LOCAL_READ_POLICY,
    _LEAF_INVOCATION,
    _METADATA_GROUP_INVOCATION,
    _METADATA_POLICY,
    _OPTIONAL_MODELOS_OPTION,
    _OPTIONAL_YEAR_FROM_OPTION,
    _OPTIONAL_YEAR_OPTION,
    _OPTIONAL_YEAR_TO_OPTION,
    _PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
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

LIVE_EXPEDIENTES_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_live_expedientes",
        parent_key="app_live",
        token="expedientes",
        kind=CommandNodeKind.GROUP,
        help_key=_key("cli.app.live.expedientes.app_help"),
        short_help_key=None,
        invocation=_METADATA_GROUP_INVOCATION,
        parameters=(),
        policy=_METADATA_POLICY,
        handler=None,
        result_schema=NO_RESULT_SCHEMA,
    ),
    CommandSpec(
        key="app_live_expedientes_pull",
        parent_key="app_live_expedientes",
        token="pull",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.expedientes.pull_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _OPTIONAL_MODELOS_OPTION,
            _OPTIONAL_YEAR_OPTION,
            _OPTIONAL_YEAR_FROM_OPTION,
            _OPTIONAL_YEAR_TO_OPTION,
        ),
        policy=_PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_expedientes_cli", "expedientes_pull")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_expedientes_payloads", "ExpedientesCaptureResult"),
            identity="app.live.expedientes.pull",
        ),
    ),
    CommandSpec(
        key="app_live_expedientes_list",
        parent_key="app_live_expedientes",
        token="list",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.expedientes.list_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_expedientes_cli", "expedientes_list")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_expedientes_payloads", "ExpedientesListResult"),
            identity="app.live.expedientes.list",
        ),
    ),
    CommandSpec(
        key="app_live_expedientes_view",
        parent_key="app_live_expedientes",
        token="view",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.expedientes.view_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            ArgumentSpec(
                name="snapshot_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.expedientes.snapshot_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_expedientes_cli", "expedientes_show")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_expedientes_payloads", "ExpedientesViewResult"),
            identity="app.live.expedientes.view",
        ),
    ),
    CommandSpec(
        key="app_live_expedientes_latest",
        parent_key="app_live_expedientes",
        token="latest",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.expedientes.latest_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_expedientes_cli", "expedientes_latest")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_expedientes_payloads", "ExpedientesLatestResult"),
            identity="app.live.expedientes.latest",
        ),
    ),
)

__all__ = ["LIVE_EXPEDIENTES_COMMAND_SPECS"]
