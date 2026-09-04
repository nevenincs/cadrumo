"""Authored CommandSpec declarations for the ledger prorrata surface."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from typing import Final

from ._app_ledger_command_spec_policies import (
    _POLICY_4,
    _POLICY_5,
)
from .command_spec import (
    TEXT_VALUE,
    WHOLE_NUMBER_VALUE,
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

_PRORRATA_REGISTER_MODULE: Final[str] = "cadrumo.core.prorrata_register"
_PRORRATA_CLI_MODULE: Final[str] = "cadrumo.entrypoints.cli._prorrata_register_cli"
_PRORRATA_PAYLOAD_MODULE: Final[str] = "cadrumo.entrypoints.cli._prorrata_register_payloads"

_PROVENANCE_VALUE: Final[ValueContract] = ValueContract(
    DeferredTarget(_PRORRATA_REGISTER_MODULE, "ProrrataProvisionalProvenance")
)
_SECTOR_LETTER_VALUE: Final[ValueContract] = ValueContract(
    DeferredTarget(_PRORRATA_REGISTER_MODULE, "SectorDiferenciadoLetra")
)

_REQUIRED: Final[ParameterDefault] = ParameterDefault.required()
_OPTIONAL: Final[ParameterDefault] = ParameterDefault.value(None)
_EMPTY_TUPLE: Final[ParameterDefault] = ParameterDefault.value(())
_CARRIED_PRIOR_DEFINITIVA: Final[ParameterDefault] = ParameterDefault.value("carried_prior_definitiva")
_UNCONSTRAINED: Final[ParameterConstraint] = ParameterConstraint()
_LEAF_INVOCATION: Final[InvocationSpec] = InvocationSpec(
    invoke_without_command=False,
    no_args_is_help=False,
    context_parameter="ctx",
)


def _option(
    *,
    name: str,
    declaration: str,
    value: ValueContract,
    default: ParameterDefault,
    help_key: str,
    multiple: bool = False,
) -> OptionSpec:
    """Build the common non-legal shape of one ordinary prorrata option."""
    return OptionSpec(
        name=name,
        declarations=(declaration,),
        value=value,
        default=default,
        help_key=TranslationKey(help_key),
        metavar=None,
        is_flag=False,
        flag_value=None,
        multiple=multiple,
        count=False,
        eager=False,
        constraint=_UNCONSTRAINED,
        show_default=True,
        hidden=False,
    )


def _handler(name: str) -> LazyBinding:
    """Bind one prorrata leaf to its public command handler."""
    return LazyBinding.available(DeferredTarget(_PRORRATA_CLI_MODULE, name))


def _result_schema(model: str, identity: str) -> ResultSchemaSpec:
    """Declare one prorrata leaf's public result payload."""
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget(_PRORRATA_PAYLOAD_MODULE, model),
        identity=identity,
    )


# These contracts are shared only where every public parameter fact is identical.
_EJERCICIO_OPTION: Final[OptionSpec] = _option(
    name="ejercicio",
    declaration="--ejercicio",
    value=WHOLE_NUMBER_VALUE,
    default=_REQUIRED,
    help_key="cli.app.ledger.prorrata.ejercicio_help",
)
_SEED_EJERCICIO_OPTION: Final[OptionSpec] = _option(
    name="ejercicio",
    declaration="--ejercicio",
    value=WHOLE_NUMBER_VALUE,
    default=_REQUIRED,
    help_key="cli.app.ledger.prorrata.seed_ejercicio_help",
)
_SECTOR_ID_OPTION: Final[OptionSpec] = _option(
    name="sector_id",
    declaration="--sector-id",
    value=TEXT_VALUE,
    default=_REQUIRED,
    help_key="cli.app.ledger.prorrata.sector_id_help",
)
_SECTOR_OPTION: Final[OptionSpec] = _option(
    name="sector",
    declaration="--sector",
    value=TEXT_VALUE,
    default=_OPTIONAL,
    help_key="cli.app.ledger.prorrata.sector_help",
)
_PROVENANCE_OPTION: Final[OptionSpec] = _option(
    name="provenance",
    declaration="--provenance",
    value=_PROVENANCE_VALUE,
    default=_CARRIED_PRIOR_DEFINITIVA,
    help_key="cli.app.ledger.prorrata.provenance_help",
)
_REFERENCE_OPTION: Final[OptionSpec] = _option(
    name="reference",
    declaration="--reference",
    value=TEXT_VALUE,
    default=_OPTIONAL,
    help_key="cli.app.ledger.prorrata.reference_help",
)


