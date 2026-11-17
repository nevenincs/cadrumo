"""Declare the command specs for the retencion soportada absence ledger commands."""

from __future__ import annotations

from typing import Final

from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.shared_contracts import (
    TEXT_VALUE,
    WHOLE_NUMBER_VALUE,
    DeferredTarget,
    LazyBinding,
    ParameterDefault,
    TranslationKey,
    ValueContract,
)
from cadrumo_client.commands.spec import CommandSpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind

from .app_ledger_command_spec_policies import POLICY_4, POLICY_5
from .ledger_command_fragments import option, result_schema

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


_EJERCICIO_OPTION: Final[OptionSpec] = option(
    name="ejercicio",
    declaration="--ejercicio",
    value=WHOLE_NUMBER_VALUE,
    default=_REQUIRED,
    help_key="cli.app.ledger.retencion_soportada.ejercicio_help",
)
_INCOME_CLASS_OPTION: Final[OptionSpec] = option(
    name="income_class",
    declaration="--income-class",
    value=_CLASS_VALUE,
    default=_REQUIRED,
    help_key="cli.app.ledger.retencion_soportada.income_class_help",
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
            option(
                name="note",
                declaration="--note",
                value=TEXT_VALUE,
                default=_REQUIRED,
                help_key="cli.app.ledger.retencion_soportada.absence_note_help",
            ),
            option(
                name="expected_revision",
                declaration="--expected-revision",
                value=TEXT_VALUE,
                default=_OPTIONAL,
                help_key="cli.app.ledger.retencion_soportada.attest_absence_expected_revision_help",
            ),
        ),
        policy=POLICY_4,
        handler=LazyBinding.available(DeferredTarget(_CLI_MODULE, "retencion_soportada_attest_absence", __package__)),
        result_schema=result_schema(
            "RetencionSoportadaAttestAbsenceResult",
            "ledger.retencion_soportada.attest_absence",
            result_module=_RESULT_MODULE,
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
        policy=POLICY_5,
        handler=LazyBinding.available(DeferredTarget(_CLI_MODULE, "retencion_soportada_list_absences", __package__)),
        result_schema=result_schema(
            "RetencionSoportadaListAbsencesResult",
            "ledger.retencion_soportada.list_absences",
            result_module=_RESULT_MODULE,
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
            option(
                name="expected_revision",
                declaration="--expected-revision",
                value=TEXT_VALUE,
                default=_REQUIRED,
                help_key="cli.app.ledger.retencion_soportada.withdraw_absence_expected_revision_help",
            ),
        ),
        policy=POLICY_4,
        handler=LazyBinding.available(DeferredTarget(_CLI_MODULE, "retencion_soportada_withdraw_absence", __package__)),
        result_schema=result_schema(
            "RetencionSoportadaWithdrawAbsenceResult",
            "ledger.retencion_soportada.withdraw_absence",
            result_module=_RESULT_MODULE,
        ),
    ),
)

__all__ = ["LEDGER_RETENCION_SOPORTADA_ABSENCE_COMMAND_SPECS"]
