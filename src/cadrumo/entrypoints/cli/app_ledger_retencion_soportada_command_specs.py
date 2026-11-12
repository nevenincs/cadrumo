"""Declare the command specs for the retencion soportada ledger commands."""

from __future__ import annotations

from typing import Final

from cadrumo_client.commands.parameters import ArgumentSpec, OptionSpec
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

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from .app_ledger_command_spec_policies import (
    POLICY_1,
    POLICY_4,
    POLICY_5,
)

_CLI_MODULE: Final[str] = ".retencion_soportada_commands"
_RESULT_MODULE: Final[str] = ".retencion_soportada_results"

_CLASS_VALUE: Final[ValueContract] = ValueContract(
    DeferredTarget("...core.retencion_soportada", "RetencionSoportadaClase", __package__)
)
_ORIGIN_VALUE: Final[ValueContract] = ValueContract(
    DeferredTarget("...domain.renta.retencion_soportada", "RetencionSoportadaOrigen", __package__)
)
_REQUIRED: Final[ParameterDefault] = ParameterDefault.required()
_OPTIONAL: Final[ParameterDefault] = ParameterDefault.value(None)
_ZERO: Final[ParameterDefault] = ParameterDefault.value("0")
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


def _argument(*, name: str, help_key: str) -> ArgumentSpec:
    """Build one required positional text argument."""
    return ArgumentSpec(
        name=name,
        value=TEXT_VALUE,
        default=_REQUIRED,
        help_key=TranslationKey(help_key),
        metavar=None,
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
_EXPECTED_REVISION_REQUIRED: Final[OptionSpec] = _option(
    name="expected_revision",
    declaration="--expected-revision",
    value=TEXT_VALUE,
    default=_REQUIRED,
    help_key="cli.app.ledger.retencion_soportada.remove_expected_revision_help",
)


def _result_schema(model: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget(_RESULT_MODULE, model, __package__),
        identity=identity,
    )


LEDGER_RETENCION_SOPORTADA_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_ledger_retencion_soportada",
        "app_ledger",
        "retencion-soportada",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.app.ledger.retencion_soportada.group_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=True, context_parameter=None),
        parameters=(),
        policy=POLICY_1,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "app_ledger_retencion_soportada_record",
        "app_ledger_retencion_soportada",
        "record",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.retencion_soportada.record_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _argument(name="payer_tax_id", help_key="cli.app.ledger.retencion_soportada.payer_tax_id_help"),
            _EJERCICIO_OPTION,
            _INCOME_CLASS_OPTION,
            _option(
                name="origin",
                declaration="--origin",
                value=_ORIGIN_VALUE,
                default=_REQUIRED,
                help_key="cli.app.ledger.retencion_soportada.origin_help",
            ),
            _option(
                name="retencion",
                declaration="--retencion",
                value=TEXT_VALUE,
                default=_ZERO,
                help_key="cli.app.ledger.retencion_soportada.retencion_help",
            ),
            _option(
                name="ingreso_a_cuenta",
                declaration="--ingreso-a-cuenta",
                value=TEXT_VALUE,
                default=_ZERO,
                help_key="cli.app.ledger.retencion_soportada.ingreso_a_cuenta_help",
            ),
            _option(
                name="ingreso_a_cuenta_repercutido",
                declaration="--ingreso-a-cuenta-repercutido",
                value=TEXT_VALUE,
                default=_ZERO,
                help_key="cli.app.ledger.retencion_soportada.ingreso_a_cuenta_repercutido_help",
            ),
            _option(
                name="importe_integro_dinerario",
                declaration="--importe-integro",
                value=TEXT_VALUE,
                default=_ZERO,
                help_key="cli.app.ledger.retencion_soportada.importe_integro_help",
            ),
            _option(
                name="valoracion_especie",
                declaration="--valoracion-especie",
                value=TEXT_VALUE,
                default=_ZERO,
                help_key="cli.app.ledger.retencion_soportada.valoracion_especie_help",
            ),
            _option(
                name="reducciones_aplicables",
                declaration="--reducciones-aplicables",
                value=TEXT_VALUE,
                default=_OPTIONAL,
                help_key="cli.app.ledger.retencion_soportada.reducciones_aplicables_help",
            ),
            _option(
                name="gastos_deducibles",
                declaration="--gastos-deducibles",
                value=TEXT_VALUE,
                default=_OPTIONAL,
                help_key="cli.app.ledger.retencion_soportada.gastos_deducibles_help",
            ),
            _option(
                name="payer_name",
                declaration="--payer-name",
                value=TEXT_VALUE,
                default=_OPTIONAL,
                help_key="cli.app.ledger.retencion_soportada.payer_name_help",
            ),
            OptionSpec(
                name="certificate_file",
                declarations=("--certificate-file",),
                value=ValueContract(DeferredTarget("pathlib", "Path")),
                default=_OPTIONAL,
                help_key=TranslationKey("cli.app.ledger.retencion_soportada.certificate_file_help"),
                metavar=None,
                is_flag=False,
                flag_value=None,
                multiple=False,
                count=False,
                eager=False,
                # Checked where it is parsed, so a mistyped path names itself instead of reaching the worker.
                constraint=ParameterConstraint(exists=True, dir_okay=False),
                show_default=True,
                hidden=False,
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.AUXILIARY,
            ),
            _option(
                name="evidence_sha256",
                declaration="--evidence-sha256",
                value=TEXT_VALUE,
                default=_OPTIONAL,
                help_key="cli.app.ledger.retencion_soportada.evidence_sha256_help",
            ),
            _option(
                name="expected_revision",
                declaration="--expected-revision",
                value=TEXT_VALUE,
                default=_OPTIONAL,
                help_key="cli.app.ledger.retencion_soportada.record_expected_revision_help",
            ),
        ),
        policy=POLICY_4,
        handler=LazyBinding.available(DeferredTarget(_CLI_MODULE, "retencion_soportada_record", __package__)),
        result_schema=_result_schema("RetencionSoportadaRecordResult", "ledger.retencion_soportada.record"),
    ),
    CommandSpec(
        "app_ledger_retencion_soportada_list",
        "app_ledger_retencion_soportada",
        "list",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.retencion_soportada.list_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(_EJERCICIO_OPTION,),
        policy=POLICY_5,
        handler=LazyBinding.available(DeferredTarget(_CLI_MODULE, "retencion_soportada_list", __package__)),
        result_schema=_result_schema("RetencionSoportadaListResult", "ledger.retencion_soportada.list"),
    ),
    CommandSpec(
        "app_ledger_retencion_soportada_remove",
        "app_ledger_retencion_soportada",
        "remove",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.retencion_soportada.remove_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _argument(name="payer_ref", help_key="cli.app.ledger.retencion_soportada.payer_ref_help"),
            _EJERCICIO_OPTION,
            _INCOME_CLASS_OPTION,
            _EXPECTED_REVISION_REQUIRED,
        ),
        policy=POLICY_4,
        handler=LazyBinding.available(DeferredTarget(_CLI_MODULE, "retencion_soportada_remove", __package__)),
        result_schema=_result_schema("RetencionSoportadaRemoveResult", "ledger.retencion_soportada.remove"),
    ),
)

__all__ = ["LEDGER_RETENCION_SOPORTADA_COMMAND_SPECS"]
