"""Authored CommandSpec declarations for the live justificante service."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._app_live_command_spec_support import (
    _ENCRYPTED_LOCAL_READ_POLICY,
    _LEAF_INVOCATION,
    _METADATA_GROUP_INVOCATION,
    _METADATA_POLICY,
    _PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
    _REQUIRED_MODELO_OPTION,
    _REQUIRED_PERIOD_OPTION,
    _REQUIRED_YEAR_OPTION,
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

LIVE_JUSTIFICANTE_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_live_justificante",
        parent_key="app_live",
        token="justificante",
        kind=CommandNodeKind.GROUP,
        help_key=_key("cli.app.live.justificante.app_help"),
        short_help_key=None,
        invocation=_METADATA_GROUP_INVOCATION,
        parameters=(),
        policy=_METADATA_POLICY,
        handler=None,
        result_schema=NO_RESULT_SCHEMA,
    ),
    CommandSpec(
        key="app_live_justificante_pull",
        parent_key="app_live_justificante",
        token="pull",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.justificante.pull_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _REQUIRED_MODELO_OPTION,
            _REQUIRED_YEAR_OPTION,
            _REQUIRED_PERIOD_OPTION,
        ),
        policy=_PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
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
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.justificante.list_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
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
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.justificante.view_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            ArgumentSpec(
                name="snapshot_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.justificante.snapshot_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
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
