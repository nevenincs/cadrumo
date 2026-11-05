"""Declare the command specs for the non-work modelo bindings commands."""

from __future__ import annotations

from typing import Final

from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.shared_contracts import (
    DeferredTarget,
    LazyBinding,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from cadrumo_client.commands.spec import CommandSpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind

from .modelo_nonwork_command_spec_policies import REGISTRY_MODEL_READ

MODELO_OPTION: Final[OptionSpec] = OptionSpec(
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
YEAR_OPTION: Final[OptionSpec] = OptionSpec(
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
PERIOD_OPTION: Final[OptionSpec] = OptionSpec(
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
AS_OF_OPTION: Final[OptionSpec] = OptionSpec(
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
BINDINGS_SCOPE: Final[tuple[OptionSpec, ...]] = (MODELO_OPTION, YEAR_OPTION, PERIOD_OPTION)
BINDINGS_INVOCATION: Final[InvocationSpec] = InvocationSpec(context_parameter="ctx")

MODELO_NONWORK_BINDINGS_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_modelo_bindings_list",
        "app_modelo_bindings",
        "list",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.bindings.list_help"),
        short_help_key=None,
        invocation=BINDINGS_INVOCATION,
        parameters=(
            *BINDINGS_SCOPE,
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
            AS_OF_OPTION,
        ),
        policy=REGISTRY_MODEL_READ,
        handler=LazyBinding.available(DeferredTarget(".modelo_discovery_commands", "bindings_list", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(".modelo_bindings_results", "ModeloBindingsListResult", __package__),
            identity="modelo.bindings.list",
        ),
    ),
    CommandSpec(
        "app_modelo_bindings_resolve",
        "app_modelo_bindings",
        "resolve",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.bindings.resolve_help"),
        short_help_key=None,
        invocation=BINDINGS_INVOCATION,
        parameters=(
            *BINDINGS_SCOPE,
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
            AS_OF_OPTION,
        ),
        policy=REGISTRY_MODEL_READ,
        handler=LazyBinding.available(DeferredTarget(".modelo_discovery_commands", "bindings_resolve", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(".modelo_bindings_results", "ModeloBindingsPreviewResult", __package__),
            identity="modelo.bindings.resolve",
        ),
    ),
)

__all__ = ["MODELO_NONWORK_BINDINGS_COMMAND_SPECS"]
"""Authored CommandSpec declarations for the Modelo non-work bindings family."""
"""Authored CommandSpec declarations for the Modelo non-work bindings family."""
