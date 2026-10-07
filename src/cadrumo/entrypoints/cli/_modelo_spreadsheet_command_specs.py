"""Command authority for outbound spreadsheet publication and local XLSX export.

Remote pull, calculate and verify have no enrolled command or compatibility alias.
"""

from __future__ import annotations

from cadrumo.application.operator_surface.command_ports import (
    CommandNodeKind,
    CommandWriteRoute,
)

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from .command_parameter_contracts import OptionSpec
from .command_shared_contracts import (
    FLAG_VALUE,
    PATH_VALUE,
    TEXT_VALUE,
    WHOLE_NUMBER_VALUE,
    DeferredTarget,
    LazyBinding,
    LiteralValue,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from .command_spec import CommandSpec, ExecutionPolicySpec, InvocationSpec

_METADATA = ExecutionPolicySpec(frozenset({"state-free"}), frozenset({"none"}), "metadata", CommandWriteRoute.NONE)
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

_OFFLINE_WORKBOOK_EXPORT = ExecutionPolicySpec(
    frozenset({"calculation", "encrypted-facts", "profile-custody"}),
    frozenset({"local-state"}),
    "local-io",
    CommandWriteRoute.PROFILE_BOUND,
)

_MODULE = ".modelo_spreadsheet_cli"
_PAYLOADS = "._modelo_spreadsheet_payloads"


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
        handler=LazyBinding.available(DeferredTarget(_MODULE, handler, __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(_PAYLOADS, schema_name, __package__),
            identity=identity,
        ),
    )


_MODELO = _option("modelo", ("--modelo",), TEXT_VALUE, "cli.app.modelo.spreadsheet.modelo_help", required=True)
_PERIOD = _option("period", ("--period",), TEXT_VALUE, "cli.app.modelo.spreadsheet.period_help", required=True)
_YEAR = _option("year", ("--year",), WHOLE_NUMBER_VALUE, "cli.app.modelo.spreadsheet.year_help", required=True)
_SPREADSHEET_ID = _option(
    "spreadsheet_id",
    ("--spreadsheet-id",),
    TEXT_VALUE,
    "cli.app.modelo.spreadsheet.spreadsheet_id_help",
    required=True,
    transport_locus=TransportLocus.REMOTE_HANDLE,
)

MODELO_SPREADSHEET_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_modelo_spreadsheet",
        "app_modelo",
        "spreadsheet",
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
                FLAG_VALUE,
                "cli.app.modelo.spreadsheet.push.prefill_relations_help",
                default=False,
                flag=True,
            ),
            _option(
                "dry_run",
                ("--dry-run",),
                FLAG_VALUE,
                "cli.app.modelo.spreadsheet.push.dry_run_help",
                default=False,
                flag=True,
            ),
        ),
    ),
    _leaf(
        "app_modelo_spreadsheet_export",
        "export",
        "cli.app.modelo.spreadsheet.export_help",
        "modelo_spreadsheet_export",
        "ModeloSpreadsheetExportResult",
        _OFFLINE_WORKBOOK_EXPORT,
        "modelo.spreadsheet.export",
        (
            _MODELO,
            _PERIOD,
            _YEAR,
            _option(
                "output",
                ("--output",),
                PATH_VALUE,
                "cli.app.modelo.spreadsheet.export.output_help",
                required=True,
                transport_locus=TransportLocus.LOCAL_OUT,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            _option(
                "replace_existing",
                ("--replace",),
                FLAG_VALUE,
                "cli.app.modelo.export.replace_help",
                default=False,
                flag=True,
            ),
            _option(
                "prefill_relations",
                ("--prefill-relations/--no-prefill-relations",),
                FLAG_VALUE,
                "cli.app.modelo.spreadsheet.push.prefill_relations_help",
                default=False,
                flag=True,
            ),
        ),
    ),
    CommandSpec(
        "app_modelo_spreadsheet_review",
        "app_modelo_spreadsheet",
        "review",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.spreadsheet.review_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _option(
                "calculation_revision_id",
                ("--calculation-revision-id",),
                TEXT_VALUE,
                "cli.app.modelo.spreadsheet.publish.calculation_revision_id_help",
                required=True,
            ),
            _option(
                "output",
                ("--output",),
                PATH_VALUE,
                "cli.app.modelo.spreadsheet.export.output_help",
                required=True,
                transport_locus=TransportLocus.LOCAL_OUT,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            _option(
                "replace_existing",
                ("--replace",),
                FLAG_VALUE,
                "cli.app.modelo.export.replace_help",
                default=False,
                flag=True,
            ),
        ),
        policy=_OFFLINE_WORKBOOK_EXPORT,
        handler=LazyBinding.available(
            DeferredTarget(".calculation_review_cli", "export_calculation_review_cli", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".calculation_review_cli", "CalculationReviewWorkbookResult", __package__),
            identity="modelo.spreadsheet.review",
        ),
    ),
    CommandSpec(
        "app_modelo_spreadsheet_publish",
        "app_modelo_spreadsheet",
        "publish",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.spreadsheet.publish_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _option(
                "calculation_revision_id",
                ("--calculation-revision-id",),
                TEXT_VALUE,
                "cli.app.modelo.spreadsheet.publish.calculation_revision_id_help",
                required=True,
            ),
            _option(
                "filing_record_id",
                ("--filing-record-id",),
                TEXT_VALUE,
                "cli.app.modelo.spreadsheet.publish.filing_record_id_help",
            ),
            _option(
                "publication_id",
                ("--publication-id",),
                TEXT_VALUE,
                "cli.app.modelo.spreadsheet.publish.publication_id_help",
            ),
            _option(
                "accept_readable_export",
                ("--accept-readable-export",),
                FLAG_VALUE,
                "cli.app.modelo.spreadsheet.publish.accept_readable_export_help",
                default=False,
                flag=True,
            ),
        ),
        policy=_GOOGLE_CALCULATION_HANDOFF,
        handler=LazyBinding.available(DeferredTarget(".google_review_cli", "publish_google_review_cli", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".google_review_cli", "GoogleReviewPublicationResult", __package__),
            identity="modelo.spreadsheet.publish",
        ),
    ),
)

__all__ = ["MODELO_SPREADSHEET_COMMAND_SPECS"]
