from __future__ import annotations

from typing import Final

from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.shared_contracts import (
    TEXT_VALUE,
    WHOLE_NUMBER_VALUE,
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

from ._app_ledger_command_spec_policies import _POLICY_4, _POLICY_5

_CLI_MODULE: Final[str] = ".retencion_soportada_absence_commands"
_RESULT_MODULE: Final[str] = ".retencion_soportada_absence_results"
_PARENT: Final[str] = "app_ledger_retencion_soportada"

_CLASS_VALUE: Final[ValueContract] = ValueContract(
    DeferredTarget("...core.retencion_soportada", "RetencionSoportadaClase", __package__)
)
_REQUIRED: Final[ParameterDefault] = ParameterDefault.required()
_OPTIONAL: Final[ParameterDefault] = ParameterDefault.value(None)
_LEAF_INVOCATION: Final[InvocationSpec] = InvocationSpec(
    invoke_without_command=False,
    no_args_is_help=False,
    context_parameter="ctx",
)


def _option(
    *, name: str, declaration: str, value: ValueContract, default: ParameterDefault, help_key: str
) -> OptionSpec:
    """Build one ordinary non-flag option."""
    return OptionSpec(
        name=name,
        declarations=(declaration,),
        value=value,
        default=default,
        help_key=TranslationKey(help_key),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=False,
        count=False,
        eager=False,
        constraint=ParameterConstraint(),
        show_default=True,
        hidden=False,
    )


_EJERCICIO_OPTION: Final[OptionSpec] = _option(
    name="ejercicio",
    declaration="--ejercicio",
    value=WHOLE_NUMBER_VALUE,
    default=_REQUIRED,
    help_key="cli.app.ledger.retencion_soportada.ejercicio_help",
)
_INCOME_CLASS_OPTION: Final[OptionSpec] = _option(
    name="income_class",
    declaration="--income-class",
    value=_CLASS_VALUE,
    default=_REQUIRED,
    help_key="cli.app.ledger.retencion_soportada.income_class_help",
)


def _result_schema(model: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget(_RESULT_MODULE, model, __package__),
        identity=identity,
    )


LEDGER_RETENCION_SOPORTADA_ABSENCE_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_ledger_retencion_soportada_attest_absence",
        _PARENT,
        "attest-absence",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.retencion_soportada.attest_absence_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _EJERCICIO_OPTION,
            _INCOME_CLASS_OPTION,
            _option(
                name="note",
                declaration="--note",
                value=TEXT_VALUE,
                default=_REQUIRED,
                help_key="cli.app.ledger.retencion_soportada.absence_note_help",
            ),
            _option(
                name="expected_revision",
                declaration="--expected-revision",
                value=TEXT_VALUE,
                default=_OPTIONAL,
                help_key="cli.app.ledger.retencion_soportada.attest_absence_expected_revision_help",
            ),
        ),
        policy=_POLICY_4,
        handler=LazyBinding.available(DeferredTarget(_CLI_MODULE, "retencion_soportada_attest_absence", __package__)),
        result_schema=_result_schema(
            "RetencionSoportadaAttestAbsenceResult", "ledger.retencion_soportada.attest_absence"
        ),
    ),
    CommandSpec(
        "app_ledger_retencion_soportada_list_absences",
        _PARENT,
        "list-absences",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.retencion_soportada.list_absences_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(_EJERCICIO_OPTION,),
        policy=_POLICY_5,
        handler=LazyBinding.available(DeferredTarget(_CLI_MODULE, "retencion_soportada_list_absences", __package__)),
        result_schema=_result_schema(
            "RetencionSoportadaListAbsencesResult", "ledger.retencion_soportada.list_absences"
        ),
    ),
    CommandSpec(
        "app_ledger_retencion_soportada_withdraw_absence",
        _PARENT,
        "withdraw-absence",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.retencion_soportada.withdraw_absence_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _EJERCICIO_OPTION,
            _INCOME_CLASS_OPTION,
            _option(
                name="expected_revision",
                declaration="--expected-revision",
                value=TEXT_VALUE,
                default=_REQUIRED,
                help_key="cli.app.ledger.retencion_soportada.withdraw_absence_expected_revision_help",
            ),
        ),
        policy=_POLICY_4,
        handler=LazyBinding.available(DeferredTarget(_CLI_MODULE, "retencion_soportada_withdraw_absence", __package__)),
        result_schema=_result_schema(
            "RetencionSoportadaWithdrawAbsenceResult", "ledger.retencion_soportada.withdraw_absence"
        ),
    ),
)

__all__ = ["LEDGER_RETENCION_SOPORTADA_ABSENCE_COMMAND_SPECS"]
