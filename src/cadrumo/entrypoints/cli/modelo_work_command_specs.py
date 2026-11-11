"""Import-light command authority for the Modelo work subtree."""

from __future__ import annotations

from typing import Final

from cadrumo_client.commands.parameters import ArgumentSpec, OptionSpec
from cadrumo_client.commands.shared_contracts import (
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
    translation_key,
)
from cadrumo_client.commands.spec import CommandSpec, ExecutionPolicySpec, InvocationSpec
from cadrumo_client.contracts.command_ports import (
    Capability,
    CommandNodeKind,
    CommandWriteRoute,
    CommandWriteRouteValue,
    PerformanceClass,
    SideEffect,
)

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape

LANGUAGE = ValueContract(DeferredTarget("...core.external_constants", "OutputLanguage", __package__))
_MODELO = ValueContract(
    DeferredTarget("builtins", "str"),
    parser=DeferredTarget(".common", "MODELO_CODE_CHOICE", __package__),
)
_M210_SOURCE = ValueContract(DeferredTarget("...core.irnr", "M210GrossIncomeSourceMode", __package__))
_RESCATE_TYPE = ValueContract(DeferredTarget("...core.rescate_type", "RescateType", __package__))
_VERIFY_SELECTOR = ValueContract(
    DeferredTarget("...application.modelo.verify_selector", "ModeloVerifySelector", __package__)
)
_REFUND = ValueContract(DeferredTarget("...core.refund_election", "RefundElection", __package__))
_PAYMENT = ValueContract(DeferredTarget("...core.payment_election", "PaymentElection", __package__))
_DOMICILIATION = ValueContract(
    DeferredTarget("...core.prior_domiciliation_election", "PriorDomiciliationElection", __package__)
)
_REPORT_DOCUMENT_FORMAT = ValueContract(
    DeferredTarget("...core.calculation_report_format", "CalculationReportDocumentFormat", __package__)
)


