"""Authored CommandSpec declarations for the ``app modelo m360`` solicitud surface."""

from __future__ import annotations

from cadrumo.application.operator_surface.command_ports import CommandNodeKind

from ._command_secret_contracts import (
    MachineSecretFieldSpec,
    MachineSecretSpec,
    MachineSecretVariantSpec,
)
from ._modelo_nonwork_command_spec_policies import _METADATA, _MODEL_READ, _MODEL_WRITE
from .command_parameter_contracts import ArgumentSpec, ParameterSpec
from .command_shared_contracts import (
    DeferredTarget,
    LazyBinding,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from .command_spec import CommandSpec, ExecutionPolicySpec, InvocationSpec
from .machine_secret_command_parameters import MACHINE_SECRET_FD_OPTION, MACHINE_SECRET_STDIN_OPTION

_GROUP = "app_modelo_m360"
_FILING_YEAR = ArgumentSpec(
    name="filing_year",
    value=ValueContract(DeferredTarget("builtins", "int")),
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.app.modelo.m360.filing_year_help"),
)


def _leaf(
    verb: str,
    parameters: tuple[ParameterSpec, ...],
    *,
    policy: ExecutionPolicySpec,
    result: str,
    machine_secret: MachineSecretSpec | None = None,
) -> CommandSpec:
    return CommandSpec(
        f"{_GROUP}_{verb}",
        _GROUP,
        verb,
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey(f"cli.app.modelo.m360.{verb}_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=parameters,
        policy=policy,
        handler=LazyBinding.available(DeferredTarget("._modelo_m360_cli", f"m360_{verb}", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._modelo_m360_payloads", result, __package__),
            identity=f"modelo.m360.{verb}",
        ),
        machine_secret=machine_secret,
    )


MODELO_M360_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        _GROUP,
        "app_modelo",
        "m360",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.app.modelo.m360.group_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=_METADATA,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    _leaf(
        "declare",
        (_FILING_YEAR, MACHINE_SECRET_STDIN_OPTION, MACHINE_SECRET_FD_OPTION),
        policy=_MODEL_WRITE,
        result="Modelo360SolicitudChangeResult",
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "solicitud",
                    (MachineSecretFieldSpec("solicitud"),),
                    DeferredTarget("._modelo_m360_cli", "Modelo360SolicitudSecrets", __package__),
                ),
            ),
        ),
    ),
    _leaf("list", (), policy=_MODEL_READ, result="Modelo360SolicitudListResult"),
    _leaf("remove", (_FILING_YEAR,), policy=_MODEL_WRITE, result="Modelo360SolicitudChangeResult"),
)

__all__ = ["MODELO_M360_COMMAND_SPECS"]
