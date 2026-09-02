"""Import-light command authority for the Modelo work subtree."""

from __future__ import annotations

from typing import Final

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from .command_spec import (
    ArgumentSpec,
    Capability,
    CommandSpec,
    CommandWriteRoute,
    CommandWriteRouteValue,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    LiteralValue,
    OptionSpec,
    ParameterDefault,
    PerformanceClass,
    ResultSchemaSpec,
    SchemaState,
    SideEffect,
    TuiCapability,
    ValueContract,
)
from .command_spec import translation_key as _key

_STR = ValueContract(DeferredTarget("builtins", "str"))
_INT = ValueContract(DeferredTarget("builtins", "int"))
_BOOL = ValueContract(DeferredTarget("builtins", "bool"))
_PATH = ValueContract(DeferredTarget("pathlib", "Path"))
_LANGUAGE = ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage"))
_MODELO = ValueContract(
    DeferredTarget("builtins", "str"),
    click_type=DeferredTarget("cadrumo.entrypoints.cli._common", "MODELO_CODE_CHOICE"),
)
_MODELO_OPEN = ValueContract(DeferredTarget("builtins", "str"))
_M210_SOURCE = ValueContract(DeferredTarget("cadrumo.core.irnr", "M210GrossIncomeSourceMode"))
_RESCATE_TYPE = ValueContract(DeferredTarget("cadrumo.core.rescate_type", "RescateType"))
_VERIFY_SELECTOR = ValueContract(DeferredTarget("cadrumo.application.modelo.verify_selector", "ModeloVerifySelector"))
_REFUND = ValueContract(DeferredTarget("cadrumo.core.refund_election", "RefundElection"))
_PAYMENT = ValueContract(DeferredTarget("cadrumo.core.payment_election", "PaymentElection"))
_DOMICILIATION = ValueContract(
    DeferredTarget("cadrumo.core.prior_domiciliation_election", "PriorDomiciliationElection")
)


def _policy(
    capabilities: frozenset[Capability],
    side_effects: frozenset[SideEffect],
    performance: PerformanceClass,
    write_route: CommandWriteRouteValue,
    *,
    destructive: bool = False,
    handoff: bool = False,
) -> ExecutionPolicySpec:
    return ExecutionPolicySpec(
        capabilities,
        side_effects,
        performance,
        write_route,
        destructive=destructive,
        handoff=handoff,
    )


_CALC_WRITE = _policy(
    frozenset({"calculation", "encrypted-facts"}),
    frozenset({"local-state"}),
    "compute",
    CommandWriteRoute.PROFILE_BOUND,
)
_MODEL_WRITE = _policy(
    frozenset({"encrypted-facts"}), frozenset({"local-state"}), "local-io", CommandWriteRoute.PROFILE_BOUND
)
_MODEL_READ = _policy(frozenset({"encrypted-facts"}), frozenset({"none"}), "local-io", CommandWriteRoute.NONE)
_CALC_READ = _policy(
    frozenset({"calculation", "encrypted-facts"}), frozenset({"none"}), "compute", CommandWriteRoute.NONE
)
_CREATE = _policy(
    frozenset({"encrypted-facts", "registry"}), frozenset({"local-state"}), "local-io", CommandWriteRoute.PROFILE_BOUND
)
_FILE = _policy(
    frozenset({"encrypted-facts", "filing"}),
    frozenset({"local-state"}),
    "compute",
    CommandWriteRoute.PROFILE_BOUND,
    handoff=True,
)
_WIZARD = _policy(
    frozenset({"calculation", "encrypted-facts"}),
    frozenset({"local-state"}),
    "interactive",
    CommandWriteRoute.PROFILE_BOUND,
)


def _o(
    name: str,
    declaration: str,
    value: ValueContract = _STR,
    *,
    help_name: str | None = None,
    default: LiteralValue | tuple[LiteralValue, ...] = None,
    multiple: bool = False,
    flag: bool = False,
    required: bool = False,
    transport_locus: TransportLocus = TransportLocus.NONE,
    transport_shape: TransportShape = TransportShape.NOT_APPLICABLE,
    transport_role: TransportRole = TransportRole.NOT_APPLICABLE,
) -> OptionSpec:
    literal_default = False if flag and default is None else (() if multiple else default)
    return OptionSpec(
        name,
        (declaration,),
        value,
        ParameterDefault.required() if required else ParameterDefault.value(literal_default),
        _key(f"cli.app.modelo.work.{help_name or name}_help"),
        multiple=multiple,
        is_flag=flag,
        flag_value=True if flag else None,
        transport_locus=transport_locus,
        transport_shape=transport_shape,
        transport_role=transport_role,
    )


