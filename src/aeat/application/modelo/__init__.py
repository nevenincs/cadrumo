"""Public application facade for modelo work-unit services.

This package is the canonical application-layer import boundary for modelo
CLI transports and cross-package application services. Callers import from
``aeat.application.modelo`` instead of private ``_...`` modules so work
selection, registry revision checks, calculation, verification, filing,
export, reconciliation, and storage orchestration stay behind one facade.

Bucket scoping is explicit at the API boundary. Services accept a caller
provided ``bucket_id`` or a resolved work target; CLI modules may derive that
value from the active profile, but the application surface itself does not read
implicit workflow state.

The facade carries :class:`CalculationRevision` and :class:`WorkUnit` through
the operator lifecycle: work-unit creation and addressing, calculation-revision
creation, verification, filing, export, history, reconciliation, registry
discovery, M036 declaration records, IVA-wallet decisions, projections, and
advisory helpers. It also re-exports the status and finding vocabulary used by
those services, including :class:`CalculationRevisionState`,
:class:`ModeloRecordStatus`, :class:`ModeloVerificationFindingKind`, and
:class:`VerificationCompletenessStatus`.

Verification, filing, and export remain owned by their focused service modules.
``verify_modelo_revision`` persists a verification report for one
:class:`CalculationRevision`; filing and export then consume the same persisted
revision rather than rebuilding parallel workflow state.

Local filing and external evidence are deliberately separate. ``file_modelo_revision``
creates an internal current :class:`aeat.domain.modelos.ModeloRecord` without
:class:`aeat.domain.modelos.ExternalEvidence`; ``import_external_filing_evidence``
creates the AEAT-attested evidence baseline, and ``amend_modelo_revision`` requires
that baseline before recording a :class:`CalculationRevisionAmendmentKind`.

See Also:
    :mod:`aeat.application.modelo._work_lifecycle`:
        Work-unit creation, listing, rename, discard, and lookup services.
    :mod:`aeat.application.modelo._work_addressing`:
        Visible modelo/year/period addressing and exact-id resolution.
    :mod:`aeat.application.modelo._calculation_actions`:
        Calculation revision creation, lookup, and completion services.
    :mod:`aeat.application.modelo._verification_actions`:
        Verification findings and report persistence for draft revisions.
    :mod:`aeat.application.modelo._filing_actions`:
        Local filing-record transitions and verification-report reads.
    :mod:`aeat.application.modelo._external_import_actions`:
        External-evidence import path that stamps official AEAT evidence on
        current filing records.
    :mod:`aeat.application.modelo._amendment_actions`:
        Amendment path for current externally evidenced filing records.
    :mod:`aeat.application.modelo._workflow_gate`:
        Workflow preflight adapter used by verification and filing services.
    :mod:`aeat.application.modelo._export`:
        Local official-file export for verified or filed revisions.
"""

from __future__ import annotations

