"""Import-light command authority for modelo projection and comparison."""

from __future__ import annotations

from ...core.modelo import Modelo
from .command_spec import (
    CommandSpec,
    CommandWriteRoute,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

_CALCULATION_READ = ExecutionPolicySpec(
    frozenset({"calculation", "encrypted-facts"}), frozenset({"none"}), "compute", CommandWriteRoute.NONE
)
_STR = ValueContract(DeferredTarget("builtins", "str"))
_INT = ValueContract(DeferredTarget("builtins", "int"))
_MODELO = ValueContract(
    DeferredTarget("builtins", "str"),
    click_type=DeferredTarget("cadrumo.entrypoints.cli._common", "MODELO_CODE_CHOICE"),
)


def _option(
    name: str,
    declarations: tuple[str, ...],
    value: ValueContract,
    help_key: str,
    *,
    required: bool = False,
    default: str | tuple[int, ...] | tuple[str, ...] | None = None,
    multiple: bool = False,
) -> OptionSpec:
    return OptionSpec(
        name,
        declarations,
        value,
        ParameterDefault.required() if required else ParameterDefault.value(default),
        TranslationKey(help_key),
        multiple=multiple,
    )


def _leaf(
    key: str,
    token: str,
    help_key: str,
    handler: str,
    parameters: tuple[OptionSpec, ...],
    schema_name: str,
) -> CommandSpec:
    return CommandSpec(
        key,
        "app_modelo",
        token,
        "leaf",
        TranslationKey(help_key),
        None,
        InvocationSpec(context_parameter="ctx"),
        parameters,
        _CALCULATION_READ,
        LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._modelo_projection_cli", handler)),
        ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads", schema_name),
            identity=f"modelo.{token}",
        ),
    )


MODELO_PROJECTION_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    _leaf(
        "app_modelo_project",
        "project",
        "cli.app.modelo.project_help",
        "modelo_project",
        (
            _option("year", ("--year",), _INT, "cli.app.modelo.project.year_help", required=True),
            _option("ccaa", ("--ccaa",), _STR, "cli.app.modelo.project.ccaa_help", required=True),
            _option(
                "casilla",
                ("--casilla",),
                _STR,
                "cli.app.modelo.project.casilla_help",
                default=(),
                multiple=True,
            ),
            _option(
                "binding",
                ("--binding",),
                _STR,
                "cli.app.modelo.project.binding_help",
                default=(),
                multiple=True,
            ),
        ),
        "ModeloProjectResult",
    ),
    _leaf(
        "app_modelo_compare",
        "compare",
        "cli.app.modelo.compare_help",
        "modelo_compare",
        (
            _option(
                "year",
                ("--year",),
                _INT,
                "cli.app.modelo.compare.year_help",
                default=(),
                multiple=True,
            ),
            _option(
                "modelo",
                ("--modelo",),
                _MODELO,
                "cli.app.modelo.compare.modelo_help",
                default=Modelo.M100.value,
            ),
        ),
        "ModeloCompareResult",
    ),
)

__all__ = ["MODELO_PROJECTION_COMMAND_SPECS"]