def _a(name: str, *, help_name: str | None = None, required: bool = False) -> ArgumentSpec:
    return ArgumentSpec(
        name,
        _STR,
        ParameterDefault.required() if required else ParameterDefault.value(None),
        _key(f"cli.app.modelo.work.{help_name or name}_help"),
    )


_ADDRESS: Final = (
    _o("modelo", "--modelo", _MODELO),
    _o("year", "--year", _INT),
    _o("period", "--period"),
    _o("revision", "--revision"),
    _o("bucket_id", "--bucket-id"),
)
_LANG = OptionSpec(
    "output_language",
    ("--output-language", "--language"),
    _LANGUAGE,
    ParameterDefault.value(None),
    _key("cli.config.auth.output_language_help"),
)


def _leaf(
    token: str,
    module: str,
    parameters: tuple[ArgumentSpec | OptionSpec, ...],
    policy: ExecutionPolicySpec,
    schema_module: str,
    schema_name: str,
    *,
    handler_name: str | None = None,
    tui_capability: TuiCapability = TuiCapability.NOT_IMPLEMENTED,
) -> CommandSpec:
    name = token.replace("-", "_")
    return CommandSpec(
        f"app_modelo_work_{name}",
        "app_modelo_work",
        token,
        "leaf",
        _key(f"cli.app.modelo.work.{name}_help"),
        None,
        InvocationSpec(context_parameter="ctx"),
        parameters,
        policy,
        LazyBinding.available(DeferredTarget(module, handler_name or f"work_{name}")),
        ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(schema_module, schema_name),
            identity=f"modelo.work.{name}",
        ),
        tui_capability=tui_capability,
    )


_CALCULATE_PARAMETERS = (
    _a("work_unit_id"),
    *_ADDRESS,
    _o("casilla", "--casilla", multiple=True),
    _o("binding", "--binding", help_name="override", multiple=True),
    _o("borrador_snapshot_id", "--borrador", help_name="borrador"),
    _o("m210_gross_income_source", "--m210-gross-income-source", _M210_SOURCE, default="manual"),
    _o("actor", "--by"),
    _o("relation", "--relation", multiple=True),
    _o("row", "--row", multiple=True),
    _o("prestacion_inss_exenta", "--prestacion-inss-exenta"),
    _o("rescate_plan_pensiones_capital", "--rescate-plan-pensiones-capital"),
    _o("rescate_plan_pensiones_aportaciones_pre_2007", "--rescate-plan-pensiones-aportaciones-pre-2007"),
    _o("rescate_plan_pensiones_aportaciones_totales", "--rescate-plan-pensiones-aportaciones-totales"),
    _o("rescate_type", "--rescate-type", _RESCATE_TYPE),
    _o("contingencia_year", "--contingencia-year", _INT, help_name="rescate_contingencia_year"),
    _o("rescate_year", "--rescate-year", _INT),
    _o("sal_beneficio_neto", "--sal-beneficio-neto"),
    _o("sal_reserva_dotada", "--sal-reserva-dotada"),
    _o("sal_capital_social", "--sal-capital-social"),
    _o("autoconsumo_promotor_base", "--autoconsumo-promotor-base"),
    _o(
        "m303_filing_evidence",
        "--m303-filing-evidence",
        _PATH,
        transport_locus=TransportLocus.LOCAL_IN,
        transport_shape=TransportShape.FILE,
        transport_role=TransportRole.AUXILIARY,
    ),
    _LANG,
)

_REVISION_ADDRESS = (
    _o("modelo", "--modelo", _MODELO),
    _o("year", "--year", _INT),
    _o("period", "--period"),
    _o("registry_revision", "--registry-revision", help_name="revision"),
    _o("work_unit_id", "--work-unit-id"),
    _o("select", "--select", default="current", help_name="revision_selector"),
    _o("bucket_id", "--bucket-id"),
)

