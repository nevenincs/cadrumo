"""Import-light CommandSpec authority for modelo readiness."""

from __future__ import annotations

from .command_spec import (
    CommandNodeKind,
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
    capabilities=frozenset({"calculation", "encrypted-facts"}),
    side_effects=frozenset({"none"}),
    performance="compute",
    write_route=CommandWriteRoute.NONE,
)
_STR = ValueContract(DeferredTarget("builtins", "str"))
_INT = ValueContract(DeferredTarget("builtins", "int"))
_MODELO = ValueContract(
    DeferredTarget("builtins", "str"),
    click_type=DeferredTarget("cadrumo.entrypoints.cli._common", "MODELO_CODE_CHOICE"),
)


def _required(name: str, flag: str, value: ValueContract, help_key: str) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=(flag,),
        value=value,
        default=ParameterDefault.required(),
        help_key=TranslationKey(help_key),
    )


def _option(name: str, flag: str, value: ValueContract, help_key: str) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=(flag,),
        value=value,
        default=ParameterDefault.value(None),
        help_key=TranslationKey(help_key),
    )


MODELO_READINESS_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_modelo_readiness",
        parent_key="app_modelo",
        token="readiness",  # noqa: S106 - CLI operator token, not a credential
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.readiness_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _required("modelo", "--modelo", _MODELO, "cli.app.modelo.readiness.modelo_help"),
            _required("filing_year", "--year", _INT, "cli.app.modelo.readiness.year_help"),
            _option("revision_id", "--revision-id", _STR, "cli.app.modelo.readiness.revision_help"),
            OptionSpec(
                name="period",
                declarations=("--period",),
                value=_STR,
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.readiness.period_help"),
            ),
        ),
        policy=_CALCULATION_READ,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_readiness_cli", "modelo_readiness")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads", "ModeloReadinessResult"),
            identity="modelo.readiness",
        ),
    ),
)

__all__ = ["MODELO_READINESS_COMMAND_SPECS"]
