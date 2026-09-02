"""Import-light command authority for the modelo spreadsheet transport family.

The subject is ``spreadsheet`` rather than ``workbook`` because ``app modelo
work`` already exists: ``work`` and ``workbook`` differ by four characters under
one parent, and ``work verify`` beside ``workbook verify`` is a collision an
operator reads as a typo. The subject is also transport-neutral, so an offline
workbook transport lands here as ``export``/``import`` without new vocabulary.

``push`` and ``pull`` are the remote counterparty pair. ``calculate`` and
``verify`` are computation verbs that happen to read the remote workbook as a
means; the verb names what the operator asked for, and the transport it performs
on the way is declared on its parameters rather than in its name.
"""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from .command_spec import (
    CommandNodeKind,
    CommandSpec,
    CommandWriteRoute,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    LiteralValue,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

_METADATA = ExecutionPolicySpec(frozenset({"state-free"}), frozenset({"none"}), "metadata", CommandWriteRoute.NONE)
_GOOGLE_CALCULATION_READ = ExecutionPolicySpec(
    frozenset({"calculation", "encrypted-facts", "google"}),
    frozenset({"google"}),
    "external-io",
    CommandWriteRoute.NONE,
)
_GOOGLE_CALCULATION_WRITE = ExecutionPolicySpec(
    frozenset({"calculation", "encrypted-facts", "google", "profile-custody"}),
    frozenset({"google", "local-state"}),
    "external-io",
    CommandWriteRoute.PROFILE_BOUND,
)
_GOOGLE_CALCULATION_HANDOFF = ExecutionPolicySpec(
    frozenset({"calculation", "encrypted-facts", "filing", "google", "profile-custody"}),
    frozenset({"google", "local-state"}),
    "external-io",
    CommandWriteRoute.PROFILE_BOUND,
    handoff=True,
)

_STR = ValueContract(DeferredTarget("builtins", "str"))
_INT = ValueContract(DeferredTarget("builtins", "int"))
_BOOL = ValueContract(DeferredTarget("builtins", "bool"))
_PATH = ValueContract(DeferredTarget("pathlib", "Path"))

_MODULE = "cadrumo.entrypoints.cli._modelo_spreadsheet_cli"
_PAYLOADS = "cadrumo.entrypoints.cli._modelo_spreadsheet_payloads"


def _option(
    name: str,
    declarations: tuple[str, ...],
    value: ValueContract,
    help_key: str,
    *,
    required: bool = False,
    default: LiteralValue | tuple[LiteralValue, ...] = None,
    flag: bool = False,
    transport_locus: TransportLocus = TransportLocus.NONE,
    transport_shape: TransportShape = TransportShape.NOT_APPLICABLE,
    transport_role: TransportRole = TransportRole.NOT_APPLICABLE,
) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=value,
        default=ParameterDefault.required() if required else ParameterDefault.value(default),
        help_key=TranslationKey(help_key),
        is_flag=flag,
        flag_value=True if flag else None,
        transport_locus=transport_locus,
        transport_shape=transport_shape,
        transport_role=transport_role,
    )


def _leaf(
    key: str,
    token: str,
    help_key: str,
    handler: str,
    schema_name: str,
    policy: ExecutionPolicySpec,
    identity: str,
    parameters: tuple[OptionSpec, ...],
) -> CommandSpec:
    return CommandSpec(
        key=key,
        parent_key="app_modelo_spreadsheet",
        token=token,
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey(help_key),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=parameters,
        policy=policy,
        handler=LazyBinding.available(DeferredTarget(_MODULE, handler)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(_PAYLOADS, schema_name),
            identity=identity,
        ),
    )


_MODELO = _option("modelo", ("--modelo",), _STR, "cli.app.modelo.spreadsheet.modelo_help", required=True)
_PERIOD = _option("period", ("--period",), _STR, "cli.app.modelo.spreadsheet.period_help", required=True)
_YEAR = _option("year", ("--year",), _INT, "cli.app.modelo.spreadsheet.year_help", required=True)
_SPREADSHEET_ID = _option(
    "spreadsheet_id",
    ("--spreadsheet-id",),
    _STR,
    "cli.app.modelo.spreadsheet.spreadsheet_id_help",
    required=True,
    transport_locus=TransportLocus.REMOTE_HANDLE,
)

MODELO_SPREADSHEET_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_modelo_spreadsheet",
        parent_key="app_modelo",
        token="spreadsheet",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.app.modelo.spreadsheet.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=_METADATA,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    _leaf(
        "app_modelo_spreadsheet_push",
        "push",
        "cli.app.modelo.spreadsheet.push_help",
        "modelo_spreadsheet_push",
        "ModeloSpreadsheetPushResult",
        _GOOGLE_CALCULATION_HANDOFF,
        "modelo.spreadsheet.push",
        (
            _MODELO,
            _PERIOD,
            _YEAR,
            _option(
                "prefill_relations",
                ("--prefill-relations/--no-prefill-relations",),
                _BOOL,
                "cli.app.modelo.spreadsheet.push.prefill_relations_help",
                default=False,
                flag=True,
            ),
            _option(
                "dry_run",
                ("--dry-run",),
                _BOOL,
                "cli.app.modelo.spreadsheet.push.dry_run_help",
                default=False,
                flag=True,
            ),
        ),
    ),
    _leaf(
        "app_modelo_spreadsheet_pull",
        "pull",
        "cli.app.modelo.spreadsheet.pull_help",
        "modelo_spreadsheet_pull",
        "ModeloSpreadsheetPullResult",
        _GOOGLE_CALCULATION_WRITE,
        "modelo.spreadsheet.pull",
        (
            _MODELO,
            _PERIOD,
            _YEAR,
            _SPREADSHEET_ID,
            _option(
                "assemble_observations",
                ("--assemble-observations/--no-assemble-observations",),
                _BOOL,
                "cli.app.modelo.spreadsheet.pull.assemble_observations_help",
                default=False,
                flag=True,
            ),
        ),
    ),
    _leaf(
        "app_modelo_spreadsheet_calculate",
        "calculate",
        "cli.app.modelo.spreadsheet.calculate_help",
        "modelo_spreadsheet_calculate",
        "ModeloSpreadsheetCalculateResult",
        _GOOGLE_CALCULATION_WRITE,
        "modelo.spreadsheet.calculate",
        (_MODELO, _PERIOD, _YEAR, _SPREADSHEET_ID),
    ),
    _leaf(
        "app_modelo_spreadsheet_verify",
        "verify",
        "cli.app.modelo.spreadsheet.verify_help",
        "modelo_spreadsheet_verify",
        "ModeloSpreadsheetVerifyResult",
        _GOOGLE_CALCULATION_READ,
        "modelo.spreadsheet.verify",
        (
            _MODELO,
            _PERIOD,
            _YEAR,
            _option(
                "scenario_path",
                ("--scenario",),
                _PATH,
                "cli.app.modelo.spreadsheet.verify.scenario_help",
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.AUXILIARY,
            ),
        ),
    ),
)

__all__ = ["MODELO_SPREADSHEET_COMMAND_SPECS"]
