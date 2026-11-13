"""Declare the command specs for the Modelo 232 related-party (operaciones vinculadas) ledger commands."""

from __future__ import annotations

from typing import Final

from cadrumo_client.commands.parameters import ArgumentSpec, OptionSpec
from cadrumo_client.commands.shared_contracts import (
    FLAG_VALUE,
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

from .app_ledger_command_spec_policies import POLICY_1, POLICY_4, POLICY_5

_CLI_MODULE: Final[str] = ".m232_related_party_commands"
_RESULT_MODULE: Final[str] = ".m232_related_party_results"
_GROUP: Final[str] = "app_ledger_operaciones_vinculadas"
_HELP: Final[str] = "cli.app.ledger.operaciones_vinculadas"
_DOMAIN: Final[str] = "...domain.modelos.m232_related_party"

_REQUIRED: Final[ParameterDefault] = ParameterDefault.required()
_OPTIONAL: Final[ParameterDefault] = ParameterDefault.value(None)
_LEAF_INVOCATION: Final[InvocationSpec] = InvocationSpec(
    invoke_without_command=False,
    no_args_is_help=False,
    context_parameter="ctx",
)


def _enum(name: str) -> ValueContract:
    return ValueContract(DeferredTarget(_DOMAIN, name, __package__))


def _option(
    name: str,
    declaration: str,
    *,
    value: ValueContract = TEXT_VALUE,
    default: ParameterDefault = _OPTIONAL,
    help_key: str | None = None,
) -> OptionSpec:
    """Build one ordinary non-flag option whose help sits under the group's key."""
    return OptionSpec(
        name=name,
        declarations=(declaration,),
        value=value,
        default=default,
        help_key=TranslationKey(f"{_HELP}.{help_key or name}_help"),
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


_EJERCICIO: Final[OptionSpec] = _option("ejercicio", "--ejercicio", value=WHOLE_NUMBER_VALUE, default=_REQUIRED)
_EXPECTED_GUARD_REVISION: Final[OptionSpec] = _option("expected_guard_revision", "--expected-guard-revision")
_EXPECTED_REVISION: Final[OptionSpec] = _option("expected_revision", "--expected-revision", default=_REQUIRED)
_SPECIFIC: Final[OptionSpec] = OptionSpec(
    name="specific",
    declarations=("--specific",),
    value=FLAG_VALUE,
    default=ParameterDefault.value(False),
    help_key=TranslationKey(f"{_HELP}.specific_help"),
    metavar=None,
    is_flag=True,
    flag_value=True,
    multiple=False,
    count=False,
    eager=False,
    constraint=ParameterConstraint(),
    show_default=True,
    hidden=False,
)
_OPERATION_ID: Final[ArgumentSpec] = ArgumentSpec(
    name="operation_id",
    value=TEXT_VALUE,
    default=_REQUIRED,
    help_key=TranslationKey(f"{_HELP}.operation_id_help"),
    metavar=None,
    constraint=ParameterConstraint(),
    show_default=True,
    hidden=False,
)


def _result_schema(model: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget(_RESULT_MODULE, model, __package__),
        identity=identity,
    )


def _leaf(
    verb: str,
    *,
    parameters: tuple[OptionSpec | ArgumentSpec, ...],
    result_model: str,
    writes: bool = True,
) -> CommandSpec:
    """Declare one leaf; its node, handler, help key and result identity all derive from ``verb``."""
    token = verb.replace("-", "_")
    return CommandSpec(
        f"{_GROUP}_{token}",
        _GROUP,
        verb,
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey(f"{_HELP}.{token}_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=parameters,
        policy=POLICY_4 if writes else POLICY_5,
        handler=LazyBinding.available(DeferredTarget(_CLI_MODULE, f"m232_related_party_{token}", __package__)),
        result_schema=_result_schema(result_model, f"ledger.operaciones_vinculadas.{token}"),
    )


LEDGER_M232_RELATED_PARTY_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        _GROUP,
        "app_ledger",
        "operaciones-vinculadas",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey(f"{_HELP}.group_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=True, context_parameter=None),
        parameters=(),
        policy=POLICY_1,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    _leaf("list", parameters=(_EJERCICIO,), result_model="Modelo232RelatedPartyListResult", writes=False),
    _leaf(
        "state-operation",
        parameters=(
            _EJERCICIO,
            _option("kind", "--kind", value=_enum("Modelo232OperationKind"), default=_REQUIRED),
            _option("counterparty_name", "--counterparty-name", default=_REQUIRED),
            _option("counterparty_country", "--counterparty-country", default=_REQUIRED),
            _option("amount", "--amount", default=_REQUIRED),
            _option("counterparty_tax_id", "--counterparty-tax-id"),
            _option("tipo_vinculacion", "--tipo-vinculacion"),
            _option("tipo_operacion", "--tipo-operacion"),
            _option("metodo_valoracion", "--metodo-valoracion"),
            _option("direction", "--direction", value=_enum("Modelo232Direction")),
            _SPECIFIC,
            _option("exclusion", "--exclusion", value=_enum("Modelo232Exclusion")),
            _option("description", "--description"),
            _option("participation", "--participation"),
            _option("parent_tax_id", "--parent-tax-id"),
            _option("parent_name", "--parent-name"),
            _EXPECTED_GUARD_REVISION,
        ),
        result_model="Modelo232OperationResult",
    ),
    _leaf(
        "withdraw-operation",
        parameters=(_OPERATION_ID, _EJERCICIO, _EXPECTED_REVISION),
        result_model="Modelo232OperationResult",
    ),
    _leaf(
        "state-none",
        parameters=(_EJERCICIO, _option("note", "--note", default=_REQUIRED), _EXPECTED_GUARD_REVISION),
        result_model="Modelo232NoneStatementResult",
    ),
    _leaf("withdraw-none", parameters=(_EJERCICIO, _EXPECTED_REVISION), result_model="Modelo232NoneStatementResult"),
    _leaf(
        "state-turnover",
        parameters=(
            _EJERCICIO,
            _option("cifra_negocios", "--cifra-negocios", default=_REQUIRED),
            _option("source", "--source", value=_enum("Modelo232TurnoverSource"), default=_REQUIRED),
            _option("source_reference", "--source-reference", default=_REQUIRED),
            _EXPECTED_GUARD_REVISION,
        ),
        result_model="Modelo232TurnoverStatementResult",
    ),
    _leaf(
        "withdraw-turnover",
        parameters=(_EJERCICIO, _EXPECTED_REVISION),
        result_model="Modelo232TurnoverStatementResult",
    ),
)

__all__ = ["LEDGER_M232_RELATED_PARTY_COMMAND_SPECS"]
