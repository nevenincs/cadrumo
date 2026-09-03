"""Shared immutable building blocks for live CommandSpec declarations."""

from __future__ import annotations

from typing import Final

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from .command_spec import (
    CommandWriteRoute,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
)
from .command_spec import (
    translation_key as _key,
)

_METADATA_GROUP_INVOCATION: Final[InvocationSpec] = InvocationSpec(
    no_args_is_help=True,
    context_parameter=None,
)
_LEAF_INVOCATION: Final[InvocationSpec] = InvocationSpec(
    no_args_is_help=False,
    context_parameter="ctx",
)
_METADATA_POLICY: Final[ExecutionPolicySpec] = ExecutionPolicySpec(
    capabilities=frozenset(["state-free"]),
    side_effects=frozenset(["none"]),
    performance="metadata",
    write_route=CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
    live_write=False,
)
_ENCRYPTED_LOCAL_READ_POLICY: Final[ExecutionPolicySpec] = ExecutionPolicySpec(
    capabilities=frozenset(["encrypted-facts"]),
    side_effects=frozenset(["none"]),
    performance="local-io",
    write_route=CommandWriteRoute.NONE,
    destructive=False,
    handoff=False,
    live_write=False,
)
_PROFILE_BOUND_NETWORK_CAPTURE_POLICY: Final[ExecutionPolicySpec] = ExecutionPolicySpec(
    capabilities=frozenset(["encrypted-facts", "network"]),
    side_effects=frozenset(["local-state", "network"]),
    performance="external-io",
    write_route=CommandWriteRoute.PROFILE_BOUND,
    destructive=False,
    handoff=False,
    live_write=False,
)
NO_RESULT_SCHEMA: Final[ResultSchemaSpec] = ResultSchemaSpec(SchemaState.NOT_SUPPORTED)

_OPTIONAL_YEAR_FROM_OPTION: Final[OptionSpec] = OptionSpec(
    name="year_from",
    declarations=("--from-year",),
    value=ValueContract(DeferredTarget("builtins", "int")),
    default=ParameterDefault.value(None),
    help_key=_key("cli.app.live.from_year_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(minimum=2000, maximum=2099),
)
_OPTIONAL_YEAR_TO_OPTION: Final[OptionSpec] = OptionSpec(
    name="year_to",
    declarations=("--to-year",),
    value=ValueContract(DeferredTarget("builtins", "int")),
    default=ParameterDefault.value(None),
    help_key=_key("cli.app.live.to_year_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(minimum=2000, maximum=2099),
)
_OUTPUT_ROOT_OPTION: Final[OptionSpec] = OptionSpec(
    name="output_root",
    declarations=("--output-root",),
    value=ValueContract(DeferredTarget("pathlib", "Path")),
    default=ParameterDefault.value(None),
    help_key=_key("cli.app.live.output_root_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(minimum=None, maximum=None),
    transport_locus=TransportLocus.LOCAL_OUT,
    transport_shape=TransportShape.DIRECTORY,
    transport_role=TransportRole.PRIMARY,
)
_REQUIRED_MODELO_OPTION: Final[OptionSpec] = OptionSpec(
    name="modelo",
    declarations=("--modelo",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.required(),
    help_key=_key("cli.app.live.modelo_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(minimum=None, maximum=None),
)
_REQUIRED_YEAR_OPTION: Final[OptionSpec] = OptionSpec(
    name="year",
    declarations=("--year",),
    value=ValueContract(DeferredTarget("builtins", "int")),
    default=ParameterDefault.required(),
    help_key=_key("cli.app.live.year_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(minimum=2000, maximum=2099),
)
_REQUIRED_PERIOD_OPTION: Final[OptionSpec] = OptionSpec(
    name="period",
    declarations=("--period",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.required(),
    help_key=_key("cli.app.live.period_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(minimum=None, maximum=None),
)
_OPTIONAL_TAXPAYER_NIF_OPTION: Final[OptionSpec] = OptionSpec(
    name="taxpayer_nif",
    declarations=("--taxpayer-nif",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=_key("cli.app.live.iva_wallet.taxpayer_nif_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(minimum=None, maximum=None),
)
_REQUIRED_YEAR_FROM_OPTION: Final[OptionSpec] = OptionSpec(
    name="year_from",
    declarations=("--from-year",),
    value=ValueContract(DeferredTarget("builtins", "int")),
    default=ParameterDefault.required(),
    help_key=_key("cli.app.live.from_year_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(minimum=2000, maximum=2099),
)
_REQUIRED_YEAR_TO_OPTION: Final[OptionSpec] = OptionSpec(
    name="year_to",
    declarations=("--to-year",),
    value=ValueContract(DeferredTarget("builtins", "int")),
    default=ParameterDefault.required(),
    help_key=_key("cli.app.live.to_year_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(minimum=2000, maximum=2099),
)

__all__ = [
    "NO_RESULT_SCHEMA",
    "_ENCRYPTED_LOCAL_READ_POLICY",
    "_LEAF_INVOCATION",
    "_METADATA_GROUP_INVOCATION",
    "_METADATA_POLICY",
    "_OPTIONAL_TAXPAYER_NIF_OPTION",
    "_OPTIONAL_YEAR_FROM_OPTION",
    "_OPTIONAL_YEAR_TO_OPTION",
    "_OUTPUT_ROOT_OPTION",
    "_PROFILE_BOUND_NETWORK_CAPTURE_POLICY",
    "_REQUIRED_MODELO_OPTION",
    "_REQUIRED_PERIOD_OPTION",
    "_REQUIRED_YEAR_FROM_OPTION",
    "_REQUIRED_YEAR_OPTION",
    "_REQUIRED_YEAR_TO_OPTION",
    "_key",
]