from ...domain.modelos import (
    CalculationRevisionState,
    Modelo184MemberRow,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo349CountryPrefixContextError,
    Modelo349OperadorRow,
    ModeloDetailRow,
    ModeloRecordStatus,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    validate_m349_country_prefix_context,
    validate_m349_nif_format,
)
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionAmendmentKind
from ...domain.modelos._errors import ModeloError
from ...domain.modelos._filing_record import ExternalEvidenceKind
from ...domain.modelos._work_unit import WorkUnit
from ._action_errors import (
    AmendmentEvidenceMissingError,
    AmendmentOverrideCasillaError,
    AmendmentTargetStateError,
    AmendmentVerificationRefusedError,
    CalculationRegistryUnavailableError,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    CasillaProvenanceMissingError,
    ExternalModeloImportError,
    ModeloAggregationBindingError,
    ModeloApplicabilityFilterError,
    ModeloCrossPeriodCleanStateError,
    ModeloLocalObservationError,
    ModeloProfileReadinessError,
    ModeloRecordNotFoundError,
    ModeloRefundElectionNotEligibleError,
    ModeloRequiredBindingsMissingError,
    ModeloWorkflowGateError,
    StoredCalculationDriftError,
    VerificationReportNotFoundError,
    WorkUnitAlreadyDiscardedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    WorkUnitRevisionDivergenceError,
)
from ._amendment_actions import amend_modelo_revision
from ._binding_readiness import profile_resolvable_binding_ids
from ._borrador_binding import (
    Modelo100BorradorBindingCommand,
    Modelo100BorradorBindingError,
    Modelo100BorradorSourceResolver,
    resolve_modelo_100_borrador_bindings,
)
from ._calculate_input import (
    Modelo202ModalitySummary,
    ModeloAuthorizationAdvisorySummary,
    ModeloWorkCalculationServiceResult,
    WorkCalculateInputBundle,
    apply_calculation_shortcut_inputs,
    authorization_advisory_for_modelo,
    build_work_calculate_input_bundle,
    calculate_modelo_work_revision,
    is_detail_casilla_override_key,
    modelo_202_modality_for_work_unit,
)
from ._calculation_actions import (
    BucketAggregationCalculationResult,
    assert_no_novel_source_kinds,
    calculate_modelo_revision,
    calculate_modelo_revision_from_bucket_aggregation,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    get_calculation_revision,
    list_calculation_revisions,
    mark_revision_verificado_completo,
)
from ._export import (
    ModeloExportCommand,
    ModeloExportCrossBucketRefusedError,
    ModeloExportNoActiveBucketError,
    ModeloExportOutputPathError,
    ModeloExportResult,
    ModeloExportUnsupportedError,
    export_modelo_revision,
)
from ._external_import_actions import import_external_filing_evidence
from ._filed_revision_observation import (
    APP_FILING_SOURCE_KIND,
    persist_filed_revision_observation,
)
from ._filing_actions import (
    file_modelo_revision,
    get_filing_record,
    get_verification_report,
    list_filing_records,
    list_verification_reports,
)
from ._history import (
    WorkUnitHistory,
    WorkUnitHistoryEvent,
    assemble_work_unit_history,
)
from ._iva_wallet_gate import (
    ModeloIvaWalletReconciliationBlocked,
    ModeloIvaWalletReconciliationBlockedError,
    require_persisted_iva_compensation_decision_matches_revision,
)
from ._iva_wallet_seed import (
    ModeloIvaWalletCorrectionNoRecordError,
    ModeloIvaWalletCorrectionSealedError,
    ModeloIvaWalletOverrideFreshWalletError,
    ModeloIvaWalletOverrideSealedError,
    ModeloIvaWalletSeedError,
    ModeloIvaWalletSeedNegativeAmountError,
    ModeloIvaWalletSeedNoTaxpayerError,
    correct_iva_compensation_period_for_bucket,
    record_iva_compensation_override_for_bucket,
    seed_iva_compensation_period_for_bucket,
)
from ._local_observation_actions import (
    OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND,
    ModeloLocalObservationResult,
    record_operator_local_observation,
)
from ._m036_lifecycle import (
    M036DeclarationCommand,
    M036DeclarationResult,
    list_m036_declarations,
    read_m036_declaration,
    record_m036_declaration,
)
from ._maritime_preview import (
    ModeloMaritimeExemptionPreview,
    maritime_facts_from_active_profile,
    preview_maritime_exemption_for_active_profile,
)
from ._participation_index_rebuild import (
    ParticipationRebuildStats,
    rebuild_participation_index,
)
from ._profile_binding import (
    ProfileBindingResolutionError,
    resolve_profile_sourced_bindings,
)
from ._profile_readiness_gate import (
    modelo_applicability_refusal,
    modelo_work_profile_baseline_missing_paths,
    modelo_work_profile_baseline_validation_issues,
    modelo_work_profile_preflight_report,
    pre_activity_period_refusal,
    require_existing_profile_baseline_ready_for_modelo_work,
    require_profile_ready_for_modelo_work,
    require_profile_ready_for_work_unit,
)
from ._projection import (
    ModeloCompareDeltaRow,
    ModeloCompareNeedTwoYearsError,
    ModeloCompareNoRevisionsError,
    ModeloCompareNoUsableRevisionsError,
    ModeloCompareNoWorkUnitsError,
    ModeloCompareSection,
    ModeloCompareServiceResult,
    ModeloProjectInvalidDecimalOverrideError,
    ModeloProjectionCasillaObservation,
    ModeloProjectionError,
    ModeloProjectM100Projection,
    ModeloProjectM130Accumulated,
    ModeloProjectNoM130RevisionsError,
    ModeloProjectNoM130UnitsError,
    ModeloProjectServiceResult,
    compare_modelo_years,
    project_modelo_100_from_m130,
)
from ._reconcile import (
    ModeloReconciliationBytesCommand,
    ModeloReconciliationCommand,
    ModeloReconciliationDiff,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationHistoryEntry,
    ModeloReconciliationReport,
    ModeloReconciliationVerdict,
    ReconciliationCrossBucketRefusedError,
    ReconciliationDeclaracionSourceUnsupportedError,
    ReconciliationEvidenceInvalidError,
    list_modelo_reconciliations,
    modelo_reconcile,
    modelo_reconcile_bytes,
)
from ._registry_discovery import (
    declared_modelo_period_tokens,
    registry_bindings,
    registry_bindings_for_scope,
    registry_bindings_for_year,
    registry_casillas,
    registry_casillas_for_registry_scope,
    registry_casillas_for_scope,
    registry_describe_modelo,
    registry_describe_modelo_for_registry_scope,
    registry_describe_modelo_for_scope,
    registry_formulas,
    registry_formulas_for_registry_scope,
    registry_formulas_for_scope,
    registry_list_modelos,
    registry_modelo_codes,
)
from ._result_summary import (
    CalculationResultSummary,
    ResultSummaryRow,
    calculation_result_summary,
)
from ._selectors import (
    ModeloCalculationRevisionCandidate,
    ModeloCalculationRevisionDefault,
    ModeloCalculationRevisionSelection,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorError,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
    ModeloVerifySelector,
    ModeloWorkNoActiveBucketError,
    ModeloWorkResolution,
    ModeloWorkRevisionConflictError,
    ModeloWorkSelectorContradictionError,
    ModeloWorkSelectorError,
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    ModeloWorkUnitCandidate,
    ModeloWorkUnitNotFoundError,
    ModeloWorkVisibleTargetAmbiguousError,
    resolve_modelo_calculation_revision_pick,
    resolve_modelo_work_bucket,
    resolve_modelo_work_unit,
    select_current_draft_revision,
    select_current_verified_revision,
    select_exportable_revision,
    select_modelo_calculation_revision,
    visible_target_work_units,
)
from ._taxation_comparison import (
    TaxationComparisonError,
    TaxationComparisonResult,
    TaxationRecommendation,
    compare_taxation_for_work_address,
    compare_taxation_for_work_unit,
    compare_taxation_modes,
)
from ._verification_actions import (
    derive_taxpayer_files_economic_activity,
    verify_modelo_revision,
)
from ._work_addressing import (
    ModeloExactWorkUnitTarget,
    ModeloResolvedRevisionProjection,
    ModeloResolvedWorkProjection,
    ModeloRevisionPick,
    ModeloVisibleFilingTarget,
    ModeloWorkAddress,
    ModeloWorkAddressNotFoundError,
    ModeloWorkEnsureResult,
    ModeloWorkPeriodTokenError,
    ModeloWorkRegistryYearMismatchError,
    ModeloWorkTarget,
    ensure_modelo_work_unit_for_visible_target,
    modelo_work_address_from_operator_target,
    project_modelo_work_target,
    project_modelo_work_unit,
    resolve_exportable_modelo_calculation_revision_address,
    resolve_fileable_modelo_calculation_revision_address,
    resolve_modelo_calculation_revision_address,
    resolve_modelo_revision_for_operator_target,
    resolve_modelo_revision_pick,
    resolve_modelo_work_address,
    resolve_modelo_work_address_unit,
    resolve_modelo_work_target,
    resolve_modelo_work_unit_for_operator_target,
    resolve_modelo_work_unit_id,
    resolve_optional_modelo_work_address,
    resolve_registry_revision_for_work_target,
    resolve_verifiable_modelo_calculation_revision_address,
    work_address_for_modelo_target,
)
from ._work_create_policy import (
    STUB_MODELO_LOCALE_KEYS,
    STUB_ONLY_MODELOS,
    ModeloWorkCreateApplicabilityRefusal,
    guard_active_profile_foral_ccaa,
    modelo_work_create_applicability_refusal,
    modelo_work_create_refusal_locale_key,
)
from ._work_lifecycle import (
    create_work_unit,
    discard_work_unit,
    get_work_unit,
    list_work_units,
    rename_work_unit,
)
from ._work_plazo import (
    ModeloWorkPlazoSummary,
    ModeloWorkRecargoSummary,
    modelo_work_plazo_summary,
)
from ._workflow_gate import workflow_period_for_work_unit

