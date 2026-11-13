"""Declare the command specs for the pension contribution certificate ledger commands."""

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

_CLI_MODULE: Final[str] = ".prevision_social_commands"
_RESULT_MODULE: Final[str] = ".prevision_social_results"

_CLAVE_VALUE: Final[ValueContract] = ValueContract(
    DeferredTarget("...core.prevision_social", "PrevisionSocialClave", __package__)
)
_SUBCLAVE_VALUE: Final[ValueContract] = ValueContract(
    DeferredTarget("...core.prevision_social", "PrevisionSocialSubclave", __package__)
)
_BENEFICIARY_VALUE: Final[ValueContract] = ValueContract(
    DeferredTarget("...core.prevision_social", "PrevisionSocialBeneficiario", __package__)
)
_SAME_PLAN_VALUE: Final[ValueContract] = ValueContract(
    DeferredTarget(".prevision_social_options", "PrevisionSocialSamePlanAnswer", __package__)
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
    help_key="cli.app.ledger.prevision_social.ejercicio_help",
)
_CLAVE_OPTION: Final[OptionSpec] = _option(
    name="clave",
    declaration="--clave",
    value=_CLAVE_VALUE,
    default=_REQUIRED,
    help_key="cli.app.ledger.prevision_social.clave_help",
)
_SUBCLAVE_OPTION: Final[OptionSpec] = _option(
    name="subclave",
    declaration="--subclave",
    value=_SUBCLAVE_VALUE,
    default=_OPTIONAL,
    help_key="cli.app.ledger.prevision_social.subclave_help",
)
_CERTIFICATE_FILE_OPTION: Final[OptionSpec] = OptionSpec(
    name="certificate_file",
    declarations=("--certificate-file",),
    value=ValueContract(DeferredTarget("pathlib", "Path")),
    default=_OPTIONAL,
    help_key=TranslationKey("cli.app.ledger.prevision_social.certificate_file_help"),
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
)


def _result_schema(model: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget(_RESULT_MODULE, model, __package__),
        identity=identity,
    )


def _handler(name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget(_CLI_MODULE, name, __package__))


_RECORD_PARAMETERS: Final[tuple[ArgumentSpec | OptionSpec, ...]] = (
    _argument(name="issuer_tax_id", help_key="cli.app.ledger.prevision_social.issuer_tax_id_help"),
    _EJERCICIO_OPTION,
    _CLAVE_OPTION,
    _option(
        name="amount",
        declaration="--amount",
        value=TEXT_VALUE,
        default=_REQUIRED,
        help_key="cli.app.ledger.prevision_social.amount_help",
    ),
    _SUBCLAVE_OPTION,
    _option(
        name="beneficiary",
        declaration="--beneficiary",
        value=_BENEFICIARY_VALUE,
        default=ParameterDefault.value("taxpayer"),
        help_key="cli.app.ledger.prevision_social.beneficiary_help",
    ),
    _option(
        name="employer_same_plan",
        declaration="--employer-same-plan",
        value=_SAME_PLAN_VALUE,
        default=_OPTIONAL,
        help_key="cli.app.ledger.prevision_social.employer_same_plan_help",
    ),
    _option(
        name="issuer_name",
        declaration="--issuer-name",
        value=TEXT_VALUE,
        default=_OPTIONAL,
        help_key="cli.app.ledger.prevision_social.issuer_name_help",
    ),
    _option(
        name="plan_nif",
        declaration="--plan-nif",
        value=TEXT_VALUE,
        default=_OPTIONAL,
        help_key="cli.app.ledger.prevision_social.plan_nif_help",
    ),
    _option(
        name="plan_name",
        declaration="--plan-name",
        value=TEXT_VALUE,
        default=_OPTIONAL,
        help_key="cli.app.ledger.prevision_social.plan_name_help",
    ),
    _CERTIFICATE_FILE_OPTION,
    _option(
        name="evidence_sha256",
        declaration="--evidence-sha256",
        value=TEXT_VALUE,
        default=_OPTIONAL,
        help_key="cli.app.ledger.prevision_social.evidence_sha256_help",
    ),
    _option(
        name="expected_revision",
        declaration="--expected-revision",
        value=TEXT_VALUE,
        default=_OPTIONAL,
        help_key="cli.app.ledger.prevision_social.record_expected_revision_help",
    ),
)

_REMOVE_PARAMETERS: Final[tuple[ArgumentSpec | OptionSpec, ...]] = (
    _argument(name="issuer_ref", help_key="cli.app.ledger.prevision_social.issuer_ref_help"),
    _EJERCICIO_OPTION,
    _CLAVE_OPTION,
    _option(
        name="expected_revision",
        declaration="--expected-revision",
        value=TEXT_VALUE,
        default=_REQUIRED,
        help_key="cli.app.ledger.prevision_social.remove_expected_revision_help",
    ),
    _SUBCLAVE_OPTION,
    _option(
        name="plan_ref",
        declaration="--plan-ref",
        value=TEXT_VALUE,
        default=_OPTIONAL,
        help_key="cli.app.ledger.prevision_social.plan_ref_help",
    ),
)


LEDGER_PREVISION_SOCIAL_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_ledger_prevision_social",
        "app_ledger",
        "prevision-social",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.app.ledger.prevision_social.group_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=True, context_parameter=None),
        parameters=(),
        policy=POLICY_1,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "app_ledger_prevision_social_record",
        "app_ledger_prevision_social",
        "record",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.prevision_social.record_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=_RECORD_PARAMETERS,
        policy=POLICY_4,
        handler=_handler("prevision_social_record"),
        result_schema=_result_schema("PrevisionSocialRecordResult", "ledger.prevision_social.record"),
    ),
    CommandSpec(
        "app_ledger_prevision_social_list",
        "app_ledger_prevision_social",
        "list",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.prevision_social.list_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(_EJERCICIO_OPTION,),
        policy=POLICY_5,
        handler=_handler("prevision_social_list"),
        result_schema=_result_schema("PrevisionSocialListResult", "ledger.prevision_social.list"),
    ),
    CommandSpec(
        "app_ledger_prevision_social_remove",
        "app_ledger_prevision_social",
        "remove",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.prevision_social.remove_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=_REMOVE_PARAMETERS,
        policy=POLICY_4,
        handler=_handler("prevision_social_remove"),
        result_schema=_result_schema("PrevisionSocialRemoveResult", "ledger.prevision_social.remove"),
    ),
)

__all__ = ["LEDGER_PREVISION_SOCIAL_COMMAND_SPECS"]