MODELO_WORK_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    _leaf(
        "calculate",
        "cadrumo.entrypoints.cli._modelo_work_calculate_cli",
        _CALCULATE_PARAMETERS,
        _CALC_WRITE,
        "cadrumo.entrypoints.cli._modelo_payloads",
        "WorkCalculateResult",
    ),
    _leaf(
        "create",
        "cadrumo.entrypoints.cli._modelo_work_lifecycle_cli",
        (
            _o("modelo", "--modelo", _MODELO_OPEN, required=True),
            _o("year", "--year", _INT, required=True),
            _o("period", "--period", required=True),
            *_ADDRESS[3:],
            _o("name", "--name"),
            _o("actor", "--by"),
            _o("allow_not_applicable", "--allow-not-applicable", _BOOL, flag=True),
            _o("quiet", "--quiet", _BOOL, help_name="create_quiet", flag=True),
            _o("causante_ccaa_raw", "--causante-ccaa", help_name="causante_ccaa"),
            _LANG,
        ),
        _CREATE,
        "cadrumo.entrypoints.cli._modelo_payloads",
        "WorkCreateResult",
    ),
    _leaf(
        "dependencies",
        "cadrumo.entrypoints.cli._modelo_work_verification_cli",
        (_o("year", "--year", _INT, required=True), _o("modelo", "--modelo", _MODELO), _o("period", "--period"), _LANG),
        _CALC_READ,
        "cadrumo.entrypoints.cli._modelo_payloads",
        "WorkDependenciesResult",
    ),
    _leaf(
        "discard",
        "cadrumo.entrypoints.cli._modelo_work_lifecycle_cli",
        (
            _a("work_unit_id"),
            *_ADDRESS,
            _o("actor", "--by"),
            _o("reason", "--reason"),
            _o("confirmed", "--yes", _BOOL, help_name="discard_yes", flag=True),
        ),
        _policy(
            frozenset({"encrypted-facts"}),
            frozenset({"local-state"}),
            "local-io",
            CommandWriteRoute.PROFILE_BOUND,
            destructive=True,
        ),
        "cadrumo.entrypoints.cli._modelo_payloads",
        "WorkDiscardResult",
    ),
    _leaf(
        "list",
        "cadrumo.entrypoints.cli._modelo_work_lifecycle_cli",
        (_o("bucket_id", "--bucket-id"), _o("include_discarded", "--include-discarded", _BOOL, flag=True), _LANG),
        _MODEL_READ,
        "cadrumo.entrypoints.cli._modelo_payloads",
        "WorkListResult",
    ),
    _leaf(
        "select",
        "cadrumo.entrypoints.cli._modelo_work_select_cli",
        (_o("bucket_id", "--bucket-id"), _o("include_discarded", "--include-discarded", _BOOL, flag=True), _LANG),
        _MODEL_READ,
        "cadrumo.entrypoints.cli._modelo_payloads",
        "WorkSelectResult",
        tui_capability=TuiCapability.AVAILABLE,
    ),
    _leaf(
        "rename",
        "cadrumo.entrypoints.cli._modelo_work_lifecycle_cli",
        (_a("work_unit_id"), *_ADDRESS, _o("name", "--name"), _o("actor", "--by")),
        _MODEL_WRITE,
        "cadrumo.entrypoints.cli._modelo_payloads",
        "WorkRenameResult",
    ),
    _leaf(
        "status",
        "cadrumo.entrypoints.cli._modelo_work_lifecycle_cli",
        (_a("work_unit_id"), *_ADDRESS, _LANG),
        _MODEL_READ,
        "cadrumo.entrypoints.cli._modelo_payloads",
        "WorkStatusResult",
    ),
    _leaf(
        "review",
        "cadrumo.entrypoints.cli._modelo_work_review_cli",
        (_a("work_unit_id"), *_ADDRESS, _LANG),
        _MODEL_READ,
        "cadrumo.entrypoints.cli._modelo_payloads",
        "WorkReviewResult",
        tui_capability=TuiCapability.AVAILABLE,
    ),
    _leaf(
        "revisions",
        "cadrumo.entrypoints.cli._modelo_work_revision_cli",
        (_a("work_unit_id"), *_ADDRESS, _LANG),
        _MODEL_READ,
        "cadrumo.entrypoints.cli._modelo_payloads",
        "WorkRevisionsResult",
    ),
    _leaf(
        "revision",
        "cadrumo.entrypoints.cli._modelo_work_revision_cli",
        (
            _a("calculation_revision_id"),
            *_REVISION_ADDRESS,
            _o("verbose", "--verbose", _BOOL, help_name="revision_verbose", flag=True),
            _LANG,
        ),
        _MODEL_READ,
        "cadrumo.entrypoints.cli._modelo_work_revision_payloads",
        "WorkRevisionResult",
    ),
    _leaf(
        "observations",
        "cadrumo.entrypoints.cli._modelo_work_revision_cli",
        (_a("calculation_revision_id"), *_REVISION_ADDRESS, _LANG),
        _MODEL_READ,
        "cadrumo.entrypoints.cli._modelo_work_revision_payloads",
        "WorkObservationsResult",
    ),
    _leaf(
        "run",
        "cadrumo.entrypoints.cli._modelo_work_runs_cli",
        (_a("run_id", required=True), _LANG),
        _MODEL_READ,
        "cadrumo.entrypoints.cli.modelo_aux_payloads",
        "WorkRunResult",
    ),
    _leaf(
        "run-details",
        "cadrumo.entrypoints.cli._modelo_work_runs_cli",
        (_a("run_id", required=True), _LANG),
        _MODEL_READ,
        "cadrumo.entrypoints.cli.modelo_aux_payloads",
        "WorkRunDetailsResult",
    ),
    _leaf(
        "runs",
        "cadrumo.entrypoints.cli._modelo_work_runs_cli",
        (_LANG,),
        _MODEL_READ,
        "cadrumo.entrypoints.cli.modelo_aux_payloads",
        "WorkRunsResult",
    ),
    _leaf(
        "resume",
        "cadrumo.entrypoints.cli._modelo_work_runs_cli",
        (
            _a("target", help_name="resume_target"),
            *_ADDRESS[:4],
            _o("select", "--select", help_name="revision_selector"),
            _o("work_unit_id", "--work-unit-id"),
            _o("calculation_revision_id", "--calculation-revision-id"),
            _o("bucket_id", "--bucket-id"),
            _LANG,
        ),
        _MODEL_READ,
        "cadrumo.entrypoints.cli._modelo_payloads",
        "WorkResumeResult",
    ),
    _leaf(
        "verify",
        "cadrumo.entrypoints.cli._modelo_work_verification_cli",
        (
            _a("calculation_revision_id"),
            *_ADDRESS[:4],
            _o("work_unit_id", "--work-unit-id"),
            _o("select", "--select", _VERIFY_SELECTOR, default="current", help_name="verify_selector"),
            _o("bucket_id", "--bucket-id"),
            _o("actor", "--by"),
            _LANG,
        ),
        _CALC_WRITE,
        "cadrumo.entrypoints.cli._modelo_payloads",
        "WorkVerifyResult",
    ),
    _leaf(
        "file",
        "cadrumo.entrypoints.cli._modelo_work_verification_cli",
        (
            _a("calculation_revision_id"),
            *_ADDRESS[:4],
            _o("work_unit_id", "--work-unit-id"),
            _o("select", "--select", default="current", help_name="revision_selector"),
            _o("bucket_id", "--bucket-id"),
            _o("actor", "--by"),
            _o("notes", "--notes"),
            _o("refund_election", "--refund-election", _REFUND, default="compensar"),
            _o("payment_election", "--payment-election", _PAYMENT, default="ingreso"),
            _o("prior_domiciliation_election", "--prior-domiciliation-election", _DOMICILIATION, default="keep"),
            _LANG,
        ),
        _FILE,
        "cadrumo.entrypoints.cli._modelo_payloads",
        "WorkFileResult",
    ),
    _leaf(
        "wizard",
        "cadrumo.entrypoints.cli._modelo_work_wizard_cli",
        (
            _a("work_unit_id"),
            *_ADDRESS,
            _o("actor", "--by"),
            _o("output_language_opt", "--output-language", _LANGUAGE, help_name="output_language"),
        ),
        _WIZARD,
        "cadrumo.entrypoints.cli._modelo_work_wizard_payloads",
        "WorkWizardResult",
        tui_capability=TuiCapability.NOT_IMPLEMENTED,
    ),
)

__all__ = ["MODELO_WORK_COMMAND_SPECS"]