__all__ = [
    "APP_FILING_SOURCE_KIND",
    "OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND",
    "STUB_MODELO_LOCALE_KEYS",
    "STUB_ONLY_MODELOS",
    "AmendmentEvidenceMissingError",
    "AmendmentOverrideCasillaError",
    "AmendmentTargetStateError",
    "AmendmentVerificationRefusedError",
    "BucketAggregationCalculationResult",
    "CalculationRegistryUnavailableError",
    "CalculationResultSummary",
    "CalculationRevision",
    "CalculationRevisionAmendmentKind",
    "CalculationRevisionNotFoundError",
    "CalculationRevisionState",
    "CalculationRevisionStateError",
    "CasillaProvenanceMissingError",
    "ExternalEvidenceKind",
    "ExternalModeloImportError",
    "M036DeclarationCommand",
    "M036DeclarationResult",
    "Modelo100BorradorBindingCommand",
    "Modelo100BorradorBindingError",
    "Modelo100BorradorSourceResolver",
    "Modelo184MemberRow",
    "Modelo202ModalitySummary",
    "Modelo232VinculadaRow",
    "Modelo347ContraparteRow",
    "Modelo349CountryPrefixContextError",
    "Modelo349OperadorRow",
    "ModeloAggregationBindingError",
    "ModeloApplicabilityFilterError",
    "ModeloAuthorizationAdvisorySummary",
    "ModeloCalculationRevisionCandidate",
    "ModeloCalculationRevisionDefault",
    "ModeloCalculationRevisionSelection",
    "ModeloCalculationRevisionSelector",
    "ModeloCalculationRevisionSelectorAmbiguousError",
    "ModeloCalculationRevisionSelectorError",
    "ModeloCalculationRevisionSelectorNotFoundError",
    "ModeloCalculationRevisionSelectorStateError",
    "ModeloCompareDeltaRow",
    "ModeloCompareNeedTwoYearsError",
    "ModeloCompareNoRevisionsError",
    "ModeloCompareNoUsableRevisionsError",
    "ModeloCompareNoWorkUnitsError",
    "ModeloCompareSection",
    "ModeloCompareServiceResult",
    "ModeloCrossPeriodCleanStateError",
    "ModeloDetailRow",
    "ModeloError",
    "ModeloExactWorkUnitTarget",
    "ModeloExportCommand",
    "ModeloExportCrossBucketRefusedError",
    "ModeloExportNoActiveBucketError",
    "ModeloExportOutputPathError",
    "ModeloExportResult",
    "ModeloExportUnsupportedError",
    "ModeloIvaWalletCorrectionNoRecordError",
    "ModeloIvaWalletCorrectionSealedError",
    "ModeloIvaWalletOverrideFreshWalletError",
    "ModeloIvaWalletOverrideSealedError",
    "ModeloIvaWalletReconciliationBlocked",
    "ModeloIvaWalletReconciliationBlockedError",
    "ModeloIvaWalletSeedError",
    "ModeloIvaWalletSeedNegativeAmountError",
    "ModeloIvaWalletSeedNoTaxpayerError",
    "ModeloLocalObservationError",
    "ModeloLocalObservationResult",
    "ModeloMaritimeExemptionPreview",
    "ModeloProfileReadinessError",
    "ModeloProjectInvalidDecimalOverrideError",
    "ModeloProjectM100Projection",
    "ModeloProjectM130Accumulated",
    "ModeloProjectNoM130RevisionsError",
    "ModeloProjectNoM130UnitsError",
    "ModeloProjectServiceResult",
    "ModeloProjectionCasillaObservation",
    "ModeloProjectionError",
    "ModeloReconciliationBytesCommand",
    "ModeloReconciliationCommand",
    "ModeloReconciliationDiff",
    "ModeloReconciliationEvidenceKind",
    "ModeloReconciliationHistoryEntry",
    "ModeloReconciliationReport",
    "ModeloReconciliationVerdict",
    "ModeloRecordNotFoundError",
    "ModeloRecordStatus",
    "ModeloRefundElectionNotEligibleError",
    "ModeloRequiredBindingsMissingError",
    "ModeloResolvedRevisionProjection",
    "ModeloResolvedWorkProjection",
    "ModeloRevisionPick",
    "ModeloVerificationFindingKind",
    "ModeloVerificationFindingSeverity",
    "ModeloVerifySelector",
    "ModeloVisibleFilingTarget",
    "ModeloWorkAddress",
    "ModeloWorkAddressNotFoundError",
    "ModeloWorkCalculationServiceResult",
    "ModeloWorkCreateApplicabilityRefusal",
    "ModeloWorkEnsureResult",
    "ModeloWorkNoActiveBucketError",
    "ModeloWorkPeriodTokenError",
    "ModeloWorkPlazoSummary",
    "ModeloWorkRecargoSummary",
    "ModeloWorkRegistryYearMismatchError",
    "ModeloWorkResolution",
    "ModeloWorkRevisionConflictError",
    "ModeloWorkSelectorContradictionError",
    "ModeloWorkSelectorError",
    "ModeloWorkSelectorRequest",
    "ModeloWorkSelectorState",
    "ModeloWorkTarget",
    "ModeloWorkUnitCandidate",
    "ModeloWorkUnitNotFoundError",
    "ModeloWorkVisibleTargetAmbiguousError",
    "ModeloWorkflowGateError",
    "ParticipationRebuildStats",
    "ProfileBindingResolutionError",
    "ReconciliationCrossBucketRefusedError",
    "ReconciliationDeclaracionSourceUnsupportedError",
    "ReconciliationEvidenceInvalidError",
    "ResultSummaryRow",
    "StoredCalculationDriftError",
    "TaxationComparisonError",
    "TaxationComparisonResult",
    "TaxationRecommendation",
    "VerificationCompletenessStatus",
    "VerificationReportNotFoundError",
    "WorkCalculateInputBundle",
    "WorkUnit",
    "WorkUnitAlreadyDiscardedError",
    "WorkUnitHistory",
    "WorkUnitHistoryEvent",
    "WorkUnitMutationRefusedError",
    "WorkUnitNotFoundError",
    "WorkUnitRevisionDivergenceError",
    "amend_modelo_revision",
    "apply_calculation_shortcut_inputs",
    "assemble_work_unit_history",
    "assert_no_novel_source_kinds",
    "authorization_advisory_for_modelo",
    "build_work_calculate_input_bundle",
    "calculate_modelo_revision",
    "calculate_modelo_revision_from_bucket_aggregation",
    "calculate_modelo_revision_from_bucket_aggregation_with_diagnostics",
    "calculate_modelo_work_revision",
    "calculation_result_summary",
    "compare_modelo_years",
    "compare_taxation_for_work_address",
    "compare_taxation_for_work_unit",
    "compare_taxation_modes",
    "correct_iva_compensation_period_for_bucket",
    "create_work_unit",
    "declared_modelo_period_tokens",
    "derive_taxpayer_files_economic_activity",
    "discard_work_unit",
    "ensure_modelo_work_unit_for_visible_target",
    "export_modelo_revision",
    "file_modelo_revision",
    "get_calculation_revision",
    "get_filing_record",
    "get_verification_report",
    "get_work_unit",
    "guard_active_profile_foral_ccaa",
    "import_external_filing_evidence",
    "is_detail_casilla_override_key",
    "list_calculation_revisions",
    "list_filing_records",
    "list_m036_declarations",
    "list_modelo_reconciliations",
    "list_verification_reports",
    "list_work_units",
    "maritime_facts_from_active_profile",
    "mark_revision_verificado_completo",
    "modelo_202_modality_for_work_unit",
    "modelo_applicability_refusal",
    "modelo_reconcile",
    "modelo_reconcile_bytes",
    "modelo_work_address_from_operator_target",
    "modelo_work_create_applicability_refusal",
    "modelo_work_create_refusal_locale_key",
    "modelo_work_plazo_summary",
    "modelo_work_profile_baseline_missing_paths",
    "modelo_work_profile_baseline_validation_issues",
    "modelo_work_profile_preflight_report",
    "persist_filed_revision_observation",
    "pre_activity_period_refusal",
    "preview_maritime_exemption_for_active_profile",
    "profile_resolvable_binding_ids",
    "project_modelo_100_from_m130",
    "project_modelo_work_target",
    "project_modelo_work_unit",
    "read_m036_declaration",
    "rebuild_participation_index",
    "record_iva_compensation_override_for_bucket",
    "record_m036_declaration",
    "record_operator_local_observation",
    "registry_bindings",
    "registry_bindings_for_scope",
    "registry_bindings_for_year",
    "registry_casillas",
    "registry_casillas_for_registry_scope",
    "registry_casillas_for_scope",
    "registry_describe_modelo",
    "registry_describe_modelo_for_registry_scope",
    "registry_describe_modelo_for_scope",
    "registry_formulas",
    "registry_formulas_for_registry_scope",
    "registry_formulas_for_scope",
    "registry_list_modelos",
    "registry_modelo_codes",
    "rename_work_unit",
    "require_existing_profile_baseline_ready_for_modelo_work",
    "require_persisted_iva_compensation_decision_matches_revision",
    "require_profile_ready_for_modelo_work",
    "require_profile_ready_for_work_unit",
    "resolve_exportable_modelo_calculation_revision_address",
    "resolve_fileable_modelo_calculation_revision_address",
    "resolve_modelo_100_borrador_bindings",
    "resolve_modelo_calculation_revision_address",
    "resolve_modelo_calculation_revision_pick",
    "resolve_modelo_revision_for_operator_target",
    "resolve_modelo_revision_pick",
    "resolve_modelo_work_address",
    "resolve_modelo_work_address_unit",
    "resolve_modelo_work_bucket",
    "resolve_modelo_work_target",
    "resolve_modelo_work_unit",
    "resolve_modelo_work_unit_for_operator_target",
    "resolve_modelo_work_unit_id",
    "resolve_optional_modelo_work_address",
    "resolve_profile_sourced_bindings",
    "resolve_registry_revision_for_work_target",
    "resolve_verifiable_modelo_calculation_revision_address",
    "seed_iva_compensation_period_for_bucket",
    "select_current_draft_revision",
    "select_current_verified_revision",
    "select_exportable_revision",
    "select_modelo_calculation_revision",
    "validate_m349_country_prefix_context",
    "validate_m349_nif_format",
    "verify_modelo_revision",
    "visible_target_work_units",
    "work_address_for_modelo_target",
    "workflow_period_for_work_unit",
]