def _boolean_choice(name: str, declaration: str, *, help_name: str) -> OptionSpec:
    """Declare a tri-state explicit operator choice with no implicit false default."""
    return OptionSpec(
        name,
        (declaration, f"--no-{declaration.removeprefix('--')}"),
        FLAG_VALUE,
        ParameterDefault.value(None),
        translation_key(f"cli.app.modelo.work.{help_name}_help"),
        is_flag=True,
        flag_value=True,
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
#: Reads the sealed revision and writes one operator-chosen file. Nothing in the
#: profile changes, so the write route stays NONE: the artefact is the operator's
#: from the moment it lands, exactly as the offline workbook export declares it.
_REPORT = _policy(
    frozenset({"calculation", "encrypted-facts"}),
    frozenset({"local-state"}),
    "local-io",
    CommandWriteRoute.NONE,
)
#: Reads a summary file and, unless the check is document-only, rebuilds the
#: report from the store. It writes no file; the profile's signing keypair is
#: minted on first use, exactly as the report verb mints it, which is the one
#: local-state effect it can have.
_REPORT_VERIFY = _policy(
    frozenset({"calculation", "encrypted-facts"}),
    frozenset({"local-state"}),
    "compute",
    CommandWriteRoute.NONE,
)


def o(
    name: str,
    declaration: str,
    value: ValueContract = TEXT_VALUE,
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
    """Build an option spec for a work command with its translated help."""
    literal_default = False if flag and default is None else (() if multiple else default)
    return OptionSpec(
        name,
        (declaration,),
        value,
        ParameterDefault.required() if required else ParameterDefault.value(literal_default),
        translation_key(f"cli.app.modelo.work.{help_name or name}_help"),
        multiple=multiple,
        is_flag=flag,
        flag_value=True if flag else None,
        transport_locus=transport_locus,
        transport_shape=transport_shape,
        transport_role=transport_role,
    )


def a(name: str, *, help_name: str | None = None, required: bool = False) -> ArgumentSpec:
    """Build a text argument spec for a work command."""
    return ArgumentSpec(
        name,
        TEXT_VALUE,
        ParameterDefault.required() if required else ParameterDefault.value(None),
        translation_key(f"cli.app.modelo.work.{help_name or name}_help"),
    )


ADDRESS: Final = (
    o("modelo", "--modelo", _MODELO),
    o("year", "--year", WHOLE_NUMBER_VALUE),
    o("period", "--period"),
    o("revision", "--revision"),
    o("bucket_id", "--bucket-id"),
)
_LANG = OptionSpec(
    "output_language",
    ("--output-language", "--language"),
    LANGUAGE,
    ParameterDefault.value(None),
    translation_key("cli.config.auth.output_language_help"),
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
) -> CommandSpec:
    name = token.replace("-", "_")
    return CommandSpec(
        f"app_modelo_work_{name}",
        "app_modelo_work",
        token,
        CommandNodeKind.LEAF,
        translation_key(f"cli.app.modelo.work.{name}_help"),
        None,
        InvocationSpec(context_parameter="ctx"),
        parameters,
        policy,
        LazyBinding.available(DeferredTarget(module, handler_name or f"work_{name}", __package__)),
        ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(schema_module, schema_name, __package__),
            identity=f"modelo.work.{name}",
        ),
    )


_CALCULATE_PARAMETERS = (
    a("work_unit_id"),
    *ADDRESS,
    o("casilla", "--casilla", multiple=True),
    o("binding", "--binding", help_name="override", multiple=True),
    o("borrador_snapshot_id", "--borrador", help_name="borrador"),
    o("m210_gross_income_source", "--m210-gross-income-source", _M210_SOURCE, default="manual"),
    o("actor", "--by"),
    o("relation", "--relation", multiple=True),
    o("row", "--row", multiple=True),
    o("prestacion_inss_exenta", "--prestacion-inss-exenta"),
    o("rescate_plan_pensiones_capital", "--rescate-plan-pensiones-capital"),
    o("rescate_plan_pensiones_aportaciones_pre_2007", "--rescate-plan-pensiones-aportaciones-pre-2007"),
    o("rescate_plan_pensiones_aportaciones_totales", "--rescate-plan-pensiones-aportaciones-totales"),
    o("rescate_type", "--rescate-type", _RESCATE_TYPE),
    o("contingencia_year", "--contingencia-year", WHOLE_NUMBER_VALUE, help_name="rescate_contingencia_year"),
    o("rescate_year", "--rescate-year", WHOLE_NUMBER_VALUE),
    o("sal_beneficio_neto", "--sal-beneficio-neto"),
    o("sal_reserva_dotada", "--sal-reserva-dotada"),
    o("sal_capital_social", "--sal-capital-social"),
    o("autoconsumo_promotor_base", "--autoconsumo-promotor-base"),
    _boolean_choice("joint_return_elected", "--joint-return-elected", help_name="joint_return_elected"),
    o(
        "m303_exonerado_390_attachment_id",
        "--m303-exonerado-390-attachment-id",
        help_name="m303_exonerado_390_attachment_id",
    ),
    o(
        "m303_exonerado_390_sha256",
        "--m303-exonerado-390-sha256",
        help_name="m303_exonerado_390_sha256",
    ),
    _LANG,
)

_REVISION_ADDRESS = (
    o("modelo", "--modelo", _MODELO),
    o("year", "--year", WHOLE_NUMBER_VALUE),
    o("period", "--period"),
    o("registry_revision", "--registry-revision", help_name="revision"),
    o("work_unit_id", "--work-unit-id"),
    o("select", "--select", default="current", help_name="revision_selector"),
    o("bucket_id", "--bucket-id"),
)

MODELO_WORK_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    _leaf(
        "calculate",
        ".modelo_work_calculate_cli",
        _CALCULATE_PARAMETERS,
        _CALC_WRITE,
        ".modelo_results",
        "WorkCalculateResult",
    ),
    _leaf(
        "attest-m303-exonerado-390",
        ".modelo_work_m303_attestation_cli",
        (
            o("year", "--year", WHOLE_NUMBER_VALUE, required=True),
            o("period", "--period", required=True),
            o("observed_at", "--observed-at", required=True),
            o("bucket_id", "--bucket-id"),
            o("actor", "--by"),
            _LANG,
        ),
        _MODEL_WRITE,
        ".modelo_results",
        "M303Exonerado390AttestationResult",
        handler_name="work_attest_m303_exonerado_390",
    ),
    _leaf(
        "attest-prior-carries",
        ".modelo_work_carry_attestation_cli",
        (
            a("work_unit_id", required=True),
            o("confirmed", "--yes", FLAG_VALUE, help_name="attest_prior_carries_yes", flag=True),
            _LANG,
        ),
        _CALC_WRITE,
        ".modelo_work_carry_attestation_payloads",
        "WorkAttestPriorCarriesResult",
    ),
    _leaf(
        "set-value",
        ".modelo_work_manual_entry_cli",
        (
            a("work_unit_id", required=True),
            a("casilla_id", help_name="entry_casilla", required=True),
            a("value", help_name="entry_value", required=True),
            o("confirmed", "--yes", FLAG_VALUE, help_name="entry_yes", flag=True),
            _LANG,
        ),
        _CALC_WRITE,
        ".modelo_work_manual_entry_payloads",
        "WorkManualEntryResult",
    ),
    _leaf(
        "override",
        ".modelo_work_manual_entry_cli",
        (
            a("work_unit_id", required=True),
            a("binding_id", help_name="entry_binding", required=True),
            a("value", help_name="entry_value", required=True),
            o("confirmed", "--yes", FLAG_VALUE, help_name="entry_yes", flag=True),
            _LANG,
        ),
        _CALC_WRITE,
        ".modelo_work_manual_entry_payloads",
        "WorkManualEntryResult",
    ),
    _leaf(
        "attest-no-amount",
        ".modelo_work_manual_entry_cli",
        (
            a("work_unit_id", required=True),
            a("binding_id", help_name="entry_binding", required=True),
            o("confirmed", "--yes", FLAG_VALUE, help_name="entry_yes", flag=True),
            _LANG,
        ),
        _CALC_WRITE,
        ".modelo_work_manual_entry_payloads",
        "WorkManualEntryResult",
    ),
    _leaf(
        "create",
        ".modelo_work_lifecycle_cli",
        (
            o("modelo", "--modelo", TEXT_VALUE, required=True),
            o("year", "--year", WHOLE_NUMBER_VALUE, required=True),
            o("period", "--period", required=True),
            *ADDRESS[3:],
            o("name", "--name"),
            o("actor", "--by"),
            o("allow_not_applicable", "--allow-not-applicable", FLAG_VALUE, flag=True),
            o("quiet", "--quiet", FLAG_VALUE, help_name="create_quiet", flag=True),
            o("causante_ccaa_raw", "--causante-ccaa", help_name="causante_ccaa"),
            _LANG,
        ),
        _CREATE,
        ".modelo_results",
        "WorkCreateResult",
    ),
    _leaf(
        "dependencies",
        ".modelo_work_verification_cli",
        (
            o("year", "--year", WHOLE_NUMBER_VALUE, required=True),
            o("modelo", "--modelo", _MODELO),
            o("period", "--period"),
            _LANG,
        ),
        _CALC_READ,
        ".modelo_results",
        "WorkDependenciesResult",
    ),
    _leaf(
        "discard",
        ".modelo_work_lifecycle_cli",
        (
            a("work_unit_id"),
            *ADDRESS,
            o("actor", "--by"),
            o("reason", "--reason"),
            o("confirmed", "--yes", FLAG_VALUE, help_name="discard_yes", flag=True),
        ),
        _policy(
            frozenset({"encrypted-facts"}),
            frozenset({"local-state"}),
            "local-io",
            CommandWriteRoute.PROFILE_BOUND,
            destructive=True,
        ),
        ".modelo_results",
        "WorkDiscardResult",
    ),
    _leaf(
        "list",
        ".modelo_work_lifecycle_cli",
        (o("bucket_id", "--bucket-id"), o("include_discarded", "--include-discarded", FLAG_VALUE, flag=True), _LANG),
        _MODEL_READ,
        ".modelo_results",
        "WorkListResult",
    ),
    _leaf(
        "select",
        ".modelo_work_select_cli",
        (o("bucket_id", "--bucket-id"), o("include_discarded", "--include-discarded", FLAG_VALUE, flag=True), _LANG),
        _MODEL_READ,
        ".modelo_results",
        "WorkSelectResult",
    ),
    _leaf(
        "rename",
        ".modelo_work_lifecycle_cli",
        (a("work_unit_id"), *ADDRESS, o("name", "--name"), o("actor", "--by")),
        _MODEL_WRITE,
        ".modelo_results",
        "WorkRenameResult",
    ),
    _leaf(
        "status",
        ".modelo_work_lifecycle_cli",
        (a("work_unit_id"), *ADDRESS, _LANG),
        _MODEL_READ,
        ".modelo_results",
        "WorkStatusResult",
    ),
    _leaf(
        "review",
        ".modelo_work_review_cli",
        (a("work_unit_id"), *ADDRESS, _LANG),
        _MODEL_READ,
        ".modelo_results",
        "WorkReviewResult",
    ),
    _leaf(
        "report",
        ".modelo_work_report_cli",
        (
            # ``--output`` leads because it is the one required parameter: the
            # generated handler signature lists parameters in this order, and a
            # required parameter may not follow one carrying a default.
            o(
                "output",
                "--output",
                PATH_VALUE,
                required=True,
                transport_locus=TransportLocus.LOCAL_OUT,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            a("work_unit_id"),
            *ADDRESS,
            o("document_format", "--document-format", _REPORT_DOCUMENT_FORMAT, default="csv"),
            OptionSpec(
                "replace_existing",
                ("--replace",),
                FLAG_VALUE,
                ParameterDefault.value(False),
                TranslationKey("cli.app.modelo.export.replace_help"),
                is_flag=True,
                flag_value=True,
            ),
            _LANG,
        ),
        _REPORT,
        ".modelo_results",
        "WorkReportResult",
    ),
    _leaf(
        "report-verify",
        ".modelo_work_report_cli",
        (
            ArgumentSpec(
                "path",
                PATH_VALUE,
                ParameterDefault.required(),
                translation_key("cli.app.modelo.work.report_verify_path_help"),
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            o("trusted_key", "--trusted-key"),
            o("document_only", "--document-only", FLAG_VALUE, flag=True),
            _LANG,
        ),
        _REPORT_VERIFY,
        ".modelo_results",
        "WorkReportVerifyResult",
    ),
    _leaf(
        "revisions",
        ".modelo_work_revision_cli",
        (a("work_unit_id"), *ADDRESS, _LANG),
        _MODEL_READ,
        ".modelo_results",
        "WorkRevisionsResult",
    ),
    _leaf(
        "revision",
        ".modelo_work_revision_cli",
        (
            a("calculation_revision_id"),
            *_REVISION_ADDRESS,
            o("verbose", "--verbose", FLAG_VALUE, help_name="revision_verbose", flag=True),
            _LANG,
        ),
        _MODEL_READ,
        ".modelo_work_revision_payloads",
        "WorkRevisionResult",
    ),
    _leaf(
        "observations",
        ".modelo_work_revision_cli",
        (a("calculation_revision_id"), *_REVISION_ADDRESS, _LANG),
        _MODEL_READ,
        ".modelo_work_revision_payloads",
        "WorkObservationsResult",
    ),
    _leaf(
        "run",
        ".modelo_work_runs_cli",
        (a("run_id", required=True), _LANG),
        _MODEL_READ,
        ".modelo_aux_payloads",
        "WorkRunResult",
    ),
    _leaf(
        "run-details",
        ".modelo_work_runs_cli",
        (a("run_id", required=True), _LANG),
        _MODEL_READ,
        ".modelo_aux_payloads",
        "WorkRunDetailsResult",
    ),
    _leaf(
        "runs",
        ".modelo_work_runs_cli",
        (_LANG,),
        _MODEL_READ,
        ".modelo_aux_payloads",
        "WorkRunsResult",
    ),
    _leaf(
        "resume",
        ".modelo_work_runs_cli",
        (
            a("target", help_name="resume_target"),
            *ADDRESS[:4],
            o("select", "--select", help_name="revision_selector"),
            o("work_unit_id", "--work-unit-id"),
            o("calculation_revision_id", "--calculation-revision-id"),
            o("bucket_id", "--bucket-id"),
            _LANG,
        ),
        _MODEL_READ,
        ".modelo_query_results",
        "WorkResumeResult",
    ),
    _leaf(
        "verify",
        ".modelo_work_verification_cli",
        (
            a("calculation_revision_id"),
            *ADDRESS[:4],
            o("work_unit_id", "--work-unit-id"),
            o("select", "--select", _VERIFY_SELECTOR, default="current", help_name="verify_selector"),
            o("bucket_id", "--bucket-id"),
            o("actor", "--by"),
            _LANG,
        ),
        _CALC_WRITE,
        ".modelo_results",
        "WorkVerifyResult",
    ),
    _leaf(
        "accept-disagreement",
        ".modelo_work_disagreement_cli",
        (
            a("finding_id", help_name="disagreement_finding_id", required=True),
            o("calculation_revision_id", "--calculation-revision-id"),
            *ADDRESS[:4],
            o("work_unit_id", "--work-unit-id"),
            o("bucket_id", "--bucket-id"),
            o("reason", "--reason", help_name="disagreement_reason"),
            _LANG,
        ),
        _MODEL_WRITE,
        ".modelo_work_disagreement_payloads",
        "WorkAcceptDisagreementResult",
    ),
    _leaf(
        "revoke-disagreement",
        ".modelo_work_disagreement_cli",
        (
            a("finding_id", help_name="disagreement_finding_id", required=True),
            o("calculation_revision_id", "--calculation-revision-id"),
            *ADDRESS[:4],
            o("work_unit_id", "--work-unit-id"),
            o("bucket_id", "--bucket-id"),
            o("expected_revision", "--expected-revision", help_name="disagreement_expected_revision"),
            _LANG,
        ),
        _MODEL_WRITE,
        ".modelo_work_disagreement_payloads",
        "WorkRevokeDisagreementResult",
    ),
    _leaf(
        "disagreements",
        ".modelo_work_disagreement_cli",
        (
            o("calculation_revision_id", "--calculation-revision-id"),
            *ADDRESS[:4],
            o("work_unit_id", "--work-unit-id"),
            o("bucket_id", "--bucket-id"),
            _LANG,
        ),
        _MODEL_READ,
        ".modelo_work_disagreement_payloads",
        "WorkDisagreementsResult",
    ),
    _leaf(
        "file",
        ".modelo_work_verification_cli",
        (
            a("calculation_revision_id"),
            *ADDRESS[:4],
            o("work_unit_id", "--work-unit-id"),
            o("select", "--select", default="current", help_name="revision_selector"),
            o("bucket_id", "--bucket-id"),
            o("actor", "--by"),
            o("notes", "--notes"),
            o("refund_election", "--refund-election", _REFUND, default="compensar"),
            o("payment_election", "--payment-election", _PAYMENT, default="ingreso"),
            o("prior_domiciliation_election", "--prior-domiciliation-election", _DOMICILIATION, default="keep"),
            _LANG,
        ),
        _FILE,
        ".modelo_results",
        "WorkFileResult",
    ),
    _leaf(
        "wizard",
        ".modelo_work_wizard_cli",
        (
            a("work_unit_id"),
            *ADDRESS,
            o("actor", "--by"),
            o("output_language_opt", "--output-language", LANGUAGE, help_name="output_language"),
        ),
        _WIZARD,
        ".modelo_work_wizard_payloads",
        "WorkWizardResult",
    ),
)

__all__ = ["MODELO_WORK_COMMAND_SPECS"]