LEDGER_PRORRATA_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_ledger_prorrata_declare_sector",
        parent_key="app_ledger_prorrata",
        token="declare-sector",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.prorrata.declare_sector_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _SECTOR_ID_OPTION,
            _option(
                name="letra",
                declaration="--letra",
                value=_SECTOR_LETTER_VALUE,
                default=_REQUIRED,
                help_key="cli.app.ledger.prorrata.letra_help",
            ),
            _option(
                name="activity_code",
                declaration="--activity-code",
                value=TEXT_VALUE,
                default=_EMPTY_TUPLE,
                help_key="cli.app.ledger.prorrata.activity_code_help",
                multiple=True,
            ),
        ),
        policy=_POLICY_4,
        handler=_handler("prorrata_declare_sector"),
        result_schema=_result_schema("ProrrataDeclareSectorResult", "ledger.prorrata.declare_sector"),
    ),
    CommandSpec(
        key="app_ledger_prorrata_elect_especial",
        parent_key="app_ledger_prorrata",
        token="elect-especial",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.prorrata.elect_especial_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _EJERCICIO_OPTION,
            _option(
                name="percentage",
                declaration="--percentage",
                value=TEXT_VALUE,
                default=_REQUIRED,
                help_key="cli.app.ledger.prorrata.percentage_help",
            ),
            _option(
                name="evidence_reference",
                declaration="--evidence-reference",
                value=TEXT_VALUE,
                default=_OPTIONAL,
                help_key="cli.app.ledger.prorrata.optional_evidence_reference_help",
            ),
            _PROVENANCE_OPTION,
            _REFERENCE_OPTION,
            _SECTOR_OPTION,
        ),
        policy=_POLICY_4,
        handler=_handler("prorrata_elect_especial"),
        result_schema=_result_schema("ProrrataElectEspecialResult", "ledger.prorrata.elect_especial"),
    ),
    CommandSpec(
        key="app_ledger_prorrata_elect_general",
        parent_key="app_ledger_prorrata",
        token="elect-general",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.prorrata.elect_general_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _EJERCICIO_OPTION,
            _option(
                name="percentage",
                declaration="--percentage",
                value=TEXT_VALUE,
                default=_REQUIRED,
                help_key="cli.app.ledger.prorrata.general_percentage_help",
            ),
            _PROVENANCE_OPTION,
            _REFERENCE_OPTION,
            _SECTOR_OPTION,
        ),
        policy=_POLICY_4,
        handler=_handler("prorrata_elect_general"),
        result_schema=_result_schema("ProrrataElectGeneralResult", "ledger.prorrata.elect_general"),
    ),
    CommandSpec(
        key="app_ledger_prorrata_list",
        parent_key="app_ledger_prorrata",
        token="list",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.prorrata.list_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(),
        policy=_POLICY_5,
        handler=_handler("prorrata_list"),
        result_schema=_result_schema("ProrrataListResult", "ledger.prorrata.list"),
    ),
    CommandSpec(
        key="app_ledger_prorrata_revoke_especial",
        parent_key="app_ledger_prorrata",
        token="revoke-especial",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.prorrata.revoke_especial_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _EJERCICIO_OPTION,
            _option(
                name="evidence_reference",
                declaration="--evidence-reference",
                value=TEXT_VALUE,
                default=_REQUIRED,
                help_key="cli.app.ledger.prorrata.evidence_reference_help",
            ),
            _option(
                name="percentage",
                declaration="--percentage",
                value=TEXT_VALUE,
                default=_REQUIRED,
                help_key="cli.app.ledger.prorrata.general_percentage_help",
            ),
            _PROVENANCE_OPTION,
            _REFERENCE_OPTION,
            _SECTOR_OPTION,
        ),
        policy=_POLICY_4,
        handler=_handler("prorrata_revoke_especial"),
        result_schema=_result_schema("ProrrataRevokeEspecialResult", "ledger.prorrata.revoke_especial"),
    ),
    CommandSpec(
        key="app_ledger_prorrata_seed",
        parent_key="app_ledger_prorrata",
        token="seed",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.prorrata.seed_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(_SEED_EJERCICIO_OPTION, _SECTOR_OPTION),
        policy=_POLICY_4,
        handler=_handler("prorrata_seed"),
        result_schema=_result_schema("ProrrataSeedResult", "ledger.prorrata.seed"),
    ),
    CommandSpec(
        key="app_ledger_prorrata_seed_sector",
        parent_key="app_ledger_prorrata",
        token="seed-sector",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.prorrata.seed_sector_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(_SEED_EJERCICIO_OPTION, _SECTOR_ID_OPTION),
        policy=_POLICY_4,
        handler=_handler("prorrata_seed_sector"),
        result_schema=_result_schema("ProrrataSeedSectorResult", "ledger.prorrata.seed_sector"),
    ),
    CommandSpec(
        key="app_ledger_prorrata_settle_sector",
        parent_key="app_ledger_prorrata",
        token="settle-sector",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.prorrata.settle_sector_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            _SEED_EJERCICIO_OPTION,
            _SECTOR_ID_OPTION,
            _option(
                name="con_derecho_volume",
                declaration="--con-derecho-volume",
                value=TEXT_VALUE,
                default=_REQUIRED,
                help_key="cli.app.ledger.prorrata.con_derecho_volume_help",
            ),
            _option(
                name="sin_derecho_volume",
                declaration="--sin-derecho-volume",
                value=TEXT_VALUE,
                default=_REQUIRED,
                help_key="cli.app.ledger.prorrata.sin_derecho_volume_help",
            ),
        ),
        policy=_POLICY_4,
        handler=_handler("prorrata_settle_sector"),
        result_schema=_result_schema("ProrrataSettleSectorResult", "ledger.prorrata.settle_sector"),
    ),
)

__all__ = ["LEDGER_PRORRATA_COMMAND_SPECS"]
