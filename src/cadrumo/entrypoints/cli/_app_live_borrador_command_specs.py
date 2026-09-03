"""Authored CommandSpec declarations for the live borrador service."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ...core.modelo import Modelo
from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from ._app_live_command_spec_support import (
    _ENCRYPTED_LOCAL_READ_POLICY,
    _LEAF_INVOCATION,
    _METADATA_GROUP_INVOCATION,
    _METADATA_POLICY,
    _REQUIRED_FILING_YEAR_OPTION,
    NO_RESULT_SCHEMA,
    _key,
)
from .command_spec import (
    ArgumentSpec,
    CommandNodeKind,
    CommandSpec,
    CommandWriteRoute,
    DeferredTarget,
    ExecutionPolicySpec,
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
        invocation=_METADATA_GROUP_INVOCATION,
        parameters=(),
        policy=_METADATA_POLICY,
        handler=None,
        result_schema=NO_RESULT_SCHEMA,
    ),
    CommandSpec(
        key="app_live_borrador_100",
        parent_key="app_live_borrador",
        token=Modelo.M100.value,
        kind=CommandNodeKind.GROUP,
        help_key=_key("cli.app.live.borrador.modelo_100_help"),
        short_help_key=None,
        invocation=_METADATA_GROUP_INVOCATION,
        parameters=(),
        policy=_METADATA_POLICY,
        handler=None,
        result_schema=NO_RESULT_SCHEMA,
    ),
    CommandSpec(
        key="app_live_borrador_100_import",
        parent_key="app_live_borrador_100",
        token="import",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.borrador.import_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            OptionSpec(
                name="file",
                declarations=("--file",),
                value=ValueContract(DeferredTarget("pathlib", "Path")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.borrador.import_file_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(exists=True, dir_okay=False),
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            _REQUIRED_FILING_YEAR_OPTION,
            OptionSpec(
                name="period",
                declarations=("--period",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value("0A"),
                help_key=_key("cli.app.live.borrador.import_period_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["registry", "encrypted-facts"]),
            side_effects=frozenset(["local-state"]),
            performance="local-io",
            write_route=CommandWriteRoute.PROFILE_BOUND,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_borrador_cli", "borrador_100_import")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._app_live_borrador_payloads", "Borrador100ImportResult"),
            identity="app.live.borrador.100.import",
        ),
    ),
    CommandSpec(
        key="app_live_borrador_100_list",
        parent_key="app_live_borrador_100",
        token="list",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.borrador.list_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
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
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
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
        invocation=_LEAF_INVOCATION,
        parameters=(
            ArgumentSpec(
                name="snapshot_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.borrador.snapshot_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
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
        invocation=_LEAF_INVOCATION,
        parameters=(_REQUIRED_FILING_YEAR_OPTION,),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
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
