"""Application services for modelo work-unit lifecycle.

The modelo work-unit verbs (``create``, ``list``, ``status``,
``rename``) call into this package. The CLI layer at
``aeat.entrypoints.cli._modelo`` is a thin Typer transport over
the services exposed here.

Bucket scoping is honoured at the API boundary: every action
accepts an explicit ``bucket_id`` rather than implicitly reading
the active profile. The CLI layer derives ``bucket_id`` from the
active profile when the caller did not pass one explicitly; this
keeps the application service unit-testable without a workflow-
state fixture.

This module re-exports :class:`CalculationRevision`, :class:`ModeloRecord`,
and other core types for convenient access by callers.

Verification boundary
---------------------
``verify_modelo_revision`` enforces a four-layer gate before the
``VERIFICADO_COMPLETO`` state transition is granted:

1. **State machine** -- the target revision must be in ``BORRADOR``
   state; any other state raises :exc:`CalculationRevisionStateError`.

2. **Per-casilla required-input gate (Layer 1)** -- every casilla
   declared ``required = true`` and ``input_kind = "manual"`` in the
   registry must be present in the revision's ``input_values_by_casilla_id``.
   Absent casillas produce :attr:`ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA`
   findings and set ``completeness_status`` to ``INCOMPLETE``.

3. **Cross-casilla predicate gate (Layer 2)** -- each
   :class:`~aeat.domain.calculations.registry.VerificationPredicateDefinition`
   attached to the revision's registry snapshot is evaluated against the
   stored ``casilla_values``.  A failing predicate produces a
   :attr:`ModeloVerificationFindingKind.BLOCKING_RULE` finding.

4. **Provenance re-validation** -- :func:`_assert_revision_content_integrity`
   re-derives the SHA-256 content address from the stored payload and
   raises :exc:`StoredCalculationDriftError` if it does not match the
   persisted ``calculation_revision_id``.  This defends against raw-storage
   tampering or schema-migration bugs that mutate the payload without
   updating the content-addressed id.

Only when layers 1-3 produce zero blocking findings AND layer 4 passes
does ``verify_modelo_revision`` grant ``VERIFICADO_COMPLETO`` and
persist the :class:`~aeat.domain.modelos._verification_report.ModeloVerificationReport`.

Use of :class:`CalculationRevision` for compliance.
"""

from __future__ import annotations

from ...domain.modelos import (
    CalculationRevisionState,
    Modelo184MemberRow,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo349OperadorRow,
    ModeloDetailRow,
    ModeloRecordStatus,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    validate_m349_nif_format,
)
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionAmendmentKind
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
    ModeloCrossPeriodCleanStateError,
    ModeloRecordNotFoundError,
    ModeloRefundElectionNotEligibleError,
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
    ModeloReconciliationHistoryEntry,
    ModeloReconciliationReport,
    ModeloReconciliationSourceKind,
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
    registry_casillas_for_scope,
    registry_describe_modelo,
    registry_describe_modelo_for_scope,
    registry_formulas,
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
    "Modelo349OperadorRow",
    "ModeloAggregationBindingError",
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
    "ModeloExactWorkUnitTarget",
    "ModeloExportCommand",
    "ModeloExportCrossBucketRefusedError",
    "ModeloExportNoActiveBucketError",
    "ModeloExportOutputPathError",
    "ModeloExportResult",
    "ModeloIvaWalletCorrectionNoRecordError",
    "ModeloIvaWalletCorrectionSealedError",
    "ModeloIvaWalletOverrideFreshWalletError",
    "ModeloIvaWalletOverrideSealedError",
    "ModeloIvaWalletReconciliationBlocked",
    "ModeloIvaWalletReconciliationBlockedError",
    "ModeloIvaWalletSeedError",
    "ModeloIvaWalletSeedNegativeAmountError",
    "ModeloIvaWalletSeedNoTaxpayerError",
    "ModeloMaritimeExemptionPreview",
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
    "ModeloReconciliationHistoryEntry",
    "ModeloReconciliationReport",
    "ModeloReconciliationSourceKind",
    "ModeloReconciliationVerdict",
    "ModeloRecordNotFoundError",
    "ModeloRecordStatus",
    "ModeloRefundElectionNotEligibleError",
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
    "list_calculation_revisions",
    "list_filing_records",
    "list_m036_declarations",
    "list_modelo_reconciliations",
    "list_verification_reports",
    "list_work_units",
    "maritime_facts_from_active_profile",
    "mark_revision_verificado_completo",
    "modelo_202_modality_for_work_unit",
    "modelo_reconcile",
    "modelo_reconcile_bytes",
    "modelo_work_address_from_operator_target",
    "modelo_work_create_applicability_refusal",
    "modelo_work_create_refusal_locale_key",
    "modelo_work_plazo_summary",
    "persist_filed_revision_observation",
    "preview_maritime_exemption_for_active_profile",
    "profile_resolvable_binding_ids",
    "project_modelo_100_from_m130",
    "project_modelo_work_target",
    "project_modelo_work_unit",
    "read_m036_declaration",
    "rebuild_participation_index",
    "record_iva_compensation_override_for_bucket",
    "record_m036_declaration",
    "registry_bindings",
    "registry_bindings_for_scope",
    "registry_bindings_for_year",
    "registry_casillas",
    "registry_casillas_for_scope",
    "registry_describe_modelo",
    "registry_describe_modelo_for_scope",
    "registry_formulas",
    "registry_formulas_for_scope",
    "registry_list_modelos",
    "registry_modelo_codes",
    "rename_work_unit",
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
    "validate_m349_nif_format",
    "derive_taxpayer_files_economic_activity",
    "verify_modelo_revision",
    "visible_target_work_units",
    "work_address_for_modelo_target",
    "workflow_period_for_work_unit",
]
