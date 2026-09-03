"""Authored CommandSpec declarations for the Modelo non-work bindings family."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from typing import Final

from ._modelo_nonwork_command_spec_policies import _REGISTRY_MODEL_READ
from .command_spec import (
    CommandNodeKind,
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

_MODELO_OPTION: Final[OptionSpec] = OptionSpec(
    name="modelo",
    declarations=("--modelo",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.modelo.bindings.modelo_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)
_YEAR_OPTION: Final[OptionSpec] = OptionSpec(
    name="year",
    declarations=("--year",),
    value=ValueContract(DeferredTarget("builtins", "int")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.modelo.bindings.year_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)
_PERIOD_OPTION: Final[OptionSpec] = OptionSpec(
    name="period",
    declarations=("--period",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.modelo.bindings.period_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)
_AS_OF_OPTION: Final[OptionSpec] = OptionSpec(
    name="as_of",
    declarations=("--as-of",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.modelo.bindings.as_of_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)
_BINDINGS_SCOPE: Final[tuple[OptionSpec, ...]] = (_MODELO_OPTION, _YEAR_OPTION, _PERIOD_OPTION)
_BINDINGS_INVOCATION: Final[InvocationSpec] = InvocationSpec(context_parameter="ctx")

MODELO_NONWORK_BINDINGS_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_modelo_bindings_list",
        parent_key="app_modelo_bindings",
        token="list",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.bindings.list_help"),
        short_help_key=None,
        invocation=_BINDINGS_INVOCATION,
        parameters=(
            *_BINDINGS_SCOPE,
            OptionSpec(
                name="missing",
                declarations=("--missing",),
                value=ValueContract(DeferredTarget("builtins", "bool")),
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.app.modelo.bindings.missing_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
            _AS_OF_OPTION,
        ),
        policy=_REGISTRY_MODEL_READ,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._modelo_discovery_cli", "bindings_list")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_bindings_payloads", "ModeloBindingsListResult"),
            identity="modelo.bindings.list",
        ),
    ),
    CommandSpec(
        key="app_modelo_bindings_resolve",
        parent_key="app_modelo_bindings",
        token="resolve",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.bindings.resolve_help"),
        short_help_key=None,
        invocation=_BINDINGS_INVOCATION,
        parameters=(
            *_BINDINGS_SCOPE,
            OptionSpec(
                name="binding",
                declarations=("--binding",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(()),
                help_key=TranslationKey("cli.app.modelo.bindings.override_help"),
                multiple=True,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
            _AS_OF_OPTION,
        ),
        policy=_REGISTRY_MODEL_READ,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_discovery_cli", "bindings_resolve")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_bindings_payloads", "ModeloBindingsPreviewResult"),
            identity="modelo.bindings.resolve",
        ),
    ),
)

__all__ = ["MODELO_NONWORK_BINDINGS_COMMAND_SPECS"]
